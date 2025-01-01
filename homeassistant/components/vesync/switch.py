"""Support for VeSync switches."""

import logging
from typing import Any

from pyvesync.vesyncbasedevice import VeSyncBaseDevice

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DEV_TYPE_TO_HA, DOMAIN, VS_COORDINATOR, VS_DISCOVERY, VS_SWITCHES
from .entity import VeSyncDevice

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up switches."""

    coordinator = hass.data[DOMAIN][VS_COORDINATOR]

    @callback
    def discover(devices):
        """Add new devices to platform."""
        _setup_entities(devices, async_add_entities, coordinator)

    config_entry.async_on_unload(
        async_dispatcher_connect(hass, VS_DISCOVERY.format(VS_SWITCHES), discover)
    )

    _setup_entities(hass.data[DOMAIN][VS_SWITCHES], async_add_entities, coordinator)


@callback
def _setup_entities(
    devices: list[VeSyncBaseDevice],
    async_add_entities,
    coordinator: DataUpdateCoordinator,
):
    """Check if device is online and add entity."""
    entities: list[VeSyncBaseSwitch] = []
    for dev in devices:
        if DEV_TYPE_TO_HA.get(dev.device_type) == "outlet":
            entities.append(VeSyncSwitchHA(dev, coordinator))
        elif DEV_TYPE_TO_HA.get(dev.device_type) == "switch":
            entities.append(VeSyncLightSwitch(dev, coordinator))
        else:
            _LOGGER.warning(
                "%s - Unknown device type - %s", dev.device_name, dev.device_type
            )
            continue

    async_add_entities(entities, update_before_add=True)


class VeSyncBaseSwitch(VeSyncDevice, SwitchEntity):
    """Base class for VeSync switch Device Representations."""

    _attr_name = None

    def turn_on(self, **kwargs: Any) -> None:
        """Turn the device on."""
        self.device.turn_on()


class VeSyncSwitchHA(VeSyncBaseSwitch, SwitchEntity):
    """Representation of a VeSync switch."""

    def __init__(self, plug, coordinator: DataUpdateCoordinator) -> None:
        """Initialize the VeSync switch device."""
        super().__init__(plug, coordinator)
        self.smartplug = plug

    def update(self) -> None:
        """Update outlet details and energy usage."""
        self.smartplug.update()
        self.smartplug.update_energy()


class VeSyncLightSwitch(VeSyncBaseSwitch, SwitchEntity):
    """Handle representation of VeSync Light Switch."""

    def __init__(self, switch, coordinator: DataUpdateCoordinator) -> None:
        """Initialize Light Switch device class."""
        super().__init__(switch, coordinator)
        self.switch = switch
