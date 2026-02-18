"""Button platform for LoJack integration."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import LoJackConfigEntry
from .coordinator import LoJackVehicleData
from .const import DOMAIN, LOGGER


def _get_device_name(vehicle: LoJackVehicleData) -> str:
    """Get device name for entity naming."""
    if vehicle.year and vehicle.make and vehicle.model:
        return f"{vehicle.year} {vehicle.make} {vehicle.model}"
    if vehicle.make and vehicle.model:
        return f"{vehicle.make} {vehicle.model}"
    if vehicle.name:
        return vehicle.name
    return "Vehicle"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LoJackConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up LoJack buttons from a config entry."""
    coordinator = entry.runtime_data.coordinator

    entities: list[LoJackRefreshLocationButton] = []

    if coordinator.data:
        for vehicle in coordinator.data.values():
            device_name = _get_device_name(vehicle)
            entities.append(LoJackRefreshLocationButton(entry, vehicle, device_name))

    async_add_entities(entities)


class LoJackRefreshLocationButton(ButtonEntity):
    """Button to request a fresh location from LoJack."""

    _attr_has_entity_name = True
    _attr_translation_key = "refresh_location"

    def __init__(
        self,
        entry: LoJackConfigEntry,
        vehicle: LoJackVehicleData,
        device_name: str,
    ) -> None:
        """Initialize the button."""
        self._entry = entry
        self._device_id = vehicle.device_id

        self._attr_unique_id = f"{vehicle.device_id}_refresh_location"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, vehicle.device_id)},
            name=device_name,
            manufacturer="Spireon LoJack",
            model=f"{vehicle.make} {vehicle.model}"
            if vehicle.make and vehicle.model
            else vehicle.make,
            serial_number=vehicle.vin,
        )

    async def async_press(self) -> None:
        """Handle the button press to request fresh location."""
        runtime_data = self._entry.runtime_data
        coordinator = runtime_data.coordinator

        # Get the device object directly from the stored devices dict
        device = runtime_data.devices.get(self._device_id)
        if device is None:
            LOGGER.warning(
                "Device %s not found when requesting fresh location", self._device_id
            )
            return

        try:
            result = await device.request_fresh_location()
            if result:
                LOGGER.debug(
                    "Fresh location requested for device %s, expected at %s",
                    self._device_id,
                    result,
                )
            else:
                LOGGER.debug(
                    "Fresh location request sent for device %s",
                    self._device_id,
                )
            # Trigger a coordinator refresh to get the updated data
            await coordinator.async_request_refresh()
        except Exception:  # noqa: BLE001 - Button press should not crash
            LOGGER.exception(
                "Error requesting fresh location for device %s", self._device_id
            )
