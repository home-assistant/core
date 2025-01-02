"""Support for VeSync switches."""

import logging
from typing import Any

from pyvesync.vesyncbasedevice import VeSyncBaseDevice
from pyvesync.vesyncfan import VeSyncHumid200300S

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .common import is_humidifier
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
        elif is_humidifier(dev):
            if getattr(dev, "set_auto_mode", None):
                entities.append(VeSyncHumidifierAutoOn(dev, coordinator))
            if getattr(dev, "automatic_stop_on", None):
                entities.append(VeSyncHumidifierAutomaticStop(dev, coordinator))
            if getattr(dev, "turn_on_display", None):
                entities.append(VeSyncHumidifierDisplay(dev, coordinator))
        else:
            _LOGGER.warning(
                "%s - Unknown device type - %s", dev.device_name, dev.device_type
            )
            continue

    async_add_entities(entities, update_before_add=True)


class VeSyncBaseSwitch(VeSyncDevice, SwitchEntity):
    """Base class for VeSync switch Device Representations."""

    _attr_name: str | None = None

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


class VeSyncHumidifierSwitchEntity(VeSyncBaseSwitch, SwitchEntity):
    """Representation of a switch for configuring a VeSync humidifier."""

    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self, humidifier: VeSyncHumid200300S, coordinator: DataUpdateCoordinator
    ) -> None:
        """Initialize the VeSync humidifier device."""
        super().__init__(humidifier, coordinator)
        self.smarthumidifier = humidifier


class VeSyncHumidifierDisplay(VeSyncHumidifierSwitchEntity, SwitchEntity):
    """Representation of the display for a VeSync humidifier."""

    _attr_name = "Display"

    def __init__(
        self, humidifier: VeSyncHumid200300S, coordinator: DataUpdateCoordinator
    ) -> None:
        """Initialize the VeSync outlet device."""
        super().__init__(humidifier, coordinator)
        self._attr_unique_id = f"{super().unique_id}-display"

    @property
    def is_on(self) -> bool:
        """Return True if it is locked."""
        return self.smarthumidifier.details["display"]

    def turn_on(self, **kwargs: Any) -> None:
        """Turn the lock on."""
        self.smarthumidifier.turn_on_display()

    def turn_off(self, **kwargs: Any) -> None:
        """Turn the lock off."""
        self.smarthumidifier.turn_off_display()


class VeSyncHumidifierAutomaticStop(VeSyncHumidifierSwitchEntity, SwitchEntity):
    """Representation of the automatic stop toggle on a VeSync humidifier."""

    _attr_name = "Automatic Stop"

    def __init__(
        self, humidifier: VeSyncHumid200300S, coordinator: DataUpdateCoordinator
    ) -> None:
        """Initialize the VeSync outlet device."""
        super().__init__(humidifier, coordinator)
        self._attr_unique_id = f"{super().unique_id}-automatic-stop"

    @property
    def is_on(self) -> bool:
        """Return True if automatic stop is on."""
        return self.smarthumidifier.config["automatic_stop"]

    def turn_on(self, **kwargs: Any) -> None:
        """Turn the automatic stop on."""
        self.smarthumidifier.automatic_stop_on()

    def turn_off(self, **kwargs: Any) -> None:
        """Turn the automatic stop off."""
        self.smarthumidifier.automatic_stop_off()


class VeSyncHumidifierAutoOn(VeSyncHumidifierSwitchEntity, SwitchEntity):
    """Provide switch to turn off auto mode and set manual mist level 1 on a VeSync humidifier."""

    _attr_name = "Auto Mode"

    def __init__(
        self, humidifier: VeSyncHumid200300S, coordinator: DataUpdateCoordinator
    ) -> None:
        """Initialize the VeSync outlet device."""
        super().__init__(humidifier, coordinator)
        self._attr_unique_id = f"{super().unique_id}-auto-mode"

    @property
    def is_on(self) -> bool:
        """Return True if in auto mode."""
        return self.smarthumidifier.details["mode"] == "auto"

    def turn_on(self, **kwargs: Any) -> None:
        """Turn auto mode on."""
        self.smarthumidifier.set_auto_mode()

    def turn_off(self, **kwargs: Any) -> None:
        """Turn auto off by setting manual and mist level 1."""
        self.smarthumidifier.set_manual_mode()
        self.smarthumidifier.set_mist_level(1)
