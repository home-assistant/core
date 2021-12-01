"""Support for VeSync switches."""
import logging

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .common import VeSyncBaseEntity, VeSyncDevice
from .const import DEV_TYPE_TO_HA, DOMAIN, VS_DISCOVERY, VS_DISPATCHERS, VS_SWITCHES

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up switches."""

    async def async_discover(devices):
        """Add new devices to platform."""
        _async_setup_entities(devices, async_add_entities)

    disp = async_dispatcher_connect(
        hass, VS_DISCOVERY.format(VS_SWITCHES), async_discover
    )
    hass.data[DOMAIN][VS_DISPATCHERS].append(disp)

    _async_setup_entities(hass.data[DOMAIN][VS_SWITCHES], async_add_entities)


@callback
def _async_setup_entities(devices, async_add_entities):
    """Check if device is online and add entity."""
    dev_list = []
    for dev in devices:
        if DEV_TYPE_TO_HA.get(dev.device_type) == "outlet":
            dev_list.append(VeSyncSwitchHA(dev))
        elif DEV_TYPE_TO_HA.get(dev.device_type) == "switch":
            dev_list.append(VeSyncLightSwitch(dev))
        elif DEV_TYPE_TO_HA.get(dev.device_type) == "humidifier":
            dev_list.append(VeSyncHumidifierDisplayHA(dev))
            dev_list.append(VeSyncHumidifierAutomaticStopHA(dev))
        else:
            _LOGGER.warning(
                "%s - Unknown device type - %s", dev.device_name, dev.device_type
            )
            continue

    async_add_entities(dev_list, update_before_add=True)


class VeSyncBaseSwitch(VeSyncDevice, SwitchEntity):
    """Base class for VeSync switch Device Representations."""

    def turn_on(self, **kwargs):
        """Turn the device on."""
        self.device.turn_on()


class VeSyncSwitchHA(VeSyncBaseSwitch, SwitchEntity):
    """Representation of a VeSync switch."""

    def __init__(self, plug):
        """Initialize the VeSync switch device."""
        super().__init__(plug)
        self.smartplug = plug

    @property
    def extra_state_attributes(self):
        """Return the state attributes of the device."""
        if not hasattr(self.smartplug, "weekly_energy_total"):
            return {}
        return {
            "voltage": self.smartplug.voltage,
            "weekly_energy_total": self.smartplug.weekly_energy_total,
            "monthly_energy_total": self.smartplug.monthly_energy_total,
            "yearly_energy_total": self.smartplug.yearly_energy_total,
        }

    def update(self):
        """Update outlet details and energy usage."""
        self.smartplug.update()
        self.smartplug.update_energy()


class VeSyncLightSwitch(VeSyncBaseSwitch, SwitchEntity):
    """Handle representation of VeSync Light Switch."""

    def __init__(self, switch):
        """Initialize Light Switch device class."""
        super().__init__(switch)
        self.switch = switch


class VeSyncHumidifierSwitchEntity(VeSyncBaseEntity, SwitchEntity):
    """Representation of a switch for configuring a VeSync humidifier."""

    def __init__(self, humidifier):
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
