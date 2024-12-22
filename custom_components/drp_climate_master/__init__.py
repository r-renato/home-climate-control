"""Support for Modbus."""
from __future__ import annotations

import logging
from typing import cast

import voluptuous as vol

from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv

from homeassistant.helpers.discovery import async_load_platform
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers.reload import async_setup_reload_service

from .climate_core import DevicesHub, async_climate_core_setup

from homeassistant.const import (
    CONF_NAME,
    CONF_FRIENDLY_NAME,
    CONF_SENSORS,
    CONF_UNIQUE_ID,
    CONF_TEMPERATURE_UNIT,

)

from .const import (
    CONF_DEVICES,
    CONF_CLIMATE,
    CONF_RADIANT,
    CONF_ELECTROVALVE,
    CONF_INDOOR,
    CONF_HUMIDITY,
    CONF_OUTDOOR,
    CONF_TCOLLECTOR,
    CONF_TEMPERATURE,
    CONF_AREA,
    CONF_AREAS,
    CONF_MQ,
    CONF_MAX_TEMP,
    CONF_MIN_TEMP,
    CONF_STEP,
    CONF_WATER_TEMPERATURE,
    CONF_OUTDOOR_TEMPERATURE,
    CONF_SET_POINTS,
    CONF_VMC,
    CONF_WEATHER,
    DEFAULT_HUB,
    DEFAULT_TEMP_UNIT,
    DOMAIN,

    CONF_POWER,
    CONF_T_SETPOINT,
    CONF_H_SETPOINT,
    CONF_DEW_POINT_SETPOINT,
    CONF_DELTA_DEW_POINT_SETPOINT,
    CONF_VENT_RECIRCULATION,

    CONF_SEASON,
    CONF_ACTUATOR,
    CONF_WINTER,
    CONF_SUMMER,
    CONF_AUTUMN,
    CONF_SPRING,

    CONF_COMPRESSOR_MANAGEMENT,
    CONF_DEHUMIDIFICATION_OR_COOLING,
    CONF_DEHUMIDIFICATION_ONLY,
    CONF_COOLING_ONLY,

    CONF_COOLING_MANAGEMENT,
    CONF_COMPRESSOR_ONLY,
    CONF_WATER_ONLY,
    CONF_FIRST_WATER_THEN_COMPRESSOR,

    CONF_REQUESTS,
    CONF_WATER,
    CONF_DEHUMIDIFICATION,
    CONF_HEATING,
    CONF_COOLING,

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
)

_LOGGER = logging.getLogger(__name__)

AREAS_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_AREA): cv.string,
        vol.Optional(CONF_INDOOR, default=True): vol.In([True,False,]),
        vol.Optional(CONF_RADIANT, default=True): vol.In([True,False,]),
        vol.Required(CONF_SENSORS): vol.Schema(
            {
                vol.Required(CONF_TEMPERATURE): cv.entity_id,
                vol.Required(CONF_HUMIDITY): cv.entity_id,   
            }
        ),
        vol.Optional(CONF_TCOLLECTOR): cv.entity_id,
        vol.Optional(CONF_MQ): cv.positive_int,
    }
)

VMC_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_POWER): cv.entity_id,
        vol.Required(CONF_T_SETPOINT): cv.entity_id,
        vol.Required(CONF_H_SETPOINT): cv.entity_id,
        vol.Required(CONF_DEW_POINT_SETPOINT): cv.entity_id,
        vol.Required(CONF_DELTA_DEW_POINT_SETPOINT): cv.entity_id,
        vol.Required(CONF_VENT_RECIRCULATION): cv.entity_id,

        vol.Required(CONF_SEASON): vol.Schema(
            {
                vol.Required(CONF_ACTUATOR): cv.entity_id,
                vol.Required(CONF_WINTER): cv.string,
                vol.Required(CONF_SUMMER): cv.string,
                vol.Required(CONF_AUTUMN): cv.string,
                vol.Required(CONF_SPRING): cv.string,
            }       
         ),

        vol.Required(CONF_COMPRESSOR_MANAGEMENT): vol.Schema(
            {
                vol.Required(CONF_ACTUATOR): cv.entity_id,
                vol.Required(CONF_DEHUMIDIFICATION_OR_COOLING): cv.positive_int,
                vol.Required(CONF_DEHUMIDIFICATION_ONLY): cv.positive_int,
                vol.Required(CONF_COOLING_ONLY): cv.positive_int,
            }       
         ),

        vol.Required(CONF_COOLING_MANAGEMENT): vol.Schema(
            {
                vol.Required(CONF_ACTUATOR): cv.entity_id,
                vol.Required(CONF_COMPRESSOR_ONLY): cv.positive_int,
                vol.Required(CONF_WATER_ONLY): cv.positive_int,
                vol.Required(CONF_FIRST_WATER_THEN_COMPRESSOR): cv.positive_int,
            }       
         ),

        vol.Required(CONF_REQUESTS): vol.Schema(
            {
                vol.Required(CONF_WATER): cv.entity_id,
                vol.Required(CONF_DEHUMIDIFICATION): cv.entity_id,
                vol.Required(CONF_HEATING): cv.entity_id,
                vol.Required(CONF_COOLING): cv.entity_id,                
            }       
         ),

        vol.Required(CONF_SENSORS): vol.Schema(
            {
                vol.Required(CONF_T_AMBIENT): cv.entity_id,  
                vol.Required(CONF_H_AMBIENT): cv.entity_id,                  
                vol.Required(CONF_T_WATER): cv.entity_id,   
                vol.Required(CONF_T_OUTDOOR): cv.entity_id,
                vol.Required(CONF_POWER_ON_NIGHT): cv.entity_id,
                vol.Required(CONF_POWER_ON_TODAY): cv.entity_id, 
            }
        ),
        vol.Required(CONF_ALARMS): vol.Schema(
            {
                vol.Required(CONF_HIGH_PRESSURE): cv.entity_id,
                vol.Required(CONF_DEW_POINT): cv.entity_id, 
                vol.Required(CONF_LOW_WATER_TEMP): cv.entity_id, 
                vol.Required(CONF_HIGH_WATER_TEMP): cv.entity_id, 
                vol.Required(CONF_ALARM): cv.entity_id,     
                vol.Required(CONF_HOME_WINDOWS_STATE): cv.entity_id,            
            }
        ),
    }
)

DEVICES_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_VMC): vol.All(VMC_SCHEMA)
    }
)

BASE_CLIMATE_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME): cv.string,
        vol.Optional(CONF_FRIENDLY_NAME): cv.string,
        vol.Optional(CONF_UNIQUE_ID): cv.string,

        vol.Optional(CONF_MAX_TEMP, default=35): vol.Coerce(float),
        vol.Optional(CONF_MIN_TEMP, default=5): vol.Coerce(float),
        vol.Optional(CONF_STEP, default=0.5): vol.Coerce(float),
        vol.Optional(CONF_TEMPERATURE_UNIT, default=DEFAULT_TEMP_UNIT): cv.string,

        vol.Required(CONF_AREAS): vol.All(
            cv.ensure_list, [vol.All(AREAS_SCHEMA)]
        ),
        vol.Optional(CONF_DEVICES): vol.All(DEVICES_SCHEMA),

        vol.Required(CONF_WEATHER): vol.All(cv.ensure_list, [cv.string]),

        # vol.Required(CONF_DEVICES): vol.Schema(
        #     {
        #         vol.Required(CONF_TCOLLECTOR): vol.All(
        #             cv.ensure_list, [vol.Schema({
        #                                 vol.Required(CONF_AREA): cv.string,
        #                                 vol.Optional(CONF_ELECTROVALVE): cv.entity_id,
        #                             })]
        #         ),
                
        #         # vol.Required(CONF_VMC): vol.All(
        #         #     cv.ensure_list, [vol.All(SENSORS_SCHEMA)]
        #         # ),
        #     }
        # ),
    }
)

CLIMATE_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME, default=DEFAULT_HUB): cv.string,
        vol.Required(CONF_CLIMATE): vol.All(
            cv.ensure_list, [vol.All(BASE_CLIMATE_SCHEMA)]
        ),
    }
)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.All(
            cv.ensure_list,
            # scan_interval_validator,
            # duplicate_entity_validator,
            # duplicate_modbus_validator,
            [
                vol.Any(CLIMATE_SCHEMA),
            ],
        ),
    },
    extra=vol.ALLOW_EXTRA,
)

def get_hub(hass: HomeAssistant, name: str) -> DevicesHub:
    """Return climate hub with name."""
    return cast(DevicesHub, hass.data[DOMAIN][name])


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up climate component."""
    _LOGGER.debug("DRP Climate Master async_setup")
    if DOMAIN not in config:
        return True
    return await async_climate_core_setup(
        hass,
        config,
    )

async def async_reset_platform(hass: HomeAssistant, integration_name: str) -> None:
    """Release climate resources."""
    _LOGGER.info("DRP Climate Master reloading")
    hubs = hass.data[DOMAIN]
    for name in hubs:
        await hubs[name].async_close()
