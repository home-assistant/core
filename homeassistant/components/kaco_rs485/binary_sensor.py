"""Binary sensors."""

from typing import override

from kaco_rs485 import is_fault

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import CONF_ADDRESSES
from .coordinator import KacoRs485ConfigEntry, KacoRs485Coordinator
from .entity import KacoRs485Entity

PARALLEL_UPDATES = 0

FAULT = BinarySensorEntityDescription(
    key="fault",
    translation_key="fault",
    device_class=BinarySensorDeviceClass.PROBLEM,
    entity_category=EntityCategory.DIAGNOSTIC,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: KacoRs485ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the fault sensor for every configured inverter."""
    coordinator = entry.runtime_data
    async_add_entities(
        KacoRs485FaultSensor(coordinator, address)
        for address in entry.data[CONF_ADDRESSES]
    )


class KacoRs485FaultSensor(KacoRs485Entity, BinarySensorEntity):
    """On while the inverter reports a status from the fault table."""

    entity_description = FAULT

    def __init__(self, coordinator: KacoRs485Coordinator, address: int) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, address)
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{address}_fault"

    @property
    @override
    def is_on(self) -> bool | None:
        """Return whether the inverter has tripped."""
        state = self.inverter
        if state is None or state.measured is None:
            return None
        return is_fault(state.measured.status)
