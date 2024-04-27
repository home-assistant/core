"""Base entity for Linear."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import LinearDevice, LinearUpdateCoordinator


class LinearEntity(CoordinatorEntity[LinearUpdateCoordinator]):
    """Common base for Linear entities."""

    _attr_has_entity_name = True

    def __init__(
        self,
        config_entry: ConfigEntry,
        coordinator: LinearUpdateCoordinator,
        device_id: str,
        device_name: str,
        sub_device_id: str,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)

        self._attr_unique_id = f"{device_id}-{sub_device_id}"
        self._config_entry = config_entry
        self._device_id = device_id
        self._device_name = device_name
        self._sub_device_id = sub_device_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device_id)},
            name=device_name,
            manufacturer="Linear",
            model="Garage Door Opener",
        )

    @property
    def linear_device(self) -> LinearDevice:
        """Return the Linear device."""
        return self.coordinator.data[self._device_id]

    @property
    def sub_device(self) -> dict[str, str]:
        """Return the subdevice."""
        return self.linear_device.subdevices[self._sub_device_id]
