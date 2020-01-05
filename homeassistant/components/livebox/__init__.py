"""Orange Livebox."""
import logging

from aiosysbus import Sysbus
import voluptuous as vol

from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_USERNAME
from homeassistant.helpers import config_validation as cv, device_registry as dr

from .bridge import BridgeData
from .const import (
    COMPONENTS,
    CONF_LAN_TRACKING,
    DATA_LIVEBOX,
    DEFAULT_HOST,
    DEFAULT_PORT,
    DEFAULT_USERNAME,
    DOMAIN,
    ID_BOX,
    SESSION_SYSBUS,
)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                # Validate as IP address and then convert back to a string.
                vol.Required(CONF_HOST, default=DEFAULT_HOST): cv.string,
                vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
                vol.Optional(CONF_USERNAME, default=DEFAULT_USERNAME): cv.string,
                vol.Required(CONF_PASSWORD): cv.string,
                vol.Required(CONF_LAN_TRACKING, default=False): cv.boolean,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass, config):
    """Load configuration for Livebox component."""

    if not hass.config_entries.async_entries(DOMAIN) and DOMAIN in config:
        livebox_config = config[DOMAIN]
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN, context={"source": SOURCE_IMPORT}, data=livebox_config
            )
        )

    return True


async def async_setup_entry(hass, config_entry):
    """Set up Livebox as config entry."""

    session = Sysbus(
        username=config_entry.data["username"],
        password=config_entry.data["password"],
        host=config_entry.data["host"],
        port=config_entry.data["port"],
    )
    perms = await session.async_get_permissions()
    if perms is not None:
        bridge = BridgeData(session, config_entry)
        hass.data[DOMAIN] = {
            ID_BOX: config_entry.data["id"],
            DATA_LIVEBOX: bridge,
            SESSION_SYSBUS: session,
        }
        infos = await bridge.async_get_infos()
        device_registry = await dr.async_get_registry(hass)
        device_registry.async_get_or_create(
            config_entry_id=config_entry.entry_id,
            identifiers={(DOMAIN, hass.data[DOMAIN][ID_BOX])},
            manufacturer=infos["Manufacturer"],
            name=infos["ProductClass"],
            model=infos["ModelName"],
            sw_version=infos["SoftwareVersion"],
        )

        for component in COMPONENTS:
            hass.async_create_task(
                hass.config_entries.async_forward_entry_setup(config_entry, component)
            )

        async def async_livebox_reboot(call):
            """Handle reboot service call."""
            await session.system.reboot()

        hass.services.async_register(DOMAIN, "reboot", async_livebox_reboot)

        return True

    return False


async def async_unload_entry(hass, config_entry):
    """Unload a config entry."""

    for component in COMPONENTS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_unload(config_entry, component)
        )

    return True
