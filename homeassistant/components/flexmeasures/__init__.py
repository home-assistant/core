"""The FlexMeasures integration."""
from __future__ import annotations

from flexmeasures_client import FlexMeasuresClient
from flexmeasures_client.s2.cem import CEM
from flexmeasures_client.s2.control_types.FRBC.frbc_simple import FRBCSimple
import isodate

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import ConfigType

# from .api import S2FlexMeasuresClient, async_register_s2_api
from .const import DOMAIN
from .services import async_setup_services, async_unload_services
from .websockets import WebsocketAPIView

ATTR_NAME = "name"
DEFAULT_NAME = "World"


def setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up is called when Home Assistant is loading our component."""

    # Return boolean to indicate that initialization was successful.
    return True


# For your initial PR, limit it to 1 platform.
# PLATFORMS: list[Platform] = [Platform.LIGHT]
PLATFORMS: list[Platform] = [Platform.SWITCH]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up FlexMeasures from a config entry."""

    hass.data.setdefault(DOMAIN, {})

    # print(entry)

    config_data = dict(entry.data)
    # print(config_data)
    # # Registers update listener to update config entry when options are updated.
    # unsub_options_update_listener = entry.add_update_listener(options_update_listener)
    # # Store a reference to the unsubscribe function to cleanup if an entry is unloaded.
    # config_data["unsub_options_update_listener"] = unsub_options_update_listener
    session = async_get_clientsession(hass)
    client = FlexMeasuresClient(
        host=config_data["host"],
        email=config_data["username"],
        password=config_data["password"],
        session=session,
    )

    hass.data[DOMAIN]["config_entry_id"] = entry.entry_id
    hass.data[DOMAIN][entry.entry_id] = config_data
    hass.data[DOMAIN]["fm_client"] = client

    cem = CEM(fm_client=client)
    frbc = FRBCSimple(
        power_sensor_id=config_data.get("power_sensor"),  # 1
        price_sensor_id=config_data.get("price_sensor"),  # 2
        soc_sensor_id=config_data.get("soc_sensor"),  # 4
        rm_discharge_sensor_id=config_data.get("rm_discharge_sensor"),  # 5
        schedule_duration=isodate.parse_duration(
            config_data.get("schedule_duration")
        ),  # 24h
    )

    cem.register_control_type(frbc)

    hass.data[DOMAIN]["cem"] = cem

    await async_setup_services(hass)

    hass.http.register_view(WebsocketAPIView(cem))

    return True


async def options_update_listener(hass: HomeAssistant, config_entry: ConfigEntry):
    """Handle options update."""
    await hass.config_entries.async_reload(config_entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""

    # Remove services
    await async_unload_services(hass)

    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id, None)

    return unload_ok
