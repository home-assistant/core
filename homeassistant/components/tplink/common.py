"""Common code for tplink."""

import logging
from datetime import timedelta
from typing import Any, Callable, List

from pyHS100 import Discover, SmartBulb, SmartDevice, SmartPlug, SmartDeviceException

from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.typing import HomeAssistantType

_LOGGER = logging.getLogger(__name__)


ATTR_CONFIG = 'config'
CONF_DISCOVERY = 'discovery'
CONF_LIGHT = 'light'
CONF_SWITCH = 'switch'


class SmartDevices:
    """Hold different kinds of devices."""

    def __init__(
            self,
            lights: List[SmartDevice] = None,
            switches: List[SmartDevice] = None
    ):
        """Constructor."""
        self._lights = lights or []
        self._switches = switches or []

    @property
    def lights(self):
        """Get the lights."""
        return self._lights

    @property
    def switches(self):
        """Get the switches."""
        return self._switches

    def has_device_with_host(self, host):
        """Check if a devices exists with a specific host."""
        for device in self.lights + self.switches:
            if device.host == host:
                return True

        return False


async def async_get_discoverable_devices(hass):
    """Return if there are devices that can be discovered."""
    def discover():
        devs = Discover.discover()
        return devs
    return await hass.async_add_executor_job(discover)


async def async_discover_devices(
        hass: HomeAssistantType,
        exclude_devices: SmartDevices
) -> SmartDevices:
    """Get devices through discovery."""
    _LOGGER.debug("Discovering devices")
    devices = await async_get_discoverable_devices(hass)
    _LOGGER.info(
        "Discovered %s TP-Link smart home device(s)",
        len(devices)
    )

    lights = []
    switches = []

    for dev in devices.values():
        # If this device is configured statically, ignore dynamic setup.
        if exclude_devices.has_device_with_host(dev.host):
            continue

        if isinstance(dev, SmartPlug):
            try:
                if dev.is_dimmable:  # Dimmers act as lights
                    lights.append(dev)
                else:
                    switches.append(dev)
            except SmartDeviceException as ex:
                _LOGGER.error("Unable to connect to device %s: %s",
                              dev.host, ex)

        elif isinstance(dev, SmartBulb):
            lights.append(dev)
        else:
            _LOGGER.error("Unknown smart device type: %s", type(dev))

    return SmartDevices(lights, switches)


def async_get_static_devices(config_data) -> SmartDevices:
    """Get statically defined devices in the config."""
    _LOGGER.debug("Getting static devices")
    lights = []
    switches = []

    for type_ in [CONF_LIGHT, CONF_SWITCH]:
        for entry in config_data[type_]:
            host = entry['host']

            if type_ == CONF_LIGHT:
                lights.append(SmartBulb(host))
            elif type_ == CONF_SWITCH:
                switches.append(SmartPlug(host))

    return SmartDevices(
        lights,
        switches
    )


def async_add_entities_retry(
        hass: HomeAssistantType,
        async_add_entities: Callable[[List[Any], bool], None],
        objects: List[Any],
        callback: Callable[[Any, Callable], None],
        interval: timedelta = timedelta(seconds=60)
):
    """
    Add entities now and retry later if issues are encountered.

    If the callback throws an exception or returns false, that
    object will try again a while later.
    This is useful for devices that are not online when hass starts.
    :param hass:
    :param async_add_entities: The callback provided to a
    platform's async_setup.
    :param objects: The objects to create as entities.
    :param callback: The callback that will perform the add.
    :param interval: THe time between attempts to add.
    :return: A callback to cancel the retries.
    """
    add_objects = objects.copy()

    def dummy_cancel():
        pass

    def process_objects(*args):
        success_indexes = []

        # Process each object.
        for i, add_object in enumerate(add_objects):
            # Call the individual item callback.
            try:
                _LOGGER.debug(
                    "Attempting to add object of type %s",
                    type(add_object)
                )
                result = callback(add_object, async_add_entities)
            except SmartDeviceException as ex:
                _LOGGER.debug(
                    "Failed to add object, will try again later. Error: %s",
                    str(ex)
                )
                result = False

            if result is True or result is None:
                _LOGGER.debug("Added object.")
                success_indexes.append(i)

        # Remove successful objects from list for next run.
        for success_index in reversed(success_indexes):
            del add_objects[success_index]

        # No more objects to process. Cancel the interval.
        if not add_objects:
            _LOGGER.debug("Cancelling interval.")
            cancel_interval_callback()

    # Attempt to add immediately.
    cancel_interval_callback = dummy_cancel
    process_objects()

    # Start interval to add again and return a cancel callback.
    if add_objects:
        _LOGGER.debug("Setting interval to retry adding entities")
        cancel_interval_callback = async_track_time_interval(
            hass,
            process_objects,
            interval
        )

        return cancel_interval_callback

    # All items are processed. Return a callback that does nothing.
    _LOGGER.debug("All entities were added in the first attempt.")
    return dummy_cancel
