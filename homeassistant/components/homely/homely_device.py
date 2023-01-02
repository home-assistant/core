"""Classes to contain the entity device link provided by Homely."""
from datetime import timedelta
import logging

from homelypy.devices import Device, SingleLocation, State
from homelypy.homely import ConnectionFailedException, Homely
from requests import ConnectTimeout, HTTPError

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class HomelyHome:
    """A Homely location."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Set up data properties."""
        self.hass = hass
        self.username = entry.data["username"]
        self.password = entry.data["password"]
        self.location_id = entry.data["location_id"]
        self.location: SingleLocation = None
        self.homely: Homely = None
        self.devices: dict[str, HomelyDevice] = {}
        self.coordinator: DataUpdateCoordinator

    async def setup(self) -> None:
        """Perform initial setup."""
        self.homely = Homely(self.username, self.password)
        try:
            self.location = await self.hass.async_add_executor_job(
                self.homely.get_location, self.location_id
            )
        except (ConnectionFailedException, ConnectTimeout, HTTPError) as ex:
            raise ConfigEntryNotReady(f"Unable to connect to Homely: {ex}") from ex
        await self.update_devices()
        self.coordinator = await self.create_coordinator()

    async def update_devices(self) -> None:
        """To be called in setup for initial configuration of devices."""
        for device in self.location.devices:
            self.devices[device.id] = HomelyDevice(device.id, device.name)
            self.devices[device.id].update(device)

    async def create_coordinator(self) -> DataUpdateCoordinator:
        """Create the coordinator."""
        return PollingDataCoordinator(self.hass, self.homely, self.location)


class HomelyDevice:
    """A single Homely device."""

    def __init__(self, device_id: str, name: str) -> None:
        """Set up data properties."""
        self._device_id = device_id
        self._name = name
        self._online = False
        self._location = ""
        self._serial_number = ""
        self._model_id = ""
        self._model_name = ""
        self._states: list[State] = []
        self._device: Device

    def update(self, device: Device) -> None:
        """Update device information from Homely."""
        self._online = device.online
        self._name = device.name
        self._location = device.location
        self._serial_number = device.serial_number
        self._model_id = device.model_id
        self._model_name = device.model_name
        self._device = device

    @property
    def is_online(self) -> bool:
        """Is the device online."""
        return self._online

    @property
    def name(self) -> str:
        """Return the device name."""
        return self._name

    @property
    def location(self) -> str:
        """Return the device location string."""
        return self._location

    @property
    def homely_api_device(self) -> Device:
        """Return the homely API device."""
        return self._device

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._device_id)},
            name=f"{self.location} - {self.name}",
            manufacturer="",
            model=self._model_name,
        )


class PollingDataCoordinator(DataUpdateCoordinator):
    """Homely polling data coordinator."""

    def __init__(
        self, hass: HomeAssistant, homely: Homely, location: SingleLocation
    ) -> None:
        """Initialise homely connection."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"Homely {location.name}",
            update_interval=timedelta(minutes=5),
        )
        self.homely = homely
        self.location = location

    async def _async_update_data(self) -> None:
        self.location = await self.hass.async_add_executor_job(
            self.homely.get_location, self.location.location_id
        )
