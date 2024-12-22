import datetime
from enum import Enum
from enum import StrEnum

class ClimateSensor(str, Enum):
    """..."""

    CURRENT_TEMPERATURE = "current_temperature"
    CURRENT_HUMIDITY = "current_humidity"
    CURRENT_DEW_POINT = "current_dew_point"
    CURRENT_HEAT_INDEX = "current_heat_index"
    CURRENT_DEW_POINT_PERCEPTION = "current_dew_point_perception"
    DEW_POINT = "dew_point"
    HEAT_INDEX = "heat_index"

class DewPointPerception(StrEnum):
    """Thermal Perception."""

    DRY = "dry"                                             # mdi-emoticon-cool-outline
    VERY_COMFORTABLE = "very_comfortable"                   # mdi-emoticon-happy-outline
    COMFORTABLE = "comfortable"                             # mdi-emoticon-outline
    OK_BUT_HUMID = "ok_but_humid"                           # mdi-emoticon-neutral-outline
    SOMEWHAT_UNCOMFORTABLE = "somewhat_uncomfortable"       # mdi-emoticon-sad-outline
    QUITE_UNCOMFORTABLE = "quite_uncomfortable"             # mdi-emoticon-angry-outline
    EXTREMELY_UNCOMFORTABLE = "extremely_uncomfortable"     # mdi-emoticon-cry-outline
    SEVERELY_HIGH = "severely_high"                         # mdi-emoticon-dead-outline


WINTER = "winter"
SPRING = "spring"
SUMMER = "summer"
AUTUMN = "autumn"

# CONFORT_ZONES = {
#     WINTER: {
#         "temp_min": 19.0,
#         "temp_max": 22.0,
#         "hum_min": 40,
#         "hum_max": 60,
#         "delta_temp": 0.5,
#         "delta_hum": 1.0
#     },
#     SPRING: {
#         "temp_min": 20.0,
#         "temp_max": 24.0,
#         "hum_min": 45,
#         "hum_max": 65,
#         "delta_temp": 0.7,
#         "delta_hum": 1.2
#     },
#     SUMMER: {
#         "temp_min": 24.0,
#         "temp_max": 27.0,
#         "hum_min": 40,
#         "hum_max": 55,
#         "delta_temp": 0.7,
#         "delta_hum": 1.6
#     },
#     AUTUMN: {
#         "temp_min": 20.0,
#         "temp_max": 24.0,
#         "hum_min": 45,
#         "hum_max": 65,
#         "delta_temp": 0.6,
#         "delta_hum": 1.3
#     }
# }

CONFORT_ZONES = {
    SUMMER: {
        "temp_min": 24.0,
        "temp_max": 27.0,
        "hum_min": 40,
        "hum_max": 55,
        "delta_temp": 0.7,
        "delta_hum": 1.6,
        "dew_point": 19
    },
    AUTUMN: {
        "temp_min": 18.0,  # Leggero abbassamento rispetto alla primavera
        "temp_max": 23.7,  # Tendenza a temperature più miti verso la fine
        "hum_min": 50,     # Maggiore umidità rispetto alla primavera
        "hum_max": 70,
        "delta_temp": 0.6,
        "delta_hum": 1.5,   # Umidità più elevata e variabile,
        "dew_point": 18
    },
    WINTER: {
        "temp_min": 17.5,
        "temp_max": 21.5,
        "hum_min": 40,
        "hum_max": 60,
        "delta_temp": 0.5,
        "delta_hum": 1.0,
        "dew_point": 18
    },
    SPRING: {
        "temp_min": 19.0,  # Ridotta per i mesi iniziali
        "temp_max": 24.0,  # Più variabile
        "hum_min": 45,
        "hum_max": 65,
        "delta_temp": 0.8,  # Maggiore variabilità termica
        "delta_hum": 1.4,   # Umidità più variabile
        "dew_point": 18
    },
}

SEASONS_BY_DATE = {
  WINTER: (datetime.date(2023, 12, 1), datetime.date(2024, 2, 29)),
  SPRING: (datetime.date(2024, 3,  1), datetime.date(2024, 5, 31)),
  SUMMER: (datetime.date(2024, 6, 1), datetime.date(2024, 8, 31)),
  AUTUMN: (datetime.date(2024, 9, 1), datetime.date(2023, 11, 30)),
}

CONF_CLIMATE = "climate"
CONF_ELECTROVALVE = 'electrovalve'
CONF_INDOOR = 'indoor'
CONF_RADIANT = "radiant"
CONF_HUMIDITY = 'humidity'
CONF_OUTDOOR = 'outdoor'
CONF_TEMPERATURE = 'temperature'
CONF_WATER_TEMPERATURE = 'water_temperature'
CONF_OUTDOOR_TEMPERATURE = 'outdoor_temperature'
CONF_AREAS = "areas"
CONF_AREA = "area"
CONF_AREA_HOME = "Home Current"
CONF_MAX_TEMP = "max_temp"
CONF_MIN_TEMP = "min_temp"
CONF_STEP = "temp_step"
CONF_MQ = "mq"
CONF_WEATHER = "weather"

CONF_SET_POINTS = "set_points"

CONF_DEVICES = "devices"
CONF_TCOLLECTOR = "thermal_collector_valve_switch"
CONF_VMC = "vmc"

ATTR_HUB = "hub"
ATTR_SENSOR_CURRENT_TEMP = 'sensor.ambient_home_current_temperature'
ATTR_SENSOR_CURRENT_HUMI = 'sensor.ambient_home_current_humidity'

DEFAULT_HUB = "DRP Climate Master HUB"
DEFAULT_TEMP_UNIT = "C"

# service calls
SERVICE_STOP = "stop"
SERVICE_RESTART = "restart"

# dispatcher signals
SIGNAL_STOP_ENTITY = "drp.climate.stop"
SIGNAL_START_ENTITY = "drp.climate.start"

#Generic
VERSION = '0.1'
DOMAIN = 'drp_climate_master'
PLATFORM = 'climate'
ISSUE_URL = 'https://github.com/r-renato/home-climate-control/issues"'

## DEVICES ##
CONF_POWER = "power"
CONF_T_SETPOINT = "t_setpoint"
CONF_H_SETPOINT = "h_setpoint"
CONF_DEW_POINT_SETPOINT = "t_dew_point_setpoint"
CONF_DELTA_DEW_POINT_SETPOINT = "delta_t_dew_point_setpoint"
CONF_VENT_RECIRCULATION = "vent_recirculation"

CONF_SEASON = "season"
CONF_ACTUATOR = "actuator"
CONF_WINTER = "winter"
CONF_SUMMER = "summer"
CONF_AUTUMN = "autumn"
CONF_SPRING = "spring"

CONF_COMPRESSOR_MANAGEMENT = "compressor_management"
CONF_DEHUMIDIFICATION_OR_COOLING = "dehumidification_or_cooling"
CONF_DEHUMIDIFICATION_ONLY = "dehumidification_only"
CONF_COOLING_ONLY = "cooling_only"

CONF_COOLING_MANAGEMENT = "cooling_management"
CONF_COMPRESSOR_ONLY = "compressor_only"
CONF_WATER_ONLY = "water_only"
CONF_FIRST_WATER_THEN_COMPRESSOR = "first_water_then_compressor"

CONF_REQUESTS = "requests"
CONF_WATER = "water"
CONF_DEHUMIDIFICATION = "dehumidification"
CONF_HEATING = "heating"
CONF_COOLING = "cooling"

CONF_T_AMBIENT = "t_ambient"
CONF_H_AMBIENT = "h_ambient"
CONF_T_WATER = "t_water"
CONF_T_OUTDOOR = "t_outdoor"
CONF_POWER_ON_NIGHT = "power_on_night"
CONF_POWER_ON_TODAY = "power_on_today"

CONF_ALARMS = "alarms"
CONF_HIGH_PRESSURE = "high_pressure"
CONF_DEW_POINT = "dew_point"
CONF_LOW_WATER_TEMP = "low_water_temp"
CONF_HIGH_WATER_TEMP = "high_water_temp"
CONF_ALARM = "alarm"
CONF_HOME_WINDOWS_STATE = "home_windows_state"

TURN_ON = "turn_on"
TURN_OFF = "turn_off"