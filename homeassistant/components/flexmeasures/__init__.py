"""The FlexMeasures integration."""
from __future__ import annotations

import logging

from flexmeasures_client import FlexMeasuresClient
from flexmeasures_client.s2.cem import CEM
from flexmeasures_client.s2.control_types.FRBC.frbc_simple import FRBCSimple
import isodate

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

# from .api import S2FlexMeasuresClient, async_register_s2_api
from .const import DOMAIN
from .helpers import get_from_option_or_config
from .services import async_setup_services, async_unload_services
from .websockets import WebsocketAPIView

ATTR_NAME = "name"
DEFAULT_NAME = "World"

_LOGGER = logging.getLogger(__name__)


# def setup(hass: HomeAssistant, config: ConfigType) -> bool:
#     """Set up is called when Home Assistant is loading our component."""

#     # Return boolean to indicate that initialization was successful.
#     return True


# PLATFORMS: list[Platform] = [Platform.SENSOR]
PLATFORMS: list[Platform] = []


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up FlexMeasures from a config entry."""

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = entry
    hass.data[DOMAIN]["current_id"] = entry.entry_id

    config_data = dict(entry.data)
    # Registers update listener to update config entry when options are updated.
    unsub_options_update_listener = entry.add_update_listener(options_update_listener)
    # Store a reference to the unsubscribe function to cleanup if an entry is unloaded.
    config_data["unsub_options_update_listener"] = unsub_options_update_listener
    client = FlexMeasuresClient(
        host=config_data["host"],
        email=config_data["username"],
        password=config_data["password"],
        session=async_get_clientsession(hass),
    )

    cem = CEM(fm_client=client)
    frbc = FRBCSimple(
        power_sensor_id=get_from_option_or_config("power_sensor", entry),  # 1
        price_sensor_id=get_from_option_or_config(
            "consumption_price_sensor", entry
        ),  # 2
        soc_sensor_id=get_from_option_or_config("soc_sensor", entry),  # 4
        rm_discharge_sensor_id=get_from_option_or_config(
            "rm_discharge_sensor", entry
        ),  # 5
        schedule_duration=isodate.parse_duration(
            get_from_option_or_config("schedule_duration", entry)
        ),  # PT24H
    )
    cem.register_control_type(frbc)
    hass.data[DOMAIN]["fm_client"] = client

    hass.data[DOMAIN]["cem"] = cem
    hass.http.register_view(WebsocketAPIView(cem))

    await async_setup_services(hass, entry)

    return True


async def options_update_listener(hass: HomeAssistant, config_entry: ConfigEntry):
    """Handle options update."""

    _LOGGER.debug("Configuration options updated, reloading FlexMeasures integration")
    await hass.config_entries.async_reload(config_entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""

    # Remove services
    await async_unload_services(hass)

    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id, None)

    return unload_ok
