"""Base entities for the SolarEdge Modbus integration.

Every identity derives from the inverter's serial number, which the config
flow stores as the config entry unique ID.
"""

from typing import TYPE_CHECKING, override

from solaredged import SolarEdge

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, SUBSYSTEM_INVERTER
from .coordinator import (
    SolarEdgeModbusConfigEntry,
    SolarEdgeModbusDataUpdateCoordinator,
)


def inverter_model(model: str | None) -> str | None:
    """Return the model an inverter is sold as, without the variant code.

    SolarEdge reports a part number like "SE17K-RW0T0BNN4". Everything up to
    the dash is what the thing is called in a brochure and in conversation;
    the rest spells out region, connectors and options. The full string is kept
    as the model ID, where a part number belongs.
    """
    if not model:
        return None
    return model.split("-", 1)[0]


def inverter_name(model: str | None) -> str:
    """Return a name for the inverter that reads like one."""
    if (commercial := inverter_model(model)) is None:
        return "SolarEdge inverter"
    return f"SolarEdge {commercial}"


def inverter_device_info(solaredge: SolarEdge, serial_number: str) -> DeviceInfo:
    """Return device information for the inverter."""
    common = solaredge.common
    return DeviceInfo(
        identifiers={(DOMAIN, serial_number)},
        manufacturer=common.manufacturer or "SolarEdge",
        model=inverter_model(common.model),
        model_id=common.model or None,
        name=inverter_name(common.model),
        sw_version=common.version or None,
        serial_number=serial_number,
    )


class SolarEdgeModbusInverterEntity(
    CoordinatorEntity[SolarEdgeModbusDataUpdateCoordinator]
):
    """Defines a SolarEdge Modbus entity on the inverter device."""

    _attr_has_entity_name = True

    def __init__(
        self,
        *,
        entry: SolarEdgeModbusConfigEntry,
        description: EntityDescription,
    ) -> None:
        """Initialize a SolarEdge Modbus inverter entity."""
        super().__init__(coordinator=entry.runtime_data.readings)
        self.entity_description = description

        serial_number = entry.unique_id
        if TYPE_CHECKING:
            assert serial_number is not None
        self._attr_unique_id = f"{serial_number}_{description.key}"
        self._attr_device_info = inverter_device_info(
            entry.runtime_data.solaredge, serial_number
        )

    @property
    @override
    def available(self) -> bool:
        """Return whether the inverter answered the most recent poll.

        A poll can come back partial, and an entity that reports a value from
        an earlier read as if it were current is lying about the device.
        """
        return (
            super().available and SUBSYSTEM_INVERTER not in self.coordinator.data.failed
        )
