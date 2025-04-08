"""Support for deCONZ devices."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import CONF_MASTER_GATEWAY, DOMAIN, PLATFORMS
from .deconz_event import async_setup_events, async_unload_events
from .errors import AuthenticationRequired, CannotConnect
from .hub import DeconzHub, get_deconz_api
from .services import async_setup_services
from .util import get_master_hub

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

type DeconzConfigEntry = ConfigEntry[DeconzHub]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up services."""
    async_setup_services(hass)
    return True


async def async_setup_entry(
    hass: HomeAssistant, config_entry: DeconzConfigEntry
) -> bool:
    """Set up a deCONZ bridge for a config entry.

    Load config, group, light and sensor data for server information.
    Start websocket for push notification of state changes from deCONZ.
    """
    if not config_entry.options:
        await async_update_master_hub(hass, config_entry)

    try:
        api = await get_deconz_api(hass, config_entry)
    except CannotConnect as err:
        raise ConfigEntryNotReady from err
    except AuthenticationRequired as err:
        raise ConfigEntryAuthFailed from err

    hub = DeconzHub(hass, config_entry, api)
    config_entry.runtime_data = hub
    await hub.async_update_device_registry()

    config_entry.async_on_unload(
        config_entry.add_update_listener(hub.async_config_entry_updated)
    )

    await async_setup_events(hub)
    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)

    api.start()

    config_entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, hub.shutdown)
    )

    return True


async def async_unload_entry(
    hass: HomeAssistant, config_entry: DeconzConfigEntry
) -> bool:
    """Unload deCONZ config entry."""
    hub = config_entry.runtime_data
    async_unload_events(hub)

    other_loaded_entries: list[DeconzConfigEntry] = [
        e
        for e in hass.config_entries.async_loaded_entries(DOMAIN)
        # exclude the config entry being unloaded
        if e.entry_id != config_entry.entry_id
    ]
    if other_loaded_entries and hub.master:
        await async_update_master_hub(hass, config_entry, master=False)
        new_master_hub = next(iter(other_loaded_entries)).runtime_data
        await async_update_master_hub(hass, new_master_hub.config_entry, master=True)

    return await hub.async_reset()


async def async_update_master_hub(
    hass: HomeAssistant,
    config_entry: DeconzConfigEntry,
    *,
    master: bool | None = None,
) -> None:
    """Update master hub boolean.

    Called by setup_entry and unload_entry.
    Makes sure there is always one master available.
    """
    if master is None:
        try:
            master_hub = get_master_hub(hass)
            master = master_hub.config_entry == config_entry
        except ValueError:
            master = True

    options = {**config_entry.options, CONF_MASTER_GATEWAY: master}

    hass.config_entries.async_update_entry(config_entry, options=options)
