"""Support for Fluss Devices."""

from datetime import timedelta
import logging
from typing import Any

from fluss_api.main import FlussApiClient

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import slugify

_LOGGER = logging.getLogger(__package__)
DEFAULT_NAME = "Fluss +"
UPDATE_INTERVAL = 60


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Fluss Devices."""
    api: FlussApiClient = entry.runtime_data
    api_key: str = entry.data[CONF_API_KEY]

    coordinator = FlussDataUpdateCoordinator(hass, api, api_key)
    await coordinator.async_config_entry_first_refresh()

    async_add_entities(
        FlussButton(coordinator, device)
        for device in coordinator.data["devices"]
        if isinstance(device, dict)
    )


class FlussDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Class to manage fetching Fluss device data."""

    def __init__(self, hass: HomeAssistant, api: FlussApiClient, api_key: str) -> None:
        """Initialize the coordinator."""
        self.api = api
        super().__init__(
            hass,
            _LOGGER,
            name=f"Fluss+ ({slugify(api_key[:8])})",
            update_interval=timedelta(seconds=UPDATE_INTERVAL),
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from the Fluss API."""
        try:
            return await self.api.async_get_devices()
        except Exception as err:
            raise UpdateFailed(f"Error fetching Fluss data: {err}") from err


class FlussButton(ButtonEntity):
    """Representation of a Fluss button device."""

    def __init__(self, coordinator: FlussDataUpdateCoordinator, device: dict) -> None:
        """Initialize the button."""
        if "deviceId" not in device:
            raise ValueError("Device missing required 'deviceId' attribute.")

        self.coordinator = coordinator
        self.device = device
        self._name = device.get("deviceName", "Unknown Device")
        self._attr_unique_id = f"fluss_{device['deviceId']}"

    @property
    def name(self) -> str:
        """Return name of the button."""
        return self._name

    async def async_press(self) -> None:
        """Handle the button press."""
        await self.coordinator.api.async_trigger_device(self.device["deviceId"])

    @property
    def available(self) -> bool:
        """Return if the entity is available."""
        return self.coordinator.last_update_success
