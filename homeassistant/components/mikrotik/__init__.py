"""The Mikrotik component."""
import voluptuous as vol

from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.helpers import config_validation as cv

from .const import (
    ATTR_MANUFACTURER,
    CONF_ARP_PING,
    CONF_DETECTION_TIME,
    CONF_FORCE_DHCP,
    DEFAULT_API_PORT,
    DEFAULT_DETECTION_TIME,
    DEFAULT_NAME,
    DOMAIN,
    PLATFORMS,
)
from .hub import MikrotikHub

MIKROTIK_SCHEMA = vol.All(
    vol.Schema(
        {
            vol.Required(CONF_HOST): cv.string,
            vol.Required(CONF_USERNAME): cv.string,
            vol.Required(CONF_PASSWORD): cv.string,
            vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
            vol.Optional(CONF_PORT, default=DEFAULT_API_PORT): cv.port,
            vol.Optional(CONF_VERIFY_SSL, default=False): cv.boolean,
            vol.Optional(CONF_ARP_PING, default=False): cv.boolean,
            vol.Optional(CONF_FORCE_DHCP, default=False): cv.boolean,
            vol.Optional(
                CONF_DETECTION_TIME, default=DEFAULT_DETECTION_TIME
            ): cv.time_period,
        }
    )
)


CONFIG_SCHEMA = vol.Schema(
    {DOMAIN: vol.All(cv.ensure_list, [MIKROTIK_SCHEMA])}, extra=vol.ALLOW_EXTRA
)


async def async_setup(hass, config):
    """Import the Mikrotik component from config."""

    if DOMAIN in config:
        for entry in config[DOMAIN]:
            hass.async_create_task(
                hass.config_entries.flow.async_init(
                    DOMAIN, context={"source": SOURCE_IMPORT}, data=entry
                )
            )

    return True


async def async_setup_entry(hass, config_entry):
    """Set up the Mikrotik component."""

    hub = MikrotikHub(hass, config_entry)
    if not await hub.async_setup():
        return False

    hass.data.setdefault(DOMAIN, {})[config_entry.entry_id] = hub
    device_registry = await hass.helpers.device_registry.async_get_registry()
    device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(DOMAIN, hub.serial_num)},
        manufacturer=ATTR_MANUFACTURER,
        model=hub.model,
        name=hub.hostname,
        sw_version=hub.firmware,
    )

    return True


async def async_unload_entry(hass, config_entry):
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(
        config_entry, PLATFORMS
    )

    hass.data[DOMAIN].pop(config_entry.entry_id)

    return unload_ok
