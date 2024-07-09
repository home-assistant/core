"""Binary sensor entities for the madVR integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.binary_sensor import (
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
from .entity import MadVREntity

_HDR_FLAG = "hdr_flag"
_OUTGOING_HDR_FLAG = "outgoing_hdr_flag"
_POWER_STATE = "power_state"
_SIGNAL_STATE = "signal_state"


@dataclass(frozen=True)
class MadvrBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describe madVR binary sensor entity."""

    value_fn: Callable[[MadVRCoordinator], bool] = lambda _: False


BINARY_SENSORS: tuple[MadvrBinarySensorEntityDescription, ...] = (
    MadvrBinarySensorEntityDescription(
        key=_POWER_STATE,
        translation_key=_POWER_STATE,
        value_fn=lambda coordinator: coordinator.client.is_on
        if coordinator.client
        else False,
    ),
    MadvrBinarySensorEntityDescription(
        key=_SIGNAL_STATE,
        translation_key=_SIGNAL_STATE,
        value_fn=lambda coordinator: bool(
            coordinator.data.get("is_signal", False) if coordinator.data else False
        ),
    ),
    MadvrBinarySensorEntityDescription(
        key=_HDR_FLAG,
        translation_key=_HDR_FLAG,
        value_fn=lambda coordinator: bool(
            coordinator.data.get("hdr_flag", False) if coordinator.data else False
        ),
    ),
    MadvrBinarySensorEntityDescription(
        key=_OUTGOING_HDR_FLAG,
        translation_key=_OUTGOING_HDR_FLAG,
        value_fn=lambda coordinator: bool(
            coordinator.data.get("outgoing_hdr_flag", False)
            if coordinator.data
            else False
        ),
    ),
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


class MadvrBinarySensor(MadVREntity, CoordinatorEntity, BinarySensorEntity):
    """Base class for madVR binary sensors."""

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
    def device_info(self) -> DeviceInfo | None:
        """Return the device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.mac)},
            name="madVR Envy",
            manufacturer="madVR",
            model="Envy",
        )
