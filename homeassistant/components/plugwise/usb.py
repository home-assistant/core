"""Support for Plugwise devices connected to a Plugwise USB-stick."""
import asyncio
import logging

import plugwise
from plugwise.exceptions import (
    CirclePlusError,
    NetworkDown,
    PortError,
    StickInitError,
    TimeoutException,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_STATE, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.entity import Entity

from .const import (
    AVAILABLE_SENSOR_ID,
    CONF_USB_PATH,
    DOMAIN,
    PLATFORMS_USB,
    PW_TYPE,
    STICK,
    UNDO_UPDATE_LISTENER,
    USB,
    USB_SENSORS,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry_usb(hass: HomeAssistant, config_entry: ConfigEntry):
    """Establish connection with plugwise USB-stick."""
    hass.data.setdefault(DOMAIN, {})

    def discover_finished():
        """Create entities for all discovered nodes."""
        nodes = stick.nodes()
        _LOGGER.debug(
            "Successfully discovered %s out of %s registered nodes",
            str(len(nodes)),
            str(stick.registered_nodes()),
        )
        for component in PLATFORMS_USB:
            hass.data[DOMAIN][config_entry.entry_id][component] = []
            for mac in nodes:
                if component in stick.node(mac).get_categories():
                    hass.data[DOMAIN][config_entry.entry_id][component].append(mac)
            hass.async_create_task(
                hass.config_entries.async_forward_entry_setup(config_entry, component)
            )
        stick.auto_update()
        # Enable reception of join request and automatically accept new node join requests
        stick.allow_join_requests(True, True)

    def shutdown(event):
        hass.async_add_executor_job(stick.disconnect)

    stick = plugwise.stick(config_entry.data[CONF_USB_PATH])
    hass.data[DOMAIN][config_entry.entry_id] = {PW_TYPE: USB, STICK: stick}
    try:
        _LOGGER.debug("Connect to USB-Stick")
        await hass.async_add_executor_job(stick.connect)
        _LOGGER.debug("Initialize USB-stick")
        await hass.async_add_executor_job(stick.initialize_stick)
        _LOGGER.debug("Discover Circle+ node")
        await hass.async_add_executor_job(stick.initialize_circle_plus)
    except PortError as err:
        _LOGGER.error("Connecting to Plugwise USBstick communication failed")
        raise ConfigEntryNotReady from err
    except StickInitError as err:
        _LOGGER.error("Initializing of Plugwise USBstick communication failed")
        await hass.async_add_executor_job(stick.disconnect)
        raise ConfigEntryNotReady from err
    except NetworkDown as err:
        _LOGGER.warning("Plugwise zigbee network down")
        await hass.async_add_executor_job(stick.disconnect)
        raise ConfigEntryNotReady from err
    except CirclePlusError as err:
        _LOGGER.warning("Failed to connect to Circle+ node")
        await hass.async_add_executor_job(stick.disconnect)
        raise ConfigEntryNotReady from err
    except TimeoutException as err:
        _LOGGER.warning("Timeout")
        await hass.async_add_executor_job(stick.disconnect)
        raise ConfigEntryNotReady from err
    _LOGGER.debug("Start discovery of registered nodes")
    stick.scan(discover_finished)

    # Listen when EVENT_HOMEASSISTANT_STOP is fired
    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, shutdown)

    # Listen for entry updates
    hass.data[DOMAIN][config_entry.entry_id][
        UNDO_UPDATE_LISTENER
    ] = config_entry.add_update_listener(_async_update_listener)

    return True


async def async_unload_entry_usb(hass: HomeAssistant, config_entry: ConfigEntry):
    """Unload the Plugwise stick connection."""
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(config_entry, component)
                for component in PLATFORMS_USB
            ]
        )
    )
    hass.data[DOMAIN][config_entry.entry_id][UNDO_UPDATE_LISTENER]()
    if unload_ok:
        stick = hass.data[DOMAIN][config_entry.entry_id]["stick"]
        await hass.async_add_executor_job(stick.disconnect)
        hass.data[DOMAIN].pop(config_entry.entry_id)
    return unload_ok


async def _async_update_listener(hass: HomeAssistant, config_entry: ConfigEntry):
    """Handle options update."""
    await hass.config_entries.async_reload(config_entry.entry_id)


class NodeEntity(Entity):
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
        return getattr(self._node, USB_SENSORS[AVAILABLE_SENSOR_ID][ATTR_STATE])()

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
