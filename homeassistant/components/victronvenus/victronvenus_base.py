"""Base classes for Victron Venus integration. This is used to ensure we don't create circular dependencies between the hub, device and sensor classes."""

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo


class VictronVenusHubBase:
    """Base class for the Venus OS hub."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the hub, by storing context information."""
        self._hass = hass

    @property
    def victron_devices(self) -> list["VictronVenusDeviceBase"]:
        """Gets the devices related to the hub. Note the information will be incomplete until the first full refresh."""
        return []

    @property
    def hass(self):
        """Return the Home Assistant object."""
        return self._hass


class VictronVenusDeviceBase:
    """Base class for a Venus OS device."""

    def __init__(self, hub: VictronVenusHubBase) -> None:
        """Initialize the device, by storing context information."""
        self._hub = hub

    @property
    def victron_hub(self):
        """Gets the hub (i.e. installation) the device is associated with."""
        return self._hub

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information about the device. Note the information will be incomplete until the first full refresh."""
        return DeviceInfo()

    @property
    def victron_sensors(self) -> list["VictronVenusSensorBase"]:
        """Gets the sensors related to the device. Note the information will be incomplete until the first full refresh."""
        return []


class VictronVenusSensorBase(SensorEntity):  # pylint: disable=hass-enforce-class-module
    """Base class for a Venus OS sensor."""

    def __init__(self, device: VictronVenusDeviceBase) -> None:
        """Initialize the sensor, by storing context information."""
        self._device = device
        self._registered_with_homeassistant = False

    @property
    def victron_device(self):
        """Gets the device the sensor is associated with."""
        return self._device

    @property
    def registered_with_homeassistant(self) -> bool:
        """Returns true of the sensor is registered with Home Assistant."""
        return self._registered_with_homeassistant

    def mark_registered_with_homeassistant(self):
        """Mark the sensor as registered."""
        self._registered_with_homeassistant = True


type VictronVenusConfigEntry = ConfigEntry[VictronVenusHubBase]
