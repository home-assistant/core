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
import homeassistant.helpers.entity_registry as er

from .config_flow import get_master_gateway
from .const import CONF_GROUP_ID_BASE, CONF_MASTER_GATEWAY, DOMAIN
from .gateway import DeconzGateway
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

    gateway = DeconzGateway(hass, config_entry)
    if not await gateway.async_setup():
        return False

    if not hass.data[DOMAIN]:
        async_setup_services(hass)

    hass.data[DOMAIN][config_entry.entry_id] = gateway

    await gateway.async_update_device_registry()

    config_entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, gateway.shutdown)
    )

    return True


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Unload deCONZ config entry."""
    gateway = hass.data[DOMAIN].pop(config_entry.entry_id)

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
    if not isinstance(old_unique_id := config_entry.data.get(CONF_GROUP_ID_BASE), str):
        return

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
