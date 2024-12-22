"""Support for Thermostats."""
from __future__ import annotations

from statistics import mean
import time
from random import randint
from datetime import datetime, timedelta
import asyncio
import json
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.components.climate import (
    DATA_COMPONENT,
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)

from homeassistant.components.sensor import (
    CONF_STATE_CLASS,
    RestoreSensor,
    SensorEntity,
)

from homeassistant.core import HomeAssistant, callback, State
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)
from homeassistant.helpers.event import (
    async_track_state_change_event,
    async_track_time_interval,
    async_call_later,
)
from homeassistant.const import (
    ATTR_TEMPERATURE,
    CONF_NAME,
    CONF_FRIENDLY_NAME,
    CONF_SENSORS,
    CONF_UNIQUE_ID,
    CONF_TEMPERATURE_UNIT,
    PRECISION_TENTHS,
    PRECISION_WHOLE,
    UnitOfTemperature,
    EVENT_HOMEASSISTANT_START,
    Platform,
)

from . import get_hub
from .helpers import async_platform_add_entities, is_number
from .climate_core import DevicesHub
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

    ClimateSensor,
)

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 1

DEPENDENCIES = ['switch', 'sensor']

async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Read configuration and create climate controller."""
    if discovery_info is None:
        return

    entities: list[HomeClimateMaster] = []
    sensors: list[SlaveSensor] = []
    home_area = {}

    hub: DevicesHub = get_hub(hass, discovery_info[CONF_NAME])
    for climate in discovery_info[CONF_CLIMATE]:
        slave_count = 0
        slave_sensors: list[SlaveSensor] = []
        climate_entity = HomeClimateMaster(hass, hub, climate)

        for area in climate.get(CONF_AREAS):
            _LOGGER.info( '%s %s', area.get(CONF_AREA), str(area.get(CONF_INDOOR)) )
    
            if area.get(CONF_INDOOR):
                slave_sensors.append(await climate_entity.async_setup_slaves(hass, hub, slave_count, climate, area, ClimateSensor.DEW_POINT))
                slave_count += 1
                slave_sensors.append(await climate_entity.async_setup_slaves(hass, hub, slave_count, climate, area, ClimateSensor.HEAT_INDEX))
                slave_count += 1
        
        home_area[CONF_AREA] = CONF_AREA_HOME
        home_area[CONF_INDOOR] = True
        home_area[CONF_RADIANT] = False
        home_area[CONF_SENSORS] = { CONF_TEMPERATURE : ATTR_SENSOR_CURRENT_TEMP, CONF_HUMIDITY : ATTR_SENSOR_CURRENT_HUMI }
        home_area[CONF_MQ] = 85
        # home_area[CONF_SENSORS][CONF_HUMIDITY] = "internal.ambient_current_home_humidity"
        # _LOGGER.info( '%s', home_area )
        slave_sensors.append(await climate_entity.async_setup_slaves(hass, hub, slave_count, climate, home_area, ClimateSensor.CURRENT_TEMPERATURE))
        slave_count += 1
        slave_sensors.append(await climate_entity.async_setup_slaves(hass, hub, slave_count, climate, home_area, ClimateSensor.CURRENT_HUMIDITY))
        slave_count += 1
        slave_sensors.append(await climate_entity.async_setup_slaves(hass, hub, slave_count, climate, home_area, ClimateSensor.DEW_POINT))
        slave_count += 1
        slave_sensors.append(await climate_entity.async_setup_slaves(hass, hub, slave_count, climate, home_area, ClimateSensor.HEAT_INDEX))
        slave_count += 1

        sensors.extend(slave_sensors)
        entities.append(climate_entity)

    async_add_entities(entities)
    await async_platform_add_entities( hass, Platform.SENSOR, sensors, False )

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a config entry."""
    return await hass.data[DATA_COMPONENT].async_setup_entry(entry)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.data[DATA_COMPONENT].async_unload_entry(entry)

class HomeClimateMaster(ClimateEntity, RestoreEntity):
    """Representation of a Thermostat."""

    # _attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        # | ClimateEntityFeature.FAN_MODE
        # | ClimateEntityFeature.PRESET_MODE
        # | ClimateEntityFeature.SWING_MODE
        | ClimateEntityFeature.TURN_OFF
        | ClimateEntityFeature.TURN_ON
    )

    def __init__(
        self,
        hass: HomeAssistant,
        hub: DevicesHub,
        config: dict[str, Any],
    ) -> None:
        """Initialize the modbus thermostat."""
        super().__init__()
        """Initialize the thermostat."""
        self.hass = hass
        self.hub = hub
        self._config = config
        self._coordinator: DataUpdateCoordinator[list[int] | None] | None = None
        self._sensor_map = dict()
        self._attr_name = config[CONF_NAME]
        self._attr_unique_id = config.get(
            CONF_UNIQUE_ID,
            config[CONF_NAME]
        ).replace(" ", "_")

        self._precision = 0

        self._unit = config[CONF_TEMPERATURE_UNIT]

        self._confort_zone = self.hub.get_confort_zone()
        self._attr_min_temp = float( self._confort_zone['temp_min'] )
        self._attr_max_temp = float( self._confort_zone['temp_max'] )
        self._attr_min_humidity = self._confort_zone['hum_min']
        self._attr_max_humidity = self._confort_zone['hum_max']
        self._attr_current_temperature = None

        self._attr_current_humidity = None
        self._attr_current_dew_point = None
        self._attr_current_h_index = None
        
        self._attr_target_temperature = None
        self._attr_temperature_unit = (
            UnitOfTemperature.FAHRENHEIT
            if self._unit == "F"
            else UnitOfTemperature.CELSIUS
        )
        self._attr_precision = (
            PRECISION_TENTHS if self._precision >= 1 else PRECISION_WHOLE
        )

        self._attr_hvac_mode = HVACMode.AUTO
        self._attr_hvac_modes = [
            HVACMode.OFF, 
            HVACMode.HEAT, 
            HVACMode.COOL, 
            HVACMode.HEAT_COOL, 
            HVACMode.AUTO, 
            HVACMode.DRY, 
            HVACMode.FAN_ONLY
            ]

    async def async_added_to_hass(self) -> None:
        """Handle entity which will be added."""
        await super().async_added_to_hass()
        state = await self.async_get_last_state()
        if state and state.attributes.get(ATTR_TEMPERATURE):
            self._attr_target_temperature = float(state.attributes[ATTR_TEMPERATURE])

        for area in self._config.get(CONF_AREAS):
            area_name = area.get(CONF_AREA)
            sensors = area.get(CONF_SENSORS)

            self.async_on_remove(
                async_track_state_change_event(
                    self.hass, sensors.get( CONF_TEMPERATURE ), self._async_sensor_changed))
            _LOGGER.info( "On sensor '%s' change.", sensors.get( CONF_TEMPERATURE ))
            self.async_on_remove(
                async_track_state_change_event(
                    self.hass, sensors.get( CONF_HUMIDITY ), self._async_sensor_changed))
            _LOGGER.info( "On sensor '%s' change.", sensors.get( CONF_HUMIDITY ))

        self.hass.bus.async_listen_once(EVENT_HOMEASSISTANT_START, self._async_read_sensors)


    async def async_setup_slaves(
        self, 
        hass: HomeAssistant, 
        hub: DevicesHub, 
        slave_count: int, 
        entry: dict[str, Any], 
        internal_sensor: dict[str, Any],
        climate_sensor: str
    ) -> list[SlaveSensor]:
        """Add slaves as needed (1 read for multiple sensors)."""

        # Add a dataCoordinator for each sensor that have slaves
        # this ensures that idx = bit position of value in result
        # polling is done with the base class
        name = self._attr_name if self._attr_name else "climate_sensor"
        if self._coordinator is None:
            self._coordinator = DataUpdateCoordinator(
                hass,
                _LOGGER,
                name=name,
            )

        # slaves: list[SlaveSensor] = []
        # for idx in range(0, slave_count):
        #     slaves.append(SlaveSensor(self._coordinator, idx, entry))
        # return slaves
        if ClimateSensor.DEW_POINT == climate_sensor or ClimateSensor.HEAT_INDEX == climate_sensor :
            return SlaveSensor(hass, hub, self._coordinator, slave_count, entry, internal_sensor, self._attr_temperature_unit, climate_sensor)
        elif ClimateSensor.CURRENT_TEMPERATURE == climate_sensor :
            return SlaveCurrentSensor(hass, hub, self._coordinator, slave_count, entry, internal_sensor, self._attr_temperature_unit, climate_sensor)
        elif ClimateSensor.CURRENT_HUMIDITY == climate_sensor :
            return SlaveCurrentSensor(hass, hub, self._coordinator, slave_count, entry, internal_sensor, "%", climate_sensor)

    async def _async_read_sensors(self, event) -> None:
        for area in self._config[CONF_AREAS]:
            t_entity_id = area['sensors']['temperature']
            h_entity_id = area['sensors']['humidity']

            self._sensor_map[t_entity_id] = self.hass.states.get(t_entity_id)
            self._sensor_map[h_entity_id] = self.hass.states.get(h_entity_id)           

    async def _async_sensor_changed(self, event):
        """Handle sensor changes."""
        entity = event.data.get("entity_id")
        new_state = event.data.get("new_state")
        self._sensor_map[entity] = new_state

        if self._coordinator:
            self._coordinator.async_set_updated_data(self._sensor_map)

        # _LOGGER.debug( "Sensor '%s' state is changed.", str(event.data))

    # @property
    # def supported_features(self):
    #     return (
    #         ClimateEntityFeature.TARGET_TEMPERATURE |
    #         ClimateEntityFeature.FAN_MODE |
    #         ClimateEntityFeature.SWING_MODE |
    #         ClimateEntityFeature.PRESET_MODE |
    #         ClimateEntityFeature.TURN_ON_OFF  # Includi questa se supporta accensione/spegnimento
    #     )
    
    async def async_update(self, now: datetime | None = None) -> None:
        """Update Target & Current Temperature."""

        # _LOGGER.debug( "async_update: %s", str(await self.hub.async_get_weather_temps()))
        # await self.hub.async_get_weather_temps()
        self._confort_zone = self.hub.get_confort_zone()
        if self._confort_zone:
            # _LOGGER.debug( "async_update: %s", self._confort_zone )
            self._attr_min_temp = float( self._confort_zone['temp_min'] )
            self._attr_max_temp = float( self._confort_zone['temp_max'] )
            self._attr_min_humidity = self._confort_zone['hum_min']
            self._attr_max_humidity = self._confort_zone['hum_max']

        temp_hum = await self.hub.async_ambient_temp_hum( self._config[CONF_AREAS], self._sensor_map)
        if temp_hum is not None:
            self._attr_current_temperature = temp_hum['temp']
            self._attr_current_humidity = temp_hum['hum']
            self._attr_current_dew_point = temp_hum['t_avg_dew_point']
            self._attr_current_h_index = temp_hum['t_avg_h_index']

            self._sensor_map[ ATTR_SENSOR_CURRENT_TEMP ] = self._attr_current_temperature
            self._sensor_map[ ATTR_SENSOR_CURRENT_HUMI ] = self._attr_current_humidity

            if self._coordinator:
                self._coordinator.async_set_updated_data(self._sensor_map)

        await self.hub.async_hvac_control( self._attr_hvac_mode, self._sensor_map )

    def set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        # raise NotImplementedError()
        _LOGGER.debug( "Set new target temperature '%s'", str(kwargs))

    def set_humidity(self, humidity: int) -> None:
        """Set new target humidity."""
        # raise NotImplementedError()
        _LOGGER.debug( "Set new target humidity '%s'", str(humidity))
    
    def set_fan_mode(self, fan_mode: str) -> None:
        """Set new target fan mode."""
        # raise NotImplementedError()
        _LOGGER.debug( "Set new target fan mode '%s'", str(fan_mode))
    
    def set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target hvac mode."""
        # raise NotImplementedError()
        self._attr_hvac_mode = hvac_mode
        _LOGGER.debug( "Set new target hvac mode '%s'", str(hvac_mode))
    
    def set_swing_mode(self, swing_mode: str) -> None:
        """Set new target swing operation."""
        # raise NotImplementedError()
        _LOGGER.debug( "Set new target swing operation '%s'", str(swing_mode))

    def set_preset_mode(self, preset_mode: str) -> None:
        """Set new preset mode."""
        # raise NotImplementedError()
        _LOGGER.debug( "Set new preset mode '%s'", str(preset_mode))

    def turn_aux_heat_on(self) -> None:
        """Turn auxiliary heater on."""
        # raise NotImplementedError()
        _LOGGER.debug( "Turn auxiliary heater on.")

    def turn_aux_heat_off(self) -> None:
        """Turn auxiliary heater off."""
        # raise NotImplementedError()
        _LOGGER.debug( "Turn auxiliary heater off.")

    def turn_on(self):
        """Accende il dispositivo."""
        # Logica per accendere il dispositivo
        _LOGGER.debug( "turn_on.")

    def turn_off(self):
        """Spegne il dispositivo."""
        # Logica per spegnere il dispositivo
        _LOGGER.debug( "turn_off.")

    @property
    def extra_state_attributes(self):
        """Return the state attributes of the device."""

        device_power_setpoint = self.hub.get_device_setpoint()
        data: dict[str, Any] = {
            "season" : self.hub.get_season_from_weather()['overridden'],
            "weather_anomaly" : self.hub.get_season_from_weather()['weather_anomaly'],
            "min_hum" : self._attr_min_humidity,
            "max_hum" : self._attr_max_humidity
        }

        if self._attr_current_dew_point:
            data[ "current dew point" ] = self._attr_current_dew_point
        if self._attr_current_h_index:
            data[ "current heat index" ] = self._attr_current_h_index
        data[ "human perception" ] = self.hub.dew_point_perception_text(self._attr_current_dew_point)
        data[ "human perception id" ] = self.hub.dew_point_perception(self._attr_current_dew_point)

        data[ "temp setpoint power on" ] = device_power_setpoint['temp_setpoint_power_on']
        data[ "temp setpoint power off" ] = device_power_setpoint['temp_setpoint_power_off']

        # if ClimateSensor.DEW_POINT == self._climate_sensor:
        #     data[ "human perception" ] = self.dew_point_perception()

        # if self._attr_manufacturer:
        #     data[ "manufacturer" ] = self._attr_manufacturer
        # if self._attr_model:
        #     data[ "model" ] = self._attr_model
        # if len(self._attr_sensor_registers) > SensorRegIdx.GUIDE:
        #     data[ "guide" ] = self._attr_sensor_registers[SensorRegIdx.GUIDE]
        return data




class SlaveSensor(
    CoordinatorEntity[DataUpdateCoordinator[list[int] | None]],
    RestoreSensor,
    SensorEntity,
):
    """Modbus slave register sensor."""

    def __init__(
        self,
        hass: HomeAssistant, 
        hub: DevicesHub,
        coordinator: DataUpdateCoordinator[list[int] | None],
        idx: int,
        entry: dict[str, Any],
        area_entry: dict[str, Any],
        temperature_unit: str,
        climate_sensor: str,
    ) -> None:
        """Initialize the Modbus register sensor."""
        self._slave_count = idx
        self._idx = idx
        self.hass = hass
        self.hub = hub
        self._area_config = area_entry
        self._climate_sensor = climate_sensor
        self._attr_native_value = None
        self._attr_native_unit_of_measurement = temperature_unit
        self._attr_name_postfix = "na"
        self._attr_device_class = "temperature"

        if ClimateSensor.DEW_POINT == climate_sensor:
            self._attr_name_postfix = 'Dew-Point'
        elif ClimateSensor.HEAT_INDEX == climate_sensor:
            self._attr_name_postfix = 'Heat-Index'
        
        self._attr_name = f"Ambient {area_entry[CONF_AREA]} {self._attr_name_postfix}"
        self._attr_unique_id = f"ambient_{area_entry[CONF_AREA]}_{idx}_{self._attr_name_postfix}"
        # if self._attr_unique_id:
        #     self._attr_unique_id = f"{self._attr_unique_id}_{idx}"
        # self._attr_native_unit_of_measurement = entry.get(CONF_UNIT_OF_MEASUREMENT)
        # self._attr_state_class = entry.get(CONF_STATE_CLASS)
        # self._attr_device_class = entry.get(CONF_DEVICE_CLASS)
        # self._attr_available = False

        # self._attr_board = entry.get(CONF_BOARD)
        # self._attr_metadata = (BOARDS[self._attr_board])[METADATA]
        # self._attr_platform_registers = (BOARDS[self._attr_board])[Platform.SENSOR]
        # self._attr_sensor_registers = self._attr_platform_registers[internal_sensors.get(CONF_NAME)]
        # self._slave = entry.get(CONF_SLAVE, None) or entry.get(CONF_DEVICE_ADDRESS, 0)
        # self._attr_name =  internal_sensors.get(CONF_FRIENDLY_NAME) 
        # self._attr_unique_id = internal_sensors.get(
        #     CONF_UNIQUE_ID,
        #     self._attr_board + ' ' + internal_sensors.get(CONF_NAME) + ' id ' + str(self._slave)
        # ).replace(" ", "_")
        # self._attr_manufacturer = self._attr_metadata[ BoardMetadataRegIdx.MANUFACTURER ]
        self._attr_manufacturer = entry[CONF_NAME]
        # self._attr_model = self._attr_metadata[ BoardMetadataRegIdx.MODEL ]
        self._attr_state_class = "measurement"
        # self._attr_device_class = self._attr_sensor_registers[SensorRegIdx.BLOCK_DEVICE_CLASS]
        # self._attr_native_unit_of_measurement = self._attr_sensor_registers[SensorRegIdx.BLOCK_UNIT_OF_MEASURE]

        # self._min_value = None
        # self._max_value = None
        # self._zero_suppress = None
        # self._nan_value = None
        # self._offset = internal_sensors[CONF_OFFSET]

        super().__init__(coordinator)
    
    async def async_added_to_hass(self) -> None:
        # """Handle entity which will be added."""
        # if state := await self.async_get_last_state():
        #     self._attr_native_value = state.state
        # await super().async_added_to_hass()
        """Handle entity which will be added."""
        await super().async_added_to_hass()
        state = await self.async_get_last_sensor_data()
        if state:
            self._attr_native_value = state.native_value

    @property
    def extra_state_attributes(self):
        """Return the state attributes of the device."""
        data: dict[str, Any] = { 
            # CONF_SLAVE : self._idx,
            "coordinated slave id" : self._slave_count,
            "area" : self._area_config[CONF_AREA]
        }
        if ClimateSensor.DEW_POINT == self._climate_sensor:
            data[ "human perception" ] = self.hub.dew_point_perception(self._attr_native_value)

        if self._attr_manufacturer:
            data[ "manufacturer" ] = self._attr_manufacturer
        # if self._attr_model:
        #     data[ "model" ] = self._attr_model
        # if len(self._attr_sensor_registers) > SensorRegIdx.GUIDE:
        #     data[ "guide" ] = self._attr_sensor_registers[SensorRegIdx.GUIDE]
        return data

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        temperature_id = (self._area_config.get(CONF_SENSORS)).get(CONF_TEMPERATURE)
        humidity_id = (self._area_config.get(CONF_SENSORS)).get(CONF_HUMIDITY)

        _attr_board_blocks = self.coordinator.data

        if temperature_id in _attr_board_blocks and _attr_board_blocks[temperature_id] is not None:
            if not isinstance(_attr_board_blocks[temperature_id], State):
                new_temp_value = _attr_board_blocks[temperature_id]
            elif isinstance(_attr_board_blocks[temperature_id].state, (int, float)):
                new_temp_value = float(_attr_board_blocks[temperature_id].state)
            else:
                new_temp_value = None
        else:
            new_temp_value = None
        if humidity_id in _attr_board_blocks and _attr_board_blocks[humidity_id] is not None:
            if not isinstance(_attr_board_blocks[humidity_id], State):
                new_humi_value = _attr_board_blocks[humidity_id]
            else:    
                new_humi_value = float(_attr_board_blocks[humidity_id].state)
        else:
            new_humi_value = None

        if new_temp_value is not None and new_humi_value is not None:
            if ClimateSensor.DEW_POINT == self._climate_sensor:
                self._attr_native_value = round((self.hub).calculate_dew_point(new_temp_value, new_humi_value), 1)
                self._attr_available = True
            elif ClimateSensor.HEAT_INDEX == self._climate_sensor:
                self._attr_native_value = round((self.hub).calculate_heat_index(new_temp_value, new_humi_value), 1)
                # _LOGGER.debug( "calculate_heat_index '%s %s' %s.", str(new_temp_value), str(new_humi_value), str(self._attr_native_value))
                self._attr_available = True
        else:
            self._attr_available = False

        # _LOGGER.debug( "Slave sensor '%s %s'.", str(new_temp_value), str(new_humi_value))

        # if _attr_board_blocks:
        #     sensor_data = _attr_board_blocks[self._attr_sensor_registers[SensorRegIdx.BLOCK_NAME]]
        #     # sensor_value = sensor_data.registers[self._attr_sensor_registers[BLOCK_NDX]]
        #     # result = self._process_raw_value(sensor_value, self._attr_sensor_registers[SCALE], self._attr_sensor_registers[PRECISION])

        #     result = DataProcessing.unpack_data( 
        #             sensor_data.registers,
        #             self._attr_sensor_registers[SensorRegIdx.BLOCK_DATA_NDX],
        #             (self._attr_platform_registers[self._attr_sensor_registers[SensorRegIdx.BLOCK_NAME]])[BoardBlockRegIdx.BLOCK_DEF_DATATYPE],
        #             self._attr_sensor_registers[SensorRegIdx.BLOCK_DATA_SCALE],
        #             self._attr_sensor_registers[SensorRegIdx.BLOCK_DATA_PRECISION],
        #     ) 

        #     # _LOGGER.debug( "_handle_coordinator_update '%s' %s", str(sensor_data.registers), str(result), str(self._offset))
        #     _LOGGER.debug( "_handle_coordinator_update (0) '%s' slave:'%s' data:'%s' result:'%s' offset: '%s'", 
        #         self._attr_board, self._slave, str(sensor_data), str(result), str(self._offset))

        #     # self._attr_native_value = result[self._idx] if result else None
        #     self._attr_native_value = result + self._offset
        #     self._attr_available = True
        # else:
        #     self._attr_available = False
        #     self._attr_native_value = None

        super()._handle_coordinator_update()


class SlaveCurrentSensor(
    CoordinatorEntity[DataUpdateCoordinator[list[int] | None]],
    RestoreSensor,
    SensorEntity,
):
    """Modbus slave register sensor."""

    def __init__(
        self,
        hass: HomeAssistant, 
        hub: DevicesHub,
        coordinator: DataUpdateCoordinator[list[int] | None],
        idx: int,
        entry: dict[str, Any],
        area_entry: dict[str, Any],
        temperature_unit: str,
        climate_sensor: str,
    ) -> None:
        """Initialize the Modbus register sensor."""
        self._slave_count = idx
        self._idx = idx
        self.hass = hass
        self.hub = hub
        self._area_config = area_entry
        self._climate_sensor = climate_sensor
        self._attr_native_value = None
        self._attr_native_unit_of_measurement = temperature_unit
        self._attr_name_postfix = "na"

        if ClimateSensor.CURRENT_TEMPERATURE == climate_sensor:
            self._attr_name_postfix = 'Temperature'
            self._attr_device_class = "temperature"
        elif ClimateSensor.CURRENT_HUMIDITY == climate_sensor:
            self._attr_name_postfix = 'Humidity'
            self._attr_device_class = "humidity"
        
        self._attr_name = f"Ambient {area_entry[CONF_AREA]} {self._attr_name_postfix}"
        self._attr_unique_id = f"ambient_{area_entry[CONF_AREA]}_{idx}_{self._attr_name_postfix}"
        # if self._attr_unique_id:
        #     self._attr_unique_id = f"{self._attr_unique_id}_{idx}"
        # self._attr_native_unit_of_measurement = entry.get(CONF_UNIT_OF_MEASUREMENT)
        # self._attr_state_class = entry.get(CONF_STATE_CLASS)
        # self._attr_device_class = entry.get(CONF_DEVICE_CLASS)
        # self._attr_available = False

        # self._attr_board = entry.get(CONF_BOARD)
        # self._attr_metadata = (BOARDS[self._attr_board])[METADATA]
        # self._attr_platform_registers = (BOARDS[self._attr_board])[Platform.SENSOR]
        # self._attr_sensor_registers = self._attr_platform_registers[internal_sensors.get(CONF_NAME)]
        # self._slave = entry.get(CONF_SLAVE, None) or entry.get(CONF_DEVICE_ADDRESS, 0)
        # self._attr_name =  internal_sensors.get(CONF_FRIENDLY_NAME) 
        # self._attr_unique_id = internal_sensors.get(
        #     CONF_UNIQUE_ID,
        #     self._attr_board + ' ' + internal_sensors.get(CONF_NAME) + ' id ' + str(self._slave)
        # ).replace(" ", "_")
        # self._attr_manufacturer = self._attr_metadata[ BoardMetadataRegIdx.MANUFACTURER ]
        self._attr_manufacturer = entry[CONF_NAME]
        # self._attr_model = self._attr_metadata[ BoardMetadataRegIdx.MODEL ]
        self._attr_state_class = "measurement"
        # self._attr_device_class = self._attr_sensor_registers[SensorRegIdx.BLOCK_DEVICE_CLASS]
        # self._attr_native_unit_of_measurement = self._attr_sensor_registers[SensorRegIdx.BLOCK_UNIT_OF_MEASURE]

        # self._min_value = None
        # self._max_value = None
        # self._zero_suppress = None
        # self._nan_value = None
        # self._offset = internal_sensors[CONF_OFFSET]

        super().__init__(coordinator)
    
    async def async_added_to_hass(self) -> None:
        # """Handle entity which will be added."""
        # if state := await self.async_get_last_state():
        #     self._attr_native_value = state.state
        # await super().async_added_to_hass()
        """Handle entity which will be added."""
        await super().async_added_to_hass()
        state = await self.async_get_last_sensor_data()
        if state:
            self._attr_native_value = state.native_value

    @property
    def extra_state_attributes(self):
        """Return the state attributes of the device."""
        data: dict[str, Any] = { 
            # CONF_SLAVE : self._idx,
            "coordinated slave id" : self._slave_count,
            "area" : self._area_config[CONF_AREA]
        }
        if ClimateSensor.DEW_POINT == self._climate_sensor:
            data[ "human perception" ] = self.hub.dew_point_perception(self._attr_native_value)

        if self._attr_manufacturer:
            data[ "manufacturer" ] = self._attr_manufacturer
        # if self._attr_model:
        #     data[ "model" ] = self._attr_model
        # if len(self._attr_sensor_registers) > SensorRegIdx.GUIDE:
        #     data[ "guide" ] = self._attr_sensor_registers[SensorRegIdx.GUIDE]
        return data

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""

        temperature_id = (self._area_config.get(CONF_SENSORS)).get(CONF_TEMPERATURE)
        humidity_id = (self._area_config.get(CONF_SENSORS)).get(CONF_HUMIDITY)

        _attr_board_blocks = self.coordinator.data

        if temperature_id in _attr_board_blocks and _attr_board_blocks[temperature_id] is not None and is_number(_attr_board_blocks[temperature_id]):
            new_temp_value = float(_attr_board_blocks[temperature_id])
        else:
            new_temp_value = None
        if humidity_id in _attr_board_blocks and _attr_board_blocks[humidity_id] is not None and is_number(_attr_board_blocks[humidity_id]):
            new_humi_value = float(_attr_board_blocks[humidity_id])
        else:
            new_humi_value = None

        # _LOGGER.debug( "_handle_coordinator_update '%s' '%s'", str(new_temp_value), str(new_humi_value))

        if new_temp_value is not None and new_humi_value is not None:
            if ClimateSensor.CURRENT_TEMPERATURE == self._climate_sensor:
                self._attr_native_value = new_temp_value
                self._attr_available = True
            elif ClimateSensor.CURRENT_HUMIDITY == self._climate_sensor:
                self._attr_native_value = new_humi_value
                self._attr_available = True
        else:
            self._attr_available = False

        # _LOGGER.debug( "Slave sensor '%s %s'.", str(new_temp_value), str(new_humi_value))

        # if _attr_board_blocks:
        #     sensor_data = _attr_board_blocks[self._attr_sensor_registers[SensorRegIdx.BLOCK_NAME]]
        #     # sensor_value = sensor_data.registers[self._attr_sensor_registers[BLOCK_NDX]]
        #     # result = self._process_raw_value(sensor_value, self._attr_sensor_registers[SCALE], self._attr_sensor_registers[PRECISION])

        #     result = DataProcessing.unpack_data( 
        #             sensor_data.registers,
        #             self._attr_sensor_registers[SensorRegIdx.BLOCK_DATA_NDX],
        #             (self._attr_platform_registers[self._attr_sensor_registers[SensorRegIdx.BLOCK_NAME]])[BoardBlockRegIdx.BLOCK_DEF_DATATYPE],
        #             self._attr_sensor_registers[SensorRegIdx.BLOCK_DATA_SCALE],
        #             self._attr_sensor_registers[SensorRegIdx.BLOCK_DATA_PRECISION],
        #     ) 

        #     # _LOGGER.debug( "_handle_coordinator_update '%s' %s", str(sensor_data.registers), str(result), str(self._offset))
        #     _LOGGER.debug( "_handle_coordinator_update (0) '%s' slave:'%s' data:'%s' result:'%s' offset: '%s'", 
        #         self._attr_board, self._slave, str(sensor_data), str(result), str(self._offset))

        #     # self._attr_native_value = result[self._idx] if result else None
        #     self._attr_native_value = result + self._offset
        #     self._attr_available = True
        # else:
        #     self._attr_available = False
        #     self._attr_native_value = None

        super()._handle_coordinator_update()

