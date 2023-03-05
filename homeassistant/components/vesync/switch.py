"""Support for VeSync switches."""
import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .common import DEVICE_HELPER, VeSyncBaseEntity, VeSyncDevice
from .const import DEV_TYPE_TO_HA, DOMAIN, VS_DISCOVERY, VS_SWITCHES

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up switches."""

    @callback
    def discover(devices):
        """Add new devices to platform."""
        _setup_entities(devices, async_add_entities)

    config_entry.async_on_unload(
        async_dispatcher_connect(hass, VS_DISCOVERY.format(VS_SWITCHES), discover)
    )

    _setup_entities(hass.data[DOMAIN][VS_SWITCHES], async_add_entities)


@callback
def _setup_entities(devices, async_add_entities):
    """Check if device is online and add entity."""
    entities = []
    for dev in devices:
        if DEV_TYPE_TO_HA.get(dev.device_type) == "outlet":
            entities.append(VeSyncSwitchHA(dev))
        elif DEV_TYPE_TO_HA.get(dev.device_type) == "switch":
            entities.append(VeSyncLightSwitch(dev))
        elif DEVICE_HELPER.is_humidifier(dev.device_type):
            entities.append(VeSyncHumidifierDisplayHA(dev))
            entities.append(VeSyncHumidifierAutomaticStopHA(dev))
        else:
            _LOGGER.warning(
                "%s - Unknown device type - %s", dev.device_name, dev.device_type
            )
            continue

    async_add_entities(entities, update_before_add=True)


class VeSyncBaseSwitch(VeSyncDevice, SwitchEntity):
    """Base class for VeSync switch Device Representations."""

    def turn_on(self, **kwargs: Any) -> None:
        """Turn the device on."""
        self.device.turn_on()


class VeSyncSwitchHA(VeSyncBaseSwitch, SwitchEntity):
    """Representation of a VeSync switch."""

    def __init__(self, plug) -> None:
        """Initialize the VeSync switch device."""
        super().__init__(plug)
        self.smartplug = plug

    def update(self) -> None:
        """Update outlet details and energy usage."""
        self.smartplug.update()
        self.smartplug.update_energy()


class VeSyncLightSwitch(VeSyncBaseSwitch, SwitchEntity):
    """Handle representation of VeSync Light Switch."""

    def __init__(self, switch) -> None:
        """Initialize Light Switch device class."""
        super().__init__(switch)
        self.switch = switch


class VeSyncHumidifierSwitchEntity(VeSyncBaseEntity, SwitchEntity):
    """Representation of a switch for configuring a VeSync humidifier."""

    def __init__(self, humidifier) -> None:
        """Initialize the VeSync humidifier device."""
        super().__init__(humidifier)
        self.smarthumidifier = humidifier

    @property
    def entity_category(self):
        """Return the configuration entity category."""
        return EntityCategory.CONFIG


class VeSyncHumidifierDisplayHA(VeSyncHumidifierSwitchEntity):
    """Representation of the display on a VeSync humidifier."""

    @property
    def unique_id(self):
        """Return the ID of this display."""
        return f"{super().unique_id}-display"

    @property
    def name(self):
        """Return the name of the display."""
        return f"{super().name} display"

    @property
    def is_on(self):
        """Return True if display is on."""
        return self.device.details["display"]

    def turn_on(self, **kwargs):
        """Turn the display on."""
        self.device.turn_on_display()

    def turn_off(self, **kwargs):
        """Turn the display off."""
        self.device.turn_off_display()


class VeSyncHumidifierAutomaticStopHA(VeSyncHumidifierSwitchEntity):
    """Representation of the automatic stop toggle on a VeSync humidifier."""

    @property
    def unique_id(self):
        """Return the ID of this device."""
        return f"{super().unique_id}-automatic-stop"

    @property
    def name(self):
        """Return the name of the device."""
        return f"{super().name} automatic stop"

    @property
    def is_on(self):
        """Return True if automatic stop is on."""
        return self.device.config["automatic_stop"]

    def turn_on(self, **kwargs):
        """Turn the automatic stop on."""
        self.device.automatic_stop_on()

    def turn_off(self, **kwargs):
        """Turn the automatic stop off."""
        self.device.automatic_stop_off()
