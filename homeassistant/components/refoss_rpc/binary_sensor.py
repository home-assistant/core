"""Binary sensor entities for Refoss."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import RefossConfigEntry
from .entity import (
    RefossAttributeEntity,
    RefossEntityDescription,
    async_setup_entry_refoss,
)
from .utils import is_refoss_input_button


@dataclass(frozen=True, kw_only=True)
class RefossBinarySensorDescription(
    RefossEntityDescription, BinarySensorEntityDescription
):
    """Class to describe a  binary sensor."""


REFOSS_BINARY_SENSORS: Final = {
    "input": RefossBinarySensorDescription(
        key="input",
        sub_key="state",
        name="Input",
        device_class=BinarySensorDeviceClass.POWER,
        removal_condition=is_refoss_input_button,
    ),
    "cloud": RefossBinarySensorDescription(
        key="cloud",
        sub_key="connected",
        name="Cloud",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    "overtemp": RefossBinarySensorDescription(
        key="sys",
        sub_key="errors",
        name="Overheating",
        device_class=BinarySensorDeviceClass.PROBLEM,
        value=lambda status, _: False if status is None else "overtemp" in status,
        entity_category=EntityCategory.DIAGNOSTIC,
        supported=lambda status: status.get("temperature") is not None,
    ),
    "overpower": RefossBinarySensorDescription(
        key="switch",
        sub_key="errors",
        name="Overpowering",
        device_class=BinarySensorDeviceClass.PROBLEM,
        value=lambda status, _: False if status is None else "overpower" in status,
        entity_category=EntityCategory.DIAGNOSTIC,
        supported=lambda status: status.get("apower") is not None,
    ),
    "overvoltage": RefossBinarySensorDescription(
        key="switch",
        sub_key="errors",
        name="Overvoltage",
        device_class=BinarySensorDeviceClass.PROBLEM,
        value=lambda status, _: False if status is None else "overvoltage" in status,
        entity_category=EntityCategory.DIAGNOSTIC,
        supported=lambda status: status.get("apower") is not None,
    ),
    "overcurrent": RefossBinarySensorDescription(
        key="switch",
        sub_key="errors",
        name="Overcurrent",
        device_class=BinarySensorDeviceClass.PROBLEM,
        value=lambda status, _: False if status is None else "overcurrent" in status,
        entity_category=EntityCategory.DIAGNOSTIC,
        supported=lambda status: status.get("apower") is not None,
    ),
    "undervoltage": RefossBinarySensorDescription(
        key="switch",
        sub_key="errors",
        name="Undervoltage",
        device_class=BinarySensorDeviceClass.PROBLEM,
        value=lambda status, _: False if status is None else "undervoltage" in status,
        entity_category=EntityCategory.DIAGNOSTIC,
        supported=lambda status: status.get("apower") is not None,
    ),
    "restart": RefossBinarySensorDescription(
        key="sys",
        sub_key="restart_required",
        name="Restart required",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: RefossConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up sensors for device."""
    coordinator = config_entry.runtime_data.coordinator
    assert coordinator

    async_setup_entry_refoss(
        hass,
        config_entry,
        async_add_entities,
        REFOSS_BINARY_SENSORS,
        RefossBinarySensor,
    )


class RefossBinarySensor(RefossAttributeEntity, BinarySensorEntity):
    """Refoss binary sensor entity."""

    entity_description: RefossBinarySensorDescription

    @property
    def is_on(self) -> bool:
        """Return true if  sensor state is on."""
        return bool(self.attribute_value)
