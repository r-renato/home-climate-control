import logging
from datetime import timedelta, datetime

from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import async_get_platforms

_LOGGER = logging.getLogger(__name__)

def get_platform(hass, name):
    platform_list = async_get_platforms(hass, name)

    for platform in platform_list:
        if platform.domain == name:
            return platform

    return None

async def async_platform_add_entities(hass: HomeAssistant, platform: str, entities: list, discovery_info=True):
    if discovery_info is None:
        _LOGGER.warn( 'discovery_info is None' )
        return

    entity_platform = get_platform(hass, platform)

    if entity_platform:
        await entity_platform.async_add_entities(entities, discovery_info)
    else:
        _LOGGER.warn( 'Platform %s not found.', platform )

def is_number(string):
    """ Returns True is string is a number. """
    try:
        float(string)
        return True
    except ValueError:
        return False

def is_leap_year(year):
    return (year % 4 == 0) and (year % 100 != 0 or year % 400 == 0)

def weighted_average(valori, pesi):
  """
  Calcola la media ponderata di un insieme di dati con pesi specifici.

  Argomenti:
    valori: Una lista contenente i valori da ponderare.
    pesi: Una lista contenente i pesi da associare ai valori corrispondenti.

  Restituisce:
    La media ponderata calcolata.
  """

  if len(valori) != len(pesi):
    raise ValueError("Lunghezze di valori e pesi devono essere uguali")

  somma_prodotti = 0
  somma_pesi = 0

  for valore, peso in zip(valori, pesi):
    somma_prodotti += valore * peso
    somma_pesi += peso

  if somma_pesi == 0:
    raise ZeroDivisionError("Somma dei pesi pari a zero")

  media_ponderata = somma_prodotti / somma_pesi
  return media_ponderata