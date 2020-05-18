"""Support for Plugwise devices connected to a Plugwise USB-stick."""
import asyncio
import logging

import plugwise
from plugwise.exceptions import NetworkDown, PortError, StickInitError, TimeoutException

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.entity import Entity

from .const import AVAILABLE_SENSOR_ID, CONF_USB_PATH, DOMAIN, SENSORS

_LOGGER = logging.getLogger(__name__)


PLUGWISE_STICK_PLATFORMS = ["switch"]


async def async_setup(hass, config):
    """Set up the Plugwise stick platform."""
    return True


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry):
    """Establish connection with plugwise USB-stick."""
    hass.data.setdefault(DOMAIN, {})

    def discover_finished():
        nodes = stick.nodes()
        _LOGGER.debug("Discovery finished %s nodes found", str(len(nodes)))
        discovery_info = {"stick": stick}
        for platform in PLUGWISE_STICK_PLATFORMS:
            discovery_info[platform] = []
        for mac in nodes:
            for platform in PLUGWISE_STICK_PLATFORMS:
                if platform in stick.node(mac).get_categories():
                    discovery_info[platform].append(mac)
        hass.data[DOMAIN][config_entry.entry_id] = discovery_info
        for platform in PLUGWISE_STICK_PLATFORMS:
            hass.async_create_task(
                hass.config_entries.async_forward_entry_setup(config_entry, platform)
            )
        stick.auto_update()

    stick = plugwise.stick(config_entry.data[CONF_USB_PATH])
    try:
        _LOGGER.debug("Connect to USB-Stick")
        await hass.async_add_executor_job(stick.connect)
        _LOGGER.debug("Initialize USB-stick")
        await hass.async_add_executor_job(stick.initialize_stick)
        _LOGGER.debug("Discover Plugwise nodes")
        stick.scan(discover_finished)
    except PortError:
        _LOGGER.error("Connecting to Plugwise USBstick communication failed")
        raise ConfigEntryNotReady
    except StickInitError:
        _LOGGER.error("Initializing of Plugwise USBstick communication failed")
        raise ConfigEntryNotReady
    except NetworkDown:
        _LOGGER.warning("Plugwise zigbee network down")
        raise ConfigEntryNotReady
    except TimeoutException:
        _LOGGER.warning("Timeout")
        raise ConfigEntryNotReady
    return True


async def async_unload_entry(hass, config_entry):
    """Unload the Plugwise stick connection."""
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(config_entry, component)
                for component in PLUGWISE_STICK_PLATFORMS
            ]
        )
    )
    if unload_ok:
        stick = hass.data[DOMAIN][config_entry.entry_id]["stick"]
        await hass.async_add_executor_job(stick.disconnect)
        hass.data[DOMAIN].pop(config_entry.entry_id)
    return unload_ok


class PlugwiseNodeEntity(Entity):
    """Base class for a Plugwise entities."""

    def __init__(self, node, mac):
        """Initialize a Node entity."""
        self._node = node
        self._mac = mac
        self.node_callbacks = (AVAILABLE_SENSOR_ID,)

    async def async_added_to_hass(self):
        """Subscribe to updates."""
        for node_callback in self.node_callbacks:
            self._node.subscribe_callback(self.sensor_update, node_callback)

    async def async_will_remove_from_hass(self):
        """Unsubscribe to updates."""
        for node_callback in self.node_callbacks:
            self._node.unsubscribe_callback(self.sensor_update, node_callback)

    @property
    def available(self):
        """Return the availability of this entity."""
        return getattr(self._node, SENSORS[AVAILABLE_SENSOR_ID]["state"])()

    @property
    def device_info(self):
        """Return the device info."""
        return {
            "identifiers": {(DOMAIN, self._mac)},
            "name": f"{self._node.get_node_type()} ({self._mac})",
            "manufacturer": "Plugwise",
            "model": self._node.get_node_type(),
            "sw_version": f"{self._node.get_firmware_version()}",
        }

    @property
    def name(self):
        """Return the display name of this entity."""
        return f"{self._node.get_node_type()} {self._mac[-5:]}"

    def sensor_update(self, state):
        """Handle status update of Entity."""
        self.schedule_update_ha_state()

    @property
    def should_poll(self):
        """Disable polling."""
        return False

    @property
    def unique_id(self):
        """Get unique ID."""
        return f"{self._mac}-{self._node.get_node_type()}"
