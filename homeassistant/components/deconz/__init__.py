"""Support for deCONZ devices."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady

from .config_flow import get_master_gateway
from .const import CONF_MASTER_GATEWAY, DOMAIN, PLATFORMS
from .deconz_event import async_setup_events, async_unload_events
from .errors import AuthenticationRequired, CannotConnect
from .hub import DeconzHub, get_deconz_api
from .services import async_setup_services, async_unload_services


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Set up a deCONZ bridge for a config entry.

    Load config, group, light and sensor data for server information.
    Start websocket for push notification of state changes from deCONZ.
    """
    hass.data.setdefault(DOMAIN, {})

    if not config_entry.options:
        await async_update_master_gateway(hass, config_entry)

    try:
        api = await get_deconz_api(hass, config_entry)
    except CannotConnect as err:
        raise ConfigEntryNotReady from err
    except AuthenticationRequired as err:
        raise ConfigEntryAuthFailed from err

    if not hass.data[DOMAIN]:
        async_setup_services(hass)

    gateway = hass.data[DOMAIN][config_entry.entry_id] = DeconzHub(
        hass, config_entry, api
    )
    await gateway.async_update_device_registry()

    config_entry.add_update_listener(gateway.async_config_entry_updated)

    await async_setup_events(gateway)
    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)

    api.start()

    config_entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, gateway.shutdown)
    )

    return True


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Unload deCONZ config entry."""
    gateway: DeconzHub = hass.data[DOMAIN].pop(config_entry.entry_id)
    async_unload_events(gateway)

    if not hass.data[DOMAIN]:
        async_unload_services(hass)

    elif gateway.master:
        await async_update_master_gateway(hass, config_entry)
        new_master_gateway = next(iter(hass.data[DOMAIN].values()))
        await async_update_master_gateway(hass, new_master_gateway.config_entry)

    return await gateway.async_reset()


async def async_update_master_gateway(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> None:
    """Update master gateway boolean.

    Called by setup_entry and unload_entry.
    Makes sure there is always one master available.
    """
    try:
        master_gateway = get_master_gateway(hass)
        master = master_gateway.config_entry == config_entry
    except ValueError:
        master = True

    options = {**config_entry.options, CONF_MASTER_GATEWAY: master}

    hass.config_entries.async_update_entry(config_entry, options=options)
