"""Base entities for the SolarEdge Modbus integration.

Each meter attached to the inverter is its own sub-device, linked to the
inverter as its parent; everything else belongs to the inverter. All
identities derive from the inverter's serial number, which the config flow
stores as the config entry unique ID.
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
    """Return device information for the inverter itself."""
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


class SolarEdgeModbusEntity(CoordinatorEntity[SolarEdgeModbusDataUpdateCoordinator]):
    """Defines a SolarEdge Modbus entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        *,
        entry: SolarEdgeModbusConfigEntry,
        subsystem: str,
        description: EntityDescription,
        key_prefix: str = "",
    ) -> None:
        """Initialize a SolarEdge Modbus entity."""
        super().__init__(coordinator=entry.runtime_data.readings)
        self.entity_description = description
        self._subsystem = subsystem

        serial_number = entry.unique_id
        if TYPE_CHECKING:
            assert serial_number is not None
        self._serial_number = serial_number
        self._attr_unique_id = f"{serial_number}_{key_prefix}{description.key}"

    @property
    @override
    def available(self) -> bool:
        """Return whether this entity's sub-system answered the last poll.

        A poll can come back partial, and an entity that reports a value from
        an earlier read as if it were current is lying about the device.
        """
        return super().available and self._subsystem not in self.coordinator.data.failed


class SolarEdgeModbusInverterEntity(SolarEdgeModbusEntity):
    """Defines a SolarEdge Modbus entity on the inverter device."""

    def __init__(
        self,
        *,
        entry: SolarEdgeModbusConfigEntry,
        description: EntityDescription,
    ) -> None:
        """Initialize a SolarEdge Modbus inverter entity."""
        super().__init__(
            entry=entry, subsystem=SUBSYSTEM_INVERTER, description=description
        )
        self._attr_device_info = entry.runtime_data.device_info


class SolarEdgeModbusMeterEntity(SolarEdgeModbusEntity):
    """Defines a SolarEdge Modbus entity on a meter sub-device."""

    def __init__(
        self,
        *,
        entry: SolarEdgeModbusConfigEntry,
        description: EntityDescription,
        index: int,
    ) -> None:
        """Initialize a SolarEdge Modbus meter entity."""
        super().__init__(
            entry=entry,
            subsystem=f"meters[{index - 1}]",
            description=description,
            key_prefix=f"meter_{index}_",
        )
        self._index = index

        meter = entry.runtime_data.solaredge.meters[index - 1]
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{self._serial_number}_meter_{index}")},
            manufacturer=meter.manufacturer or "SolarEdge",
            model=meter.model or None,
            name=f"Meter {index}",
            serial_number=meter.serial_number or None,
            via_device_id=entry.runtime_data.inverter_device_id,
        )
