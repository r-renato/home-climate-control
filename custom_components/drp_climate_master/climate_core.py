"""Support for Climate Devices."""
from __future__ import annotations

import time
from datetime import datetime, date
import copy
import asyncio
from collections import namedtuple
from collections.abc import Callable
import logging
from typing import Any

import psychrolib
import voluptuous as vol

from homeassistant.core import Event, HomeAssistant, ServiceCall, callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.discovery import async_load_platform
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.reload import async_setup_reload_service
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers.entity import Entity
from homeassistant.const import (
    CONF_NAME,
    CONF_SENSORS,
    EVENT_HOMEASSISTANT_STOP,
    Platform,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.helpers.event import (
    async_track_state_change_event,
    async_track_time_interval,
    async_call_later,
) 
from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from .helpers import weighted_average, is_leap_year

from .const import (
    ATTR_HUB,
    CONFORT_ZONES,
    DOMAIN,
    SERVICE_RESTART,
    SERVICE_STOP,
    SIGNAL_START_ENTITY,
    SIGNAL_STOP_ENTITY,
    SEASONS_BY_DATE,
    DewPointPerception,
)
from .const import (
    ATTR_SENSOR_CURRENT_TEMP,
    ATTR_SENSOR_CURRENT_HUMI,
    CONF_AREA,
    CONF_AREAS,
    CONF_AREA_HOME,
    CONF_MQ,
    CONF_CLIMATE,
    CONF_INDOOR,
    CONF_RADIANT,
    CONF_TEMPERATURE,
    CONF_HUMIDITY,
    CONF_DEVICES,
    CONF_VMC,
    CONF_WEATHER,
    CONF_T_AMBIENT,
    CONF_H_AMBIENT,
    CONF_T_WATER,
    CONF_T_OUTDOOR,
    CONF_POWER_ON_NIGHT,
    CONF_POWER_ON_TODAY,
    CONF_ALARMS,
    CONF_HIGH_PRESSURE,
    CONF_DEW_POINT,
    CONF_LOW_WATER_TEMP,
    CONF_HIGH_WATER_TEMP,
    CONF_ALARM,
    CONF_HOME_WINDOWS_STATE,

    CONF_POWER,
    CONF_VENT_RECIRCULATION,
    CONF_T_SETPOINT,
    CONF_H_SETPOINT,
    CONF_SEASON,
    CONF_ACTUATOR,
    CONF_WINTER,
    CONF_SUMMER,
    CONF_AUTUMN,
    CONF_SPRING,

    TURN_ON,
    TURN_OFF,

    ClimateSensor,
)

_LOGGER = logging.getLogger(__name__)

async def async_climate_core_setup(
    hass: HomeAssistant,
    config: ConfigType,
) -> bool:
    """Set up Climate Core component."""

    await async_setup_reload_service(hass, DOMAIN, [DOMAIN])

    if DOMAIN in hass.data and config[DOMAIN] == []:
        hubs = hass.data[DOMAIN]
        for name in hubs:
            if not await hubs[name].async_setup():
                return False
        hub_collect = hass.data[DOMAIN]
    else:
        hass.data[DOMAIN] = hub_collect = {}

    for conf_hub in config[DOMAIN]:
        _LOGGER.info( '%s starting setup.', conf_hub[CONF_NAME] )
        my_hub = DevicesHub(hass, conf_hub)
        hub_collect[conf_hub[CONF_NAME]] = my_hub

        # modbus needs to be activated before components are loaded
        # to avoid a racing problem
        if not await my_hub.async_setup():
            return False

        # load platforms
        hass.async_create_task(
            async_load_platform(hass, Platform.CLIMATE, DOMAIN, conf_hub, config)
        )

    psychrolib.SetUnitSystem(psychrolib.SI)

    async def async_stop_climate_core(event: Event) -> None:
        """Stop Modbus service."""

        async_dispatcher_send(hass, SIGNAL_STOP_ENTITY)
        # for client in hub_collect.values():
        #     await client.async_close()

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, async_stop_climate_core)

    async def async_stop_hub(service: ServiceCall) -> None:
        """Stop Modbus hub."""
        async_dispatcher_send(hass, SIGNAL_STOP_ENTITY)
        hub = hub_collect[service.data[ATTR_HUB]]
        await hub.async_close()

    async def async_restart_hub(service: ServiceCall) -> None:
        """Restart Modbus hub."""
        async_dispatcher_send(hass, SIGNAL_START_ENTITY)
        hub = hub_collect[service.data[ATTR_HUB]]
        await hub.async_restart()

    for x_service in (
        (SERVICE_STOP, async_stop_hub),
        (SERVICE_RESTART, async_restart_hub),
    ):
        hass.services.async_register(
            DOMAIN,
            x_service[0],
            x_service[1],
            schema=vol.Schema({vol.Required(ATTR_HUB): cv.string}),
        )
    return True

class DevicesHub(Entity):
    """Thread safe wrapper class for pymodbus."""

    def __init__(self, hass: HomeAssistant, client_config: dict[str, Any]) -> None:
        """Initialize the Modbus hub."""
        self.hass = hass
        self._sensor_map = dict()        
        self.climate_config = client_config
        self._config = client_config.get(CONF_CLIMATE)[0]
        self._config_areas = self._config.get(CONF_AREAS)
        self._config_vmc = self._config.get(CONF_DEVICES).get(CONF_VMC)
        self._config_vmc_sensors = self._config.get(CONF_DEVICES).get(CONF_VMC).get(CONF_SENSORS)
        self._config_vmc_alarms = self._config.get(CONF_DEVICES).get(CONF_VMC).get(CONF_ALARMS)
        self._config_weather = self._config.get(CONF_WEATHER)

        self._vmc_power_entity_id = self._config_vmc.get(CONF_POWER)
        self._vmc_season_config = self._config_vmc.get(CONF_SEASON)
        self._vmc_vent_recirculation_id = self._config_vmc.get(CONF_VENT_RECIRCULATION)
        self._vmc_t_setpoint_entity_id = self._config_vmc.get(CONF_T_SETPOINT)
        self._vmc_h_setpoint_entity_id = self._config_vmc.get(CONF_H_SETPOINT) 

        self._vmc_t_ambient = self._config_vmc_sensors.get(CONF_T_AMBIENT)
        self._vmc_h_ambient = self._config_vmc_sensors.get(CONF_H_AMBIENT)
        self._vmc_t_water = self._config_vmc_sensors.get(CONF_T_WATER)
        self._vmc_t_outdoor = self._config_vmc_sensors.get(CONF_T_OUTDOOR)
        self._vmc_power_on_night = self._config_vmc_sensors.get(CONF_POWER_ON_NIGHT)
        self._vmc_power_on_today = self._config_vmc_sensors.get(CONF_POWER_ON_TODAY)
        
        self._vmc_high_pressure = self._config_vmc_alarms.get(CONF_HIGH_PRESSURE)
        self._vmc_dew_point = self._config_vmc_alarms.get(CONF_DEW_POINT)
        self._vmc_low_water_temp = self._config_vmc_alarms.get(CONF_LOW_WATER_TEMP)
        self._vmc_high_water_temp = self._config_vmc_alarms.get(CONF_HIGH_WATER_TEMP)
        self._vmc_alarm = self._config_vmc_alarms.get(CONF_ALARM)
        self._vmc_home_windows_state = self._config_vmc_alarms.get(CONF_HOME_WINDOWS_STATE)
        
        self.hass.async_create_task( self._async_setup_entity_change( self._vmc_power_entity_id ) )
        self.hass.async_create_task( self._async_setup_entity_change( self._vmc_vent_recirculation_id ) )
        self.hass.async_create_task( self._async_setup_entity_change( self._vmc_t_setpoint_entity_id ) )
        self.hass.async_create_task( self._async_setup_entity_change( self._vmc_h_setpoint_entity_id ) )
        self.hass.async_create_task( self._async_setup_entity_change( self._vmc_season_config.get(CONF_ACTUATOR) ) )

        self.hass.async_create_task( self._async_setup_entity_change( self._vmc_t_ambient ) )
        self.hass.async_create_task( self._async_setup_entity_change( self._vmc_h_ambient ) )
        self.hass.async_create_task( self._async_setup_entity_change( self._vmc_t_water ) )
        self.hass.async_create_task( self._async_setup_entity_change( self._vmc_t_outdoor ) )
        self.hass.async_create_task( self._async_setup_entity_change( self._vmc_power_on_night ) )
        self.hass.async_create_task( self._async_setup_entity_change( self._vmc_power_on_today ) )

        self.hass.async_create_task( self._async_setup_entity_change( self._vmc_high_pressure ) )
        self.hass.async_create_task( self._async_setup_entity_change( self._vmc_dew_point ) )
        self.hass.async_create_task( self._async_setup_entity_change( self._vmc_low_water_temp ) )
        self.hass.async_create_task( self._async_setup_entity_change( self._vmc_high_water_temp ) )
        self.hass.async_create_task( self._async_setup_entity_change( self._vmc_alarm ) )
        self.hass.async_create_task( self._async_setup_entity_change( self._vmc_home_windows_state ) )

        _LOGGER.debug( "Config: %s", str(self._config))
        # _LOGGER.debug( "Config: %s", str(self._config_weather))

    async def _async_setup_entity_change(self, entity_id):
        self.async_on_remove(
            async_track_state_change_event(
                self.hass, entity_id, self._async_entity_changed))
        _LOGGER.info( "_async_setup_entity_change '%s'.", entity_id )

    async def _async_entity_changed(self, event):
        """Handle sensor changes."""
        entity_id = event.data.get("entity_id")
        new_state = event.data.get("new_state")
        self._sensor_map[entity_id] = new_state
        # _LOGGER.debug( "_async_entity_changed '%s' status change '%s'.", str(entity_id), str(new_state) )
        # await self._async_switch_turn( "turn_off", entity_id)
        # _LOGGER.debug( "_async_entity_changed keys %s", str(self._sensor_map.keys()) )

    def _get_entity_object(self, entity_id):
        entity = self._sensor_map.get( entity_id )

        if entity is None:
            entity = self.hass.states.get(entity_id)
        
        # _LOGGER.debug( "_get_entity_object %s", str(isinstance(entity, object)) )
            
        return (entity if isinstance(entity, object) else None)

    async def _async_switch_turn(self, entity_id, state):
        self.hass.async_create_task(
            self.hass.services.async_call(
                "homeassistant", state, {"entity_id": entity_id}
            )
        )

    async def _async_number_set_value(self, entity_id, value):
        await self.hass.services.async_call(
            "number", "set_value", {"entity_id": entity_id, "value": value}
        )

    async def _async_input_select_set_value(self, entity_id, value):
        """Imposta il valore di un input_select."""
        await self.hass.services.async_call(
            "input_select", "select_option", {
                "entity_id": entity_id,
                "option": value
            }
        )

    async def async_setup(self) -> bool:
        """Set up ..."""
        return True

    def get_weather_temps(self):       
        result = []
        
        for entity_id in self._config_weather:
            # _LOGGER.debug( "entity: %s", str(entity_id))
            entity = self.hass.states.get(entity_id)
            temps = {}
            if entity is None or entity.attributes.get('minTemp') is None or entity.attributes.get('maxTemp') is None:
                continue
            
            temps['min'] = float(entity.attributes.get('minTemp'))
            temps['max'] = float(entity.attributes.get('maxTemp'))
            result.append( temps )
        
        return (result if len(result) > 0 else None)

    def calculate_heat_index(self, temperature: float, humidity: float) -> float:
        """ Calculate the Ottava Steadman apparent temperature """
        t = temperature * 9/5 + 32
        hi = 0.5 * (t + 61.0 + ((t - 68.0) * 1.2) + (humidity * 0.094))
        return ((hi - 32) * 5/9)

    def calculate_dew_point(self, temperature: float, humidity: float) -> float:
        """Calculate the dew point for the area."""

        dp: float = 0

        try:
            dp = psychrolib.GetTDewPointFromRelHum(temperature, humidity / 100) 
        except ValueError:
            _LOGGER.error( "temperature: %s humidity: %s", str(temperature), str(humidity))

        return ( dp )

    def dew_point_perception(self, dewpoint) -> (DewPointPerception) | None:
        """Dew Point <https://en.wikipedia.org/wiki/Dew_point>."""

        if dewpoint is None:
            return None
        elif dewpoint < 10:
            perception = DewPointPerception.DRY
        elif dewpoint < 13:
            perception = DewPointPerception.VERY_COMFORTABLE
        elif dewpoint < 16:
            perception = DewPointPerception.COMFORTABLE
        elif dewpoint < 18:
            perception = DewPointPerception.OK_BUT_HUMID
        elif dewpoint < 21:
            perception = DewPointPerception.SOMEWHAT_UNCOMFORTABLE
        elif dewpoint < 24:
            perception = DewPointPerception.QUITE_UNCOMFORTABLE
        elif dewpoint < 26:
            perception = DewPointPerception.EXTREMELY_UNCOMFORTABLE
        else:
            perception = DewPointPerception.SEVERELY_HIGH

        return perception
    
    def get_season_by_date(self, data=date.today()) -> dict | None:
        """
        Restituisce la label associata all'intervallo di date che contiene la data specificata,
        insieme ai giorni totali, trascorsi e rimanenti.

        Argomenti:
            data: Oggetto datetime.date che rappresenta la data da classificare.

        Restituisce:
            Dizionario contenente la label della stagione e informazioni sui giorni, o None se la data non rientra in alcun intervallo.
        """
        today = data  # Mantieni coerenza con il tipo datetime.date
        current_year = today.year
        
        for label, intervallo in SEASONS_BY_DATE.items():
            # Modifica l'anno in base all'anno corrente
            start = intervallo[0].replace(year=current_year)
            end = intervallo[1].replace(year=current_year)
            # _LOGGER.debug("get_season_by_date %s %s", str(start), str(end))
            # Se l'intervallo termina prima che inizi, spostiamo l'anno di fine al successivo
            if not is_leap_year(current_year + 1):
                end = end.replace(day=28)

            if end < start:
                end = end.replace(year=current_year + 1)
            
            # Controlla se la data corrente rientra nell'intervallo
            if start <= today <= end:
                total_days = (end - start).days + 1
                days_passed = (today - start).days
                days_remaining = (end - today).days
                return {
                    'label': label,
                    'days': total_days,
                    'passed': days_passed,
                    'remaining': days_remaining
                }
        
        return None
    
    # def get_season_from_weather(self, temperatures):
    #     """
    #     Restituisce la label della stagione in base alle previsioni della temperatura nei prossimi 5 giorni.

    #     Argomenti:
    #         temperatures: array temperature

    #     Restituisce:
    #         La label della stagione corrispondente o None.
    #     """
    #     season_scores = {season: 0 for season in CONFORT_ZONES}
        
    #     for i in range(5):
    #         temp_min_day = temperatures[i]['min']
    #         temp_max_day = temperatures[i]['max']

    #         for season, conditions in CONFORT_ZONES.items():
    #             # Verifica se la temperatura minima e massima sono all'interno dell'intervallo della stagione
    #             temp_in_range = (conditions['temp_min'] <= temp_min_day <= conditions['temp_max']) and \
    #                             (conditions['temp_min'] <= temp_max_day <= conditions['temp_max'])
                
    #             if temp_in_range:
    #                 season_scores[season] += 1
        
    #     # Seleziona la stagione con il punteggio più alto
    #     selected_season = max(season_scores, key=season_scores.get)
    #     _LOGGER.debug( "get_season_from_weather %s", str(season_scores))
    #     return selected_season

    # def get_season_from_weather_old(self):
    #     """
    #     Restituisce la label della stagione in base alle previsioni della temperatura nei prossimi 5 giorni.

    #     Restituisce:
    #         La label della stagione corrispondente o None.
    #     """
    #     temperatures = self.get_weather_temps()
    #     season_min_scores = {season: 0 for season in CONFORT_ZONES}
    #     season_max_scores = {season: 0 for season in CONFORT_ZONES}
    #     current_season = copy.copy(self.get_season_by_date())
    #     # _LOGGER.debug("get_season_from_weather %s", str(current_season)) 

    #     if temperatures is not None:
    #         for i in range(len(temperatures)):
    #             temp_min_day = temperatures[i]['min']
    #             temp_max_day = temperatures[i]['max']

    #             for season, conditions in CONFORT_ZONES.items():
    #                 confort_temp_min = conditions['temp_min'] - conditions['delta_temp']
    #                 confort_temp_max = conditions['temp_max'] - conditions['delta_temp']
    #                 confort_temp_avg = (confort_temp_min + confort_temp_max) / 2

    #                 # Verifica se la temperatura minima e/o massima rientra nell'intervallo della stagione
    #                 # temp_min_in_range = conditions['temp_min'] - conditions['delta_temp'] <= temp_min_day <= conditions['temp_max'] + conditions['delta_temp']
    #                 # temp_max_in_range = conditions['temp_min'] - conditions['delta_temp'] <= temp_max_day <= conditions['temp_max'] + conditions['delta_temp']
                    
    #                 temp_min_in_range = temp_min_day <= confort_temp_avg <= temp_max_day
                    
    #                 # Aggiungi allo score se almeno una delle temperature è nell'intervallo
    #                 if temp_min_in_range:
    #                     season_min_scores[season] += 1
    #                 # if temp_max_in_range:
    #                 #     season_max_scores[season] += 1

    #         # Seleziona la stagione con il punteggio più alto, ma solo se lo score è maggiore di zero
    #         selected_min_season = max(season_min_scores, key=season_min_scores.get) if max(season_min_scores.values()) > 0 else None
    #         # selected_max_season = max(season_max_scores, key=season_max_scores.get) if max(season_max_scores.values()) > 0 else None
    #         current_season['overridden'] = selected_min_season
    #         current_season['weather_anomaly'] = selected_min_season != current_season['label']
    #         _LOGGER.debug("get_season_from_weather - season selected '%s' season by date '%s' data %s", str(selected_min_season), str(current_season), str(season_min_scores))
        
    #     return current_season

    def get_season_from_weather(self):
        """
        Restituisce la label della stagione in base alle previsioni della temperatura nei prossimi 5 giorni.
        Restituisce:
            La label della stagione corrispondente o None.
        """
        temperatures = self.get_weather_temps()
        season_scores = {season: 0.0 for season in CONFORT_ZONES}
        current_season = copy.copy(self.get_season_by_date())

        if temperatures is not None:
            for i, temp_data in enumerate(temperatures):
                temp_min_day = temp_data['min']
                temp_max_day = temp_data['max']
                weight = 1.0 - (i * 0.1)  # Dare più peso ai giorni vicini

                for season, conditions in CONFORT_ZONES.items():
                    confort_temp_min = conditions['temp_min'] - conditions['delta_temp']
                    confort_temp_max = conditions['temp_max'] + conditions['delta_temp']
                    confort_temp_avg = (confort_temp_min + confort_temp_max) / 2

                    # Calcola la deviazione della temperatura minima e massima dalla media della stagione
                    min_deviation = abs(temp_min_day - confort_temp_avg)
                    max_deviation = abs(temp_max_day - confort_temp_avg)

                    # Valuta quanto la temperatura è vicina alla media della stagione
                    score = weight * (1 / (1 + min_deviation + max_deviation))  # Inversamente proporzionale alla deviazione

                    # Aggiungi il punteggio alla stagione corrispondente
                    season_scores[season] += score

            sorted_seasons = sorted(season_scores.items(), key=lambda item: item[1], reverse=True)
            # Seleziona la stagione con il punteggio più alto
            selected_season = max(season_scores, key=season_scores.get)
            current_season['overridden'] = selected_season
            current_season['weather_anomaly'] = selected_season != current_season['label']
            _LOGGER.debug("get_season_from_weather - Current season %s / Selected season '%s' / Scores data %s", str(current_season), str(selected_season), str(sorted_seasons))

        return current_season


    def get_confort_zone(self):
        season = self.get_season_from_weather()
        _LOGGER.debug( "get_confort_zone - %s", str(season))

        # season = self.get_season_by_date()['label']
        if season and season.get('overridden') in CONFORT_ZONES:
            return CONFORT_ZONES[season['overridden']]
        return None

    async def async_ambient_temp_hum(self, areas, sensor_map) -> Any:
        temps = []
        hums = []
        weights = []
        area_count = 0
        area_missing = 0

        # _LOGGER.debug( "sensor_map: %s", str(sensor_map) )
        for area in areas:
            # _LOGGER.debug( "area: %s %s", str(area), str( "indoor" in area) )
            if "indoor" in area and "radiant" in area and area['indoor'] and area['radiant']:
                area_count += 1
                t_entity_id = area['sensors']['temperature']
                h_entity_id = area['sensors']['humidity']
                if t_entity_id in sensor_map and h_entity_id in sensor_map:
                    temps.append( float(sensor_map[t_entity_id].state ) )
                    hums.append( float( sensor_map[h_entity_id].state ) )
                    weights.append( area['mq'] )
                else:
                    area_missing += 1
                    _LOGGER.warning( "async_ambient no data for entity %s and %s", str(t_entity_id), str(h_entity_id) )
                    # return None
        
        if round(area_count / 3, 0) >= area_missing:
            t_avg = round(weighted_average( temps, weights ), 1)
            h_avg = round(weighted_average( hums, weights ), 1)
            t_dew_point = round(self.calculate_dew_point( t_avg, h_avg ), 1)
            t_h_index = round(self.calculate_heat_index( t_avg, h_avg ), 1)
            _LOGGER.debug( "temperature: %s humidity: %s weights: %s %s %s", str(temps), str(hums), str(weights), str(t_avg), str(h_avg))

            return { 'temp' : t_avg, 'hum' : h_avg, 't_avg_dew_point' : t_dew_point, 't_avg_h_index' : t_h_index }
        else:
            _LOGGER.debug( "Totali: %s Min:%s/Missing:%s", str( area_count ), str( round(area_count / 3, 0)), str(area_missing))
            return None

    async def async_hvac_control(self, hvac_mode, sensor_map) -> Any:
        """hvac controller"""

        if hvac_mode == HVACMode.AUTO:
            _LOGGER.debug( "async_hvac_control mode: %s", str(hvac_mode))

            await self._async_vmc_mode_auto(hvac_mode, sensor_map)

    # Funzione per recuperare un'area specifica dal nome
    def _get_area_by_name(self, area_name):
        for area in self._config[CONF_AREAS]:
            if area['area'] == area_name:
                return area
        return None

    async def _async_vmc_mode_auto(self, hvac_mode, sensor_map) -> Any:
        """hvac VMC controller"""

        #
        # HVAC Mode: AUTO & Home Windows: ON (Opened) 
        #
        if hvac_mode == HVACMode.AUTO:
            season_name = ''

            season_info = self.get_season_from_weather()
            confort_zone = self.get_confort_zone()
            season_actuator_id = self._vmc_season_config.get(CONF_ACTUATOR)
            
            home_current_temp_hum = await self.async_ambient_temp_hum( self._config[CONF_AREAS], sensor_map)
            home_current_temperature = home_current_temp_hum.get('temp')
            home_current_humidity = home_current_temp_hum.get('hum')
            terrace_temperature_id = self._get_area_by_name('Terrace').get(CONF_SENSORS).get(CONF_TEMPERATURE)
            terrace_temperature = float(sensor_map.get(terrace_temperature_id).state)
            is_device_power_on = self._sensor_map.get(self._vmc_power_entity_id) and self._sensor_map.get(self._vmc_power_entity_id).state == STATE_ON


            # _LOGGER.debug( "_async_vmc_mode_auto : season %s | confort zone %s", \
            #     str(season_info), str(confort_zone))

            #
            # Season evaluation
            #
            if season_info and not season_info.get('weather_anomaly'):
                season_name = season_info.get('label')
                _LOGGER.debug( "_async_vmc_mode_auto - FALSE weather_anomaly, current season is %s, weather season %s", \
                                str(season_name), str(season_info.get('label')) )

            elif season_info and season_info.get('weather_anomaly'):
                season_name = season_info.get('overridden')
                _LOGGER.debug( "_async_vmc_mode_auto - TRUE weather_anomaly, current season is '%s', weather season '%s'", \
                                str(season_info.get('label')), str(season_name) )
                
            #
            # Processing VMC
            #
            if is_device_power_on:
                #
                # VMC temperature Setpoint by season
                # 
                set_point_temp = max( home_current_temperature, float(confort_zone['temp_max'] ) )
                if self._sensor_map.get(self._vmc_t_setpoint_entity_id) and \
                    float(self._sensor_map.get(self._vmc_t_setpoint_entity_id).state) != set_point_temp:
                    
                    await self._async_number_set_value(self._vmc_t_setpoint_entity_id, set_point_temp)
                    _LOGGER.info( "_async_vmc_mode_auto - Set %s to %s", str(self._vmc_t_setpoint_entity_id), str(set_point_temp) )

                #
                # VMC humidity Setpoint by season
                #
                if self._sensor_map.get(self._vmc_h_setpoint_entity_id) and \
                    float(self._sensor_map.get(self._vmc_h_setpoint_entity_id).state) != float(confort_zone['hum_max']):
                    
                    await self._async_number_set_value(self._vmc_h_setpoint_entity_id, float(confort_zone['hum_max']))
                    _LOGGER.info( "_async_vmc_mode_auto - Set %s to %s", str(self._vmc_h_setpoint_entity_id), str(confort_zone['hum_max']) )

            if season_name == CONF_WINTER:
                await self._async_vmc_mode_auto_season_winter( \
                    is_device_power_on, season_actuator_id, confort_zone, home_current_temperature )
            elif season_name == CONF_SPRING:
                await self._async_vmc_mode_auto_season_spring( \
                    is_device_power_on, season_actuator_id, confort_zone, home_current_temperature )
            elif season_name == CONF_SUMMER:
                await self._async_vmc_mode_auto_season_summer( \
                    is_device_power_on, season_actuator_id, confort_zone, home_current_temperature )                
            elif season_name == CONF_AUTUMN:
                await self._async_vmc_mode_auto_season_autumn( \
                    is_device_power_on, season_actuator_id, confort_zone, home_current_temperature )



            #
            # VMC Power: ON
            #
            if self._sensor_map.get(self._vmc_power_entity_id) and \
                self._sensor_map.get(self._vmc_power_entity_id).state == STATE_ON and False:

                is_device_power_on = self._sensor_map.get(self._vmc_power_entity_id).state == STATE_ON
                


                # #
                # # VMC temperature Setpoint by season
                # # 
                # if self._sensor_map.get(self._vmc_t_setpoint_entity_id) and \
                # float(self._sensor_map.get(self._vmc_t_setpoint_entity_id).state) != float(confort_zone['temp_max']):
                #     # _LOGGER.debug( "_async_vmc_mode_auto :: %s %s", str(confort_zone['temp_max']), str(self._sensor_map.get(self._vmc_t_setpoint_entity_id).state))
                #     await self._async_number_set_value(self._vmc_t_setpoint_entity_id, float(confort_zone['temp_max']))
                #     _LOGGER.info( "_async_vmc_mode_auto - Set %s to %s", str(self._vmc_t_setpoint_entity_id), str(confort_zone['temp_max']) )


                # #
                # # VMC humidity Setpoint by season
                # #
                # if self._sensor_map.get(self._vmc_h_setpoint_entity_id) and \
                # float(self._sensor_map.get(self._vmc_h_setpoint_entity_id).state) != float(confort_zone['hum_max']):
                #     # _LOGGER.debug( "_async_vmc_mode_auto :: %s %s", str(confort_zone['hum_max']), str(self._sensor_map.get(self._vmc_h_setpoint_entity_id).state))
                #     await self._async_number_set_value(self._vmc_h_setpoint_entity_id, float(confort_zone['hum_max']))
                #     _LOGGER.info( "_async_vmc_mode_auto - Set %s to %s", str(self._vmc_h_setpoint_entity_id), str(confort_zone['hum_max']) )



                if season_name == CONF_WINTER:
                    await self._async_vmc_mode_auto_season_winter( is_device_power_on, season_actuator_id, confort_zone, home_current_temperature )
                    processing = self._vmc_season_config.get(CONF_WINTER)
                    season_actuator_object = self._get_entity_object( season_actuator_id )
                    if season_actuator_object and season_actuator_object.state != processing:
                        await self._async_input_select_set_value( season_actuator_id, processing )
                        _LOGGER.info( "_async_vmc_mode_auto - Switch processing season to '%s'", processing )

                    #
                    # VMC temperature Setpoint by season
                    # 
                    set_point_temp = max( home_current_temperature, float(confort_zone['temp_max'] ) )
                    if self._sensor_map.get(self._vmc_t_setpoint_entity_id) and \
                        float(self._sensor_map.get(self._vmc_t_setpoint_entity_id).state) != set_point_temp:
                        
                        await self._async_number_set_value(self._vmc_t_setpoint_entity_id, set_point_temp)
                        _LOGGER.info( "_async_vmc_mode_auto - CONF_WINTER - Set %s to %s", str(self._vmc_t_setpoint_entity_id), str(set_point_temp) )

                    # season_actuator_object = self._get_entity_object( season_actuator_id )
                    # if season_actuator_object and season_actuator_object.state != processing:
                    #     await self._async_input_select_set_value( season_actuator_id, processing )
                    #     _LOGGER.info( "_async_vmc_mode_auto - CONF_WINTER - Switch processing season to '%s'", processing )

                elif season_name == CONF_SPRING:
                    processing = self._vmc_season_config.get(CONF_SPRING)
                    await self._async_input_select_set_value( season_actuator_id, processing )
                    
                elif season_name == CONF_SUMMER:
                    processing = self._vmc_season_config.get(CONF_SUMMER)
                    await self._async_input_select_set_value( season_actuator_id, processing )
                    
                elif season_name == CONF_AUTUMN:
                    processing = self._vmc_season_config.get(CONF_AUTUMN)
                    season_actuator_object = self._get_entity_object( season_actuator_id )
                    if season_actuator_object and season_actuator_object.state != processing:
                        await self._async_input_select_set_value( season_actuator_id, processing )
                        _LOGGER.info( "_async_vmc_mode_auto - Switch processing season to '%s'", processing )
                  
                    #
                    # VMC temperature Setpoint by season
                    # 
                    set_point_temp = max( home_current_temperature, float(confort_zone['temp_max'] ) )
                    if self._sensor_map.get(self._vmc_t_setpoint_entity_id) and \
                        float(self._sensor_map.get(self._vmc_t_setpoint_entity_id).state) != set_point_temp:
                        
                        await self._async_number_set_value(self._vmc_t_setpoint_entity_id, set_point_temp)
                        _LOGGER.info( "_async_vmc_mode_auto - CONF_AUTUMN - Set %s to %s", str(self._vmc_t_setpoint_entity_id), str(set_point_temp) )

                    # _LOGGER.info( "_async_vmc_mode_auto - Switch processing season %s %s %s", \
                    #              season_actuator_id, str(sensor_map.get(season_actuator_id)), str(self.hass.states.get(season_actuator_id).state) )

                    vent_recirculation_object = self._get_entity_object( self._vmc_vent_recirculation_id )
                    if terrace_temperature >= (max(home_current_temperature, confort_zone.get('temp_max')) - (confort_zone.get('delta_temp') * 7)):
                        if vent_recirculation_object and vent_recirculation_object.state == 'on':
                            await self._async_switch_turn( self._vmc_vent_recirculation_id, TURN_OFF )
                            _LOGGER.info( "_async_vmc_mode_auto - Set Vent Recirculation OFF" )
                    else:
                        if vent_recirculation_object and vent_recirculation_object.state == 'off':
                            await self._async_switch_turn( self._vmc_vent_recirculation_id, TURN_ON )  
                            _LOGGER.info( "_async_vmc_mode_auto - Set Vent Recirculation ON" )                      

                    # _LOGGER.debug( "_async_vmc_mode_auto - %s", str(terrace_temperature) )

    async def _async_vmc_mode_auto_season_winter(
            self,
            is_device_power_on,
            season_actuator_id,
            confort_zone,
            home_current_temperature,
        ) -> Any:
        """hvac VMC controller for season winter"""

        # Ottieni l'ora corrente
        ora_corrente = datetime.now().time()
        # Imposta l'intervallo di tempo
        inizio = ora_corrente.replace(hour=2, minute=0, second=0, microsecond=0)
        fine = ora_corrente.replace(hour=9, minute=0, second=0, microsecond=0)

        # _LOGGER.debug( "_async_vmc_mode_auto_season_winter - CONF_WINTER - processing season is '%s'", 
        #              str(self._sensor_map.get( self._vmc_season_config.get( CONF_ACTUATOR ) ) ) 
        #             # str(ora_corrente)
        # )
        
        _LOGGER.debug( "_async_vmc_mode_auto_season_winter - %s", str(ora_corrente) )

        # Verifica se l'ora corrente è tra le 2:00 e le 9:00
        if inizio <= ora_corrente < fine:
            # print("È tra le 2:00 e le 8:00.")
            if not is_device_power_on: # VMC POWER OFF
                # Change device power ON
                await self._async_switch_turn( self._vmc_power_entity_id, TURN_ON )
                _LOGGER.info( "_async_vmc_mode_auto_season_winter - Turn VMC ON" )
                return
            
            vmc_processing_object = self._sensor_map.get( self._vmc_season_config.get( CONF_ACTUATOR ) )
            if vmc_processing_object and vmc_processing_object.state != 'Off':
                await self._async_input_select_set_value( season_actuator_id, 'Off' )
                _LOGGER.info( "_async_vmc_mode_auto_season_winter - Switch processing season to '%s'", 'Off' )
            
            vent_recirculation_object = self._sensor_map.get( self._vmc_vent_recirculation_id )
            if vent_recirculation_object and vent_recirculation_object.state == 'off':
                await self._async_switch_turn( self._vmc_vent_recirculation_id, TURN_ON )
                _LOGGER.info( "_async_vmc_mode_auto_season_winter - Set Vent Recirculation ON" )
        else:
            # print("Non è tra le 2:00 e le 8:00.")
            # Ottieni l'ora corrente
            ora_corrente = datetime.now().time()
            # Imposta l'intervallo di tempo
            inizio = ora_corrente.replace(hour=12, minute=0, second=0, microsecond=0)
            fine = ora_corrente.replace(hour=15, minute=0, second=0, microsecond=0)
            if inizio <= ora_corrente < fine:
                if not is_device_power_on: # VMC POWER OFF
                    # Change device power ON
                    await self._async_switch_turn( self._vmc_power_entity_id, TURN_ON )
                    _LOGGER.info( "_async_vmc_mode_auto_season_winter - Turn VMC ON" )
                    return
                
                vmc_processing_object = self._sensor_map.get( self._vmc_season_config.get( CONF_ACTUATOR ) )
                if vmc_processing_object and vmc_processing_object.state != self._vmc_season_config.get(CONF_WINTER):
                    await self._async_input_select_set_value( season_actuator_id, self._vmc_season_config.get(CONF_WINTER) )
                    _LOGGER.info( "_async_vmc_mode_auto_season_winter - Switch processing season to '%s'", self._vmc_season_config.get( CONF_ACTUATOR ) )
                
                vent_recirculation_object = self._sensor_map.get( self._vmc_vent_recirculation_id )
                if vent_recirculation_object and vent_recirculation_object.state == 'on':
                    await self._async_switch_turn( self._vmc_vent_recirculation_id, TURN_OFF )
                    _LOGGER.info( "_async_vmc_mode_auto_season_winter - Set Vent Recirculation OFF" )               
            else:
                if is_device_power_on: # VMC POWER OFF
                    
                    # Turn off Vent Recirculation
                    vent_recirculation_object = self._sensor_map.get( self._vmc_vent_recirculation_id )
                    if vent_recirculation_object and vent_recirculation_object.state == 'on':
                        await self._async_switch_turn( self._vmc_vent_recirculation_id, TURN_OFF )
                        _LOGGER.info( "_async_vmc_mode_auto_season_winter - Set Vent Recirculation OFF" )

                    # Change device power ON
                    await self._async_switch_turn( self._vmc_power_entity_id, TURN_OFF )
                    _LOGGER.info( "_async_vmc_mode_auto_season_winter - Turn VMC OFF" )
                    return                

    async def _async_vmc_mode_auto_season_spring(
            self,
            is_device_power_on,
            season_actuator_id,
            confort_zone,
            home_current_temperature,
        ) -> Any:
        """hvac VMC controller for season spring"""
        # Ottieni l'ora corrente
        ora_corrente = datetime.now().time()

        _LOGGER.debug( "_async_vmc_mode_auto_season_spring - %s", str(ora_corrente) )

    async def _async_vmc_mode_auto_season_summer(
            self,
            is_device_power_on,
            season_actuator_id,
            confort_zone,
            home_current_temperature,
        ) -> Any:
        """hvac VMC controller for season summer"""
        # Ottieni l'ora corrente
        ora_corrente = datetime.now().time()

        _LOGGER.debug( "_async_vmc_mode_auto_season_summer - %s", str(ora_corrente) )

    async def _async_vmc_mode_auto_season_autumn(
            self,
            is_device_power_on,
            season_actuator_id,
            confort_zone,
            home_current_temperature,
        ) -> Any:
        """hvac VMC controller for season autumn"""
        # Ottieni l'ora corrente
        ora_corrente = datetime.now().time()

        _LOGGER.debug( "_async_vmc_mode_auto_season_autumn - %s", str(ora_corrente) )


        # if is_device_power_on: # VMC POWER ON

        # else: # VMC POWER OFF



        
        # processing = self._vmc_season_config.get(CONF_WINTER)
        # season_actuator_object = self._get_entity_object( season_actuator_id )
        # if season_actuator_object and season_actuator_object.state != processing:
        #     await self._async_input_select_set_value( season_actuator_id, processing )
        #     _LOGGER.info( "_async_vmc_mode_auto - Switch processing season to '%s'", processing )

        # #
        # # VMC temperature Setpoint by season
        # # 
        # set_point_temp = max( home_current_temperature, float(confort_zone['temp_max'] ) )
        # if self._sensor_map.get(self._vmc_t_setpoint_entity_id) and \
        #     float(self._sensor_map.get(self._vmc_t_setpoint_entity_id).state) != set_point_temp:
            
        #     await self._async_number_set_value(self._vmc_t_setpoint_entity_id, set_point_temp)
        #     _LOGGER.info( "_async_vmc_mode_auto - CONF_WINTER - Set %s to %s", str(self._vmc_t_setpoint_entity_id), str(set_point_temp) )

        # season_actuator_object = self._get_entity_object( season_actuator_id )
        # if season_actuator_object and season_actuator_object.state != processing:
        #     await self._async_input_select_set_value( season_actuator_id, processing )
        #     _LOGGER.info( "_async_vmc_mode_auto - CONF_WINTER - Switch processing season to '%s'", processing )


            # self._vmc_t_setpoint_entity_id = self._config_vmc.get(CONF_T_SETPOINT)
            # self._vmc_h_setpoint_entity_id = self._config_vmc.get(CONF_H_SETPOINT) 



