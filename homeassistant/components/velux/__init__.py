"""Support for VELUX KLF 200 devices."""
import logging

from pyvlx import Node, PyVLX
import voluptuous as vol

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ConfigEntryNotReady
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue
from homeassistant.helpers.typing import ConfigType

_LOGGER = logging.getLogger(__name__)

DOMAIN = "velux"
PLATFORMS = [
    Platform.COVER,
    Platform.LIGHT,
    Platform.SCENE,
]
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
        async_create_issue(
            hass,
            DOMAIN,
            "deprecated_yaml",
            breaks_in_ha_version="2023.7.0",
            is_fixable=False,
            severity=IssueSeverity.WARNING,
            translation_key="deprecated_yaml",
        )
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

    # Try to connect to KLF200. Sometimes KLF200 becomes unresponsives and block new connections.
    # Keep trying to connect if this happen.
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

    # Register velux services
    async def async_reboot_gateway(service_call: ServiceCall) -> None:
        await pyvlx.reboot_gateway()

    hass.services.async_register(DOMAIN, "reboot_gateway", async_reboot_gateway)

    # Setup velux platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unloading the Velux platform."""
    pyvlx: PyVLX = hass.data[DOMAIN][entry.entry_id]

    # Avoid reconnection problems due to unresponsive KLF200
    await pyvlx.reboot_gateway()

    # Disconnect from KLF200
    await pyvlx.disconnect()

    # Unload velux platforms
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


class VeluxEntity(Entity):
    """Abstraction for all pyvlx node entities."""

    _attr_should_poll = False

    def __init__(self, node: Node) -> None:
        """Initialize the Velux device."""
        self.node: Node = node
        self._attr_unique_id = (
            node.serial_number if node.serial_number else str(node.node_id)
        )
        self._attr_name = node.name if node.name else f"#{node.node_id}"

    async def after_update_callback(self, node: Node) -> None:
        """Call after device was updated."""
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Store register state change callback."""
        self.node.register_device_updated_cb(self.after_update_callback)
