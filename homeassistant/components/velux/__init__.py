"""Support for VELUX KLF 200 devices."""
import logging

from pyvlx import PyVLX
import voluptuous as vol

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ConfigEntryNotReady
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN, PLATFORMS

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema(
    vol.All(
        cv.deprecated(DOMAIN),
        {
            DOMAIN: vol.Schema(
                {
                    vol.Required(CONF_HOST): cv.string,
                    vol.Required(CONF_PASSWORD): cv.string,
                }
            )
        },
    ),
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up velux component via configuration.yaml."""
    if DOMAIN in config:
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN, context={"source": SOURCE_IMPORT}, data=config[DOMAIN]
            )
        )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up velux component from config entry."""

    # Setup pyvlx module and connect to KLF200
    pyvlx_args = {
        "host": entry.data[CONF_HOST],
        "password": entry.data[CONF_PASSWORD],
    }
    pyvlx: PyVLX = PyVLX(**pyvlx_args)
    try:
        await pyvlx.connect()
    except OSError as ex:
        _LOGGER.warning("Unable to connect to KLF200: %s", str(ex))
        raise ConfigEntryNotReady from ex

    # Store pyvlx in hass data
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = pyvlx

    # Load nodes (devices) and scenes from API
    await pyvlx.load_nodes()
    await pyvlx.load_scenes()

    # Setup velux components
    for component in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, component)
        )

    # Register velux services
    async def async_reboot_gateway(service_call: ServiceCall) -> None:
        await pyvlx.reboot_gateway()

    hass.services.async_register(DOMAIN, "reboot_gateway", async_reboot_gateway)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unloading the Velux platform."""
    pyvlx: PyVLX = hass.data[DOMAIN][entry.entry_id]

    # Avoid reconnection problems due to unresponsive KLF200
    await pyvlx.reboot_gateway()

    # Disconnect from KLF200
    await pyvlx.disconnect()

    # Unload velux platform components
    for component in PLATFORMS:
        await hass.config_entries.async_forward_entry_unload(entry, component)

    return True
