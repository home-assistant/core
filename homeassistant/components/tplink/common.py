"""Common code for tplink."""
import asyncio
from dataclasses import dataclass
from datetime import timedelta
import logging
from typing import Any, Awaitable, Callable, List

from kasa import (
    Discover,
    SmartBulb,
    SmartDevice,
    SmartDeviceException,
    SmartDimmer,
    SmartLightStrip,
    SmartPlug,
    SmartStrip,
)

from homeassistant.core import callback
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.typing import HomeAssistantType

_LOGGER = logging.getLogger(__name__)


ATTR_CONFIG = "config"
CONF_DIMMER = "dimmer"
CONF_DISCOVERY = "discovery"
CONF_LIGHT = "light"
CONF_STRIP = "strip"
CONF_SWITCH = "switch"
CONF_LIGHTSTRIP = "lightstrip"


class SmartDevices:
    """Hold different kinds of devices."""

    def __init__(
        self, lights: List[SmartDevice] = None, switches: List[SmartDevice] = None
    ):
        """Initialize device holder."""
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
    return await Discover.discover()


async def async_discover_devices(
    hass: HomeAssistantType, existing_devices: SmartDevices
) -> SmartDevices:
    """Get devices through discovery."""
    _LOGGER.debug("Discovering devices")
    devices = await async_get_discoverable_devices(hass)
    _LOGGER.info("Discovered %s TP-Link smart home device(s)", len(devices))

    lights = []
    switches = []

    for dev in devices.values():
        await dev.update()
        # If this device already exists, ignore dynamic setup.
        if existing_devices.has_device_with_host(dev.host):
            continue

        if dev.is_strip or dev.is_plug:
            switches.append(dev)
        elif dev.is_dimmer or dev.is_bulb or dev.is_lightstrip:
            lights.append(dev)
        else:
            _LOGGER.error("Unknown smart device type: %s", dev.device_type)

    return SmartDevices(lights, switches)


def get_static_devices(config_data) -> SmartDevices:
    """Get statically defined devices in the config."""
    _LOGGER.debug("Getting static devices")
    lights = []
    switches = []

    for type_ in [CONF_LIGHT, CONF_SWITCH, CONF_STRIP, CONF_DIMMER, CONF_LIGHTSTRIP]:
        for entry in config_data[type_]:
            host = entry["host"]

            if type_ == CONF_LIGHT:
                lights.append(SmartBulb(host))
            elif type_ == CONF_SWITCH:
                switches.append(SmartPlug(host))
            elif type_ == CONF_STRIP:
                switches.append(SmartStrip(host))
            elif type_ == CONF_DIMMER:
                lights.append(SmartDimmer(host))
            elif type_ == CONF_LIGHTSTRIP:
                lights.append(SmartLightStrip(host))

    return SmartDevices(lights, switches)


@dataclass
class ProcessObjectResult:
    """The result of processing an object in async_add_entities_retry."""

    object: Any
    result: bool


AsyncAddEntities = Callable[[List[Any], bool], None]


async def async_add_entities_retry(
    hass: HomeAssistantType,
    async_add_entities: AsyncAddEntities,
    objects: List[Any],
    add_entity_callback: Callable[[Any, AsyncAddEntities], Awaitable],
    interval: timedelta = timedelta(seconds=60),
) -> Callable[[], None]:
    """
    Add entities now and retry later if issues are encountered.

    If the callback throws an exception or returns false, that
    object will try again a while later.
    This is useful for devices that are not online when hass starts.
    :param hass:
    :param async_add_entities: The callback provided to a
    platform's async_setup.
    :param objects: The objects to create as entities.
    :param add_entity_callback: The callback that will perform the add.
    :param interval: THe time between attempts to add.
    :return: A callback to cancel the retries.
    """
    add_objects = list(objects)
    cancel_func1 = None

    @callback
    def cancel() -> None:
        nonlocal cancel_func1
        cancel_func1()

    async def process_object(add_object) -> ProcessObjectResult:
        nonlocal add_entity_callback
        nonlocal async_add_entities
        try:
            _LOGGER.debug("Attempting to add object of type %s", type(add_object))
            result = await add_entity_callback(add_object, async_add_entities)
            if result is not False:
                _LOGGER.debug("Object added")
                result = True

        except SmartDeviceException as ex:
            _LOGGER.debug(str(ex))
            result = False

        return ProcessObjectResult(object=add_object, result=result)

    @callback
    async def process_objects(*args) -> None:
        nonlocal add_objects

        # Process objects in parallel.
        results: List[ProcessObjectResult] = await asyncio.gather(
            *[process_object(add_object) for add_object in tuple(add_objects)],
            loop=hass.loop,
        )

        # Remove successfully processed objects from the list of objects to add.
        for result in results:
            if result.result:
                add_objects.remove(result.object)

        if add_objects:
            _LOGGER.debug("Waiting to try adding objects again.")
        else:
            cancel()

    # Schedule the retry interval.
    cancel_func1 = async_track_time_interval(hass, process_objects, interval)

    # Attempt to add the objects the first time.
    # Note: By design, this will briefly block HASS startup if devices are not
    # accessible on the network. This only occurs on startup and all subsequent
    # retries are non-blocking.
    await process_objects()

    return cancel
