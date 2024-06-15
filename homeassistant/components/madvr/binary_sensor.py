"""Binary sensor entities for the MadVR integration."""

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import MadVRCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the binary sensor entities."""
    coordinator: MadVRCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            MadvrPowerStateBinarySensor(coordinator, entry.entry_id),
            MadvrSignalStateBinarySensor(coordinator, entry.entry_id),
            MadvrHDRFlagBinarySensor(coordinator, entry.entry_id),
        ]
    )


class MadvrBaseBinarySensor(CoordinatorEntity, BinarySensorEntity):
    """Base class for MadVR binary sensors."""

    def __init__(
        self, coordinator: MadVRCoordinator, name: str, unique_id: str
    ) -> None:
        """Initialize the base binary sensor."""
        super().__init__(coordinator)
        self._attr_name = name
        self._attr_unique_id = unique_id
        self.coordinator: MadVRCoordinator = coordinator


class MadvrPowerStateBinarySensor(MadvrBaseBinarySensor):
    """Binary sensor representing the power state of the MadVR device."""

    def __init__(self, coordinator: MadVRCoordinator, entry_id: str) -> None:
        """Initialize the power state binary sensor."""
        super().__init__(
            coordinator, f"{coordinator.name} Power State", f"{entry_id}_power_state"
        )

    @property
    def is_on(self) -> bool:
        """Return true if the device is on."""
        return self.coordinator.my_api.is_on


class MadvrSignalStateBinarySensor(MadvrBaseBinarySensor):
    """Binary sensor representing the signal state of the MadVR device."""

    def __init__(self, coordinator: MadVRCoordinator, entry_id: str) -> None:
        """Initialize the signal state binary sensor."""
        super().__init__(
            coordinator, f"{coordinator.name} Signal State", f"{entry_id}_signal_state"
        )

    @property
    def is_on(self) -> bool:
        """Return true if the device is receiving a signal."""
        return self.coordinator.data.get("is_signal", False)


class MadvrHDRFlagBinarySensor(MadvrBaseBinarySensor):
    """Binary sensor representing the HDR flag state of the MadVR device."""

    def __init__(self, coordinator: MadVRCoordinator, entry_id: str) -> None:
        """Initialize the HDR flag binary sensor."""
        super().__init__(
            coordinator, f"{coordinator.name} HDR Flag", f"{entry_id}_hdr_flag"
        )

    @property
    def is_on(self) -> bool:
        """Return true if HDR is detected."""
        return self.coordinator.data.get("hdr_flag", False)
