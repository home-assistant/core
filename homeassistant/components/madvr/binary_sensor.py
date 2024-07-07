"""Binary sensor entities for the madVR integration."""

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import MadVRCoordinator

type MadVRConfigEntry = ConfigEntry[MadVRCoordinator]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MadVRConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the binary sensor entities."""
    coordinator = entry.runtime_data
    async_add_entities(
        [
            MadvrPowerStateBinarySensor(coordinator),
            MadvrSignalStateBinarySensor(coordinator),
            MadvrHDRFlagBinarySensor(coordinator),
            MadvrHDROutgoingFlagBinarySensor(coordinator),
        ]
    )


class MadvrBaseBinarySensor(CoordinatorEntity, BinarySensorEntity):
    """Base class for madVR binary sensors."""

    _attr_has_entity_name = True
    coordinator: MadVRCoordinator

    def __init__(self, coordinator: MadVRCoordinator, name: str, key: str) -> None:
        """Initialize the base binary sensor."""
        super().__init__(coordinator)
        self._attr_name = name
        self._key = key
        self._attr_unique_id = f"{coordinator.mac}_{key}"

    @property
    def device_info(self) -> DeviceInfo | None:
        """Return the device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.mac)},
            name="madVR Envy",
            manufacturer="madVR",
            model="Envy",
        )


class MadvrPowerStateBinarySensor(MadvrBaseBinarySensor):
    """Binary sensor representing the power state of the madVR device."""

    def __init__(self, coordinator: MadVRCoordinator) -> None:
        """Initialize the power state binary sensor."""
        super().__init__(coordinator, f"{coordinator.name} Power State", "power_state")

    @property
    def is_on(self) -> bool:
        """Return true if the device is on."""
        return self.coordinator.client.is_on if self.coordinator.client else False

    @property
    def icon(self) -> str:
        """Return the icon to use in the frontend."""
        return "mdi:power" if self.is_on else "mdi:power-off"


class MadvrSignalStateBinarySensor(MadvrBaseBinarySensor):
    """Binary sensor representing the signal state of the madVR device."""

    def __init__(self, coordinator: MadVRCoordinator) -> None:
        """Initialize the signal state binary sensor."""
        super().__init__(
            coordinator, f"{coordinator.name} Signal State", "signal_state"
        )

    @property
    def is_on(self) -> bool:
        """Return true if the device is receiving a signal."""
        return bool(
            self.coordinator.data.get("is_signal", False)
            if self.coordinator.data
            else False
        )

    @property
    def icon(self) -> str:
        """Return the icon to use in the frontend."""
        return "mdi:signal" if self.is_on else "mdi:signal-off"


class MadvrHDRFlagBinarySensor(MadvrBaseBinarySensor):
    """Binary sensor representing the HDR flag state of the madVR device."""

    def __init__(self, coordinator: MadVRCoordinator) -> None:
        """Initialize the HDR flag binary sensor."""
        super().__init__(coordinator, f"{coordinator.name} HDR Flag", "hdr_flag")

    @property
    def is_on(self) -> bool:
        """Return true if HDR is detected."""
        return bool(
            self.coordinator.data.get("hdr_flag", False)
            if self.coordinator.data
            else False
        )

    @property
    def icon(self) -> str:
        """Return the icon to use in the frontend."""
        return "mdi:hdr" if self.is_on else "mdi:hdr-off"


class MadvrHDROutgoingFlagBinarySensor(MadvrBaseBinarySensor):
    """Binary sensor representing the outgoing HDR flag state of the madVR device."""

    def __init__(self, coordinator: MadVRCoordinator) -> None:
        """Initialize the outgoing HDR flag binary sensor."""
        super().__init__(
            coordinator,
            f"{coordinator.name} Outgoing HDR Flag",
            "outgoing_hdr_flag",
        )

    @property
    def is_on(self) -> bool:
        """Return true if HDR is detected."""
        return bool(
            self.coordinator.data.get("outgoing_hdr_flag", False)
            if self.coordinator.data
            else False
        )

    @property
    def icon(self) -> str:
        """Return the icon to use in the frontend."""
        return "mdi:hdr" if self.is_on else "mdi:hdr-off"
