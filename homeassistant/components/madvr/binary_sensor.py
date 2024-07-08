"""Binary sensor entities for the madVR integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import MadVRConfigEntry
from .const import DOMAIN
from .coordinator import MadVRCoordinator

_HDR_FLAG = "hdr_flag"
_OUTGOING_HDR_FLAG = "outgoing_hdr_flag"
_POWER_STATE = "power_state"
_SIGNAL_STATE = "signal_state"


@dataclass(frozen=True)
class MadvrBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describe madVR binary sensor entity."""

    icon_on: str = ""
    icon_off: str = ""
    value_fn: Callable[[MadVRCoordinator], bool] = lambda _: False


BINARY_SENSORS: tuple[MadvrBinarySensorEntityDescription, ...] = (
    MadvrBinarySensorEntityDescription(
        key=_POWER_STATE,
        name="Power State",
        device_class=BinarySensorDeviceClass.POWER,
        icon_on="mdi:power",
        icon_off="mdi:power-off",
        value_fn=lambda coordinator: coordinator.client.is_on
        if coordinator.client
        else False,
    ),
    MadvrBinarySensorEntityDescription(
        key=_SIGNAL_STATE,
        name="Signal State",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        icon_on="mdi:signal",
        icon_off="mdi:signal-off",
        value_fn=lambda coordinator: bool(
            coordinator.data.get("is_signal", False) if coordinator.data else False
        ),
    ),
    MadvrBinarySensorEntityDescription(
        key=_HDR_FLAG,
        name="HDR Flag",
        device_class=None,
        icon_on="mdi:hdr",
        icon_off="mdi:hdr-off",
        value_fn=lambda coordinator: bool(
            coordinator.data.get("hdr_flag", False) if coordinator.data else False
        ),
    ),
    MadvrBinarySensorEntityDescription(
        key=_OUTGOING_HDR_FLAG,
        name="Outgoing HDR Flag",
        device_class=None,
        icon_on="mdi:hdr",
        icon_off="mdi:hdr-off",
        value_fn=lambda coordinator: bool(
            coordinator.data.get("outgoing_hdr_flag", False)
            if coordinator.data
            else False
        ),
    ),
)


class MadvrBinarySensor(CoordinatorEntity, BinarySensorEntity):
    """Base class for madVR binary sensors."""

    _attr_has_entity_name = True
    coordinator: MadVRCoordinator
    entity_description: MadvrBinarySensorEntityDescription

    def __init__(
        self,
        coordinator: MadVRCoordinator,
        description: MadvrBinarySensorEntityDescription,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.mac}_{description.key}"

    @property
    def is_on(self) -> bool:
        """Return true if the binary sensor is on."""
        return bool(self.entity_description.value_fn(self.coordinator))

    @property
    def icon(self) -> str:
        """Return the icon to use in the frontend."""
        return (
            self.entity_description.icon_on
            if self.is_on
            else self.entity_description.icon_off
        )

    @property
    def device_info(self) -> DeviceInfo | None:
        """Return the device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.mac)},
            name="madVR Envy",
            manufacturer="madVR",
            model="Envy",
        )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MadVRConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the binary sensor entities."""
    coordinator = entry.runtime_data
    async_add_entities(
        MadvrBinarySensor(coordinator, description) for description in BINARY_SENSORS
    )
