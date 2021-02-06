"""Support for deCONZ devices."""
import voluptuous as vol

from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import callback
from homeassistant.helpers.entity_registry import async_migrate_entries

from .config_flow import get_master_gateway
from .const import CONF_GROUP_ID_BASE, CONF_MASTER_GATEWAY, DOMAIN, LOGGER
from .gateway import DeconzGateway
from .services import async_setup_services, async_unload_services

CONFIG_SCHEMA = vol.Schema(
    {DOMAIN: vol.Schema({}, extra=vol.ALLOW_EXTRA)}, extra=vol.ALLOW_EXTRA
)


async def async_setup(hass, config):
    """Old way of setting up deCONZ integrations."""
    return True


async def async_setup_entry(hass, config_entry):
    """Set up a deCONZ bridge for a config entry.

    Load config, group, light and sensor data for server information.
    Start websocket for push notification of state changes from deCONZ.
    """
    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {}

    if not config_entry.options:
        await async_update_master_gateway(hass, config_entry)

    gateway = DeconzGateway(hass, config_entry)

    if not await gateway.async_setup():
        return False

    hass.data[DOMAIN][config_entry.unique_id] = gateway

    await gateway.async_update_device_registry()

    await async_setup_services(hass)

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, gateway.shutdown)

    return True


async def async_unload_entry(hass, config_entry):
    """Unload deCONZ config entry."""
    gateway = hass.data[DOMAIN].pop(config_entry.unique_id)

    if not hass.data[DOMAIN]:
        await async_unload_services(hass)

    elif gateway.master:
        await async_update_master_gateway(hass, config_entry)
        new_master_gateway = next(iter(hass.data[DOMAIN].values()))
        await async_update_master_gateway(hass, new_master_gateway.config_entry)

    return await gateway.async_reset()


async def async_update_master_gateway(hass, config_entry):
    """Update master gateway boolean.

    Called by setup_entry and unload_entry.
    Makes sure there is always one master available.
    """
    master = not get_master_gateway(hass)
    options = {**config_entry.options, CONF_MASTER_GATEWAY: master}

    hass.config_entries.async_update_entry(config_entry, options=options)


async def async_migrate_entry(hass, config_entry) -> bool:
    """Migrate old entry."""
    LOGGER.debug("Migrating from version %s", config_entry.version)

    # Update unique ID entities based on deCONZ groups
    if config_entry.version == 1:
        old_unique_id = config_entry.data.get(CONF_GROUP_ID_BASE)
        if old_unique_id:
            # if old_unique_id := config_entry.data.get(CONF_GROUP_ID_BASE):
            new_unique_id: str = config_entry.unique_id

        @callback
        def update_unique_id(entity_entry):
            """Update unique ID of entity entry."""
            if f"{old_unique_id}-" not in entity_entry.unique_id:
                return None
            return {
                "new_unique_id": entity_entry.unique_id.replace(
                    old_unique_id, new_unique_id
                )
            }

        if old_unique_id:
            await async_migrate_entries(hass, config_entry.entry_id, update_unique_id)

    LOGGER.info("Migration to version %s successful", config_entry.version)

    return True
