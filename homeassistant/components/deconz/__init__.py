"""Support for deCONZ devices."""

from __future__ import annotations

from typing import cast

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_API_KEY,
    CONF_HOST,
    CONF_PORT,
    EVENT_HOMEASSISTANT_STOP,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
import homeassistant.helpers.entity_registry as er

from .config_flow import get_master_gateway
from .const import CONF_GROUP_ID_BASE, CONF_MASTER_GATEWAY, DOMAIN, PLATFORMS
from .deconz_event import async_setup_events, async_unload_events
from .errors import AuthenticationRequired, CannotConnect
from .gateway import DeconzGateway, get_deconz_session
from .services import async_setup_services, async_unload_services


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Set up a deCONZ bridge for a config entry.

    Load config, group, light and sensor data for server information.
    Start websocket for push notification of state changes from deCONZ.
    """
    hass.data.setdefault(DOMAIN, {})

    await async_update_group_unique_id(hass, config_entry)

    if not config_entry.options:
        await async_update_master_gateway(hass, config_entry)

    try:
        api = await get_deconz_session(hass, config_entry.data)
    except CannotConnect as err:
        raise ConfigEntryNotReady from err
    except AuthenticationRequired as err:
        raise ConfigEntryAuthFailed from err

    gateway = hass.data[DOMAIN][config_entry.entry_id] = DeconzGateway(
        hass, config_entry, api
    )

    config_entry.add_update_listener(gateway.async_config_entry_updated)
    hass.config_entries.async_setup_platforms(config_entry, PLATFORMS)

    await async_setup_events(gateway)
    await gateway.async_update_device_registry()

    if len(hass.data[DOMAIN]) == 1:
        async_setup_services(hass)

    api.start()

    config_entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, gateway.shutdown)
    )

    return True


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Unload deCONZ config entry."""
    gateway: DeconzGateway = hass.data[DOMAIN].pop(config_entry.entry_id)
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


async def async_update_group_unique_id(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> None:
    """Update unique ID entities based on deCONZ groups."""
    if not (group_id_base := config_entry.data.get(CONF_GROUP_ID_BASE)):
        return

    old_unique_id = cast(str, group_id_base)
    new_unique_id = cast(str, config_entry.unique_id)

    @callback
    def update_unique_id(entity_entry: er.RegistryEntry) -> dict[str, str] | None:
        """Update unique ID of entity entry."""
        if f"{old_unique_id}-" not in entity_entry.unique_id:
            return None
        return {
            "new_unique_id": entity_entry.unique_id.replace(
                old_unique_id, new_unique_id
            )
        }

    await er.async_migrate_entries(hass, config_entry.entry_id, update_unique_id)
    data = {
        CONF_API_KEY: config_entry.data[CONF_API_KEY],
        CONF_HOST: config_entry.data[CONF_HOST],
        CONF_PORT: config_entry.data[CONF_PORT],
    }
    hass.config_entries.async_update_entry(config_entry, data=data)
