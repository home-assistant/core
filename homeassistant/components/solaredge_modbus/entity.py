"""Base entities for the SolarEdge Modbus integration.

Each meter and battery attached to the inverter is its own sub-device, linked
to the inverter as its parent; everything else belongs to the inverter. All
identities derive from the inverter's serial number, which the config flow
stores as the config entry unique ID.
"""

from typing import TYPE_CHECKING, override

from solaredged import (
    Battery,
    ExportControl,
    Meter,
    PowerControl,
    SolarEdge,
    StorageControl,
)

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN,
    SUBSYSTEM_INVERTER,
    SUBSYSTEM_POWER_CONTROL,
    SUBSYSTEM_SITE_CONTROL,
)
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


# The control blocks that host entities. Advanced power control is polled but
# has none, so adding entities for it means widening this and the sub-system it
# maps to below.
type ControlComponent = ExportControl | PowerControl | StorageControl


def _control_subsystem(component: ControlComponent) -> str:
    """Return the sub-system a control block's poll is reported under."""
    if isinstance(component, PowerControl):
        return SUBSYSTEM_POWER_CONTROL
    # Export control's read spans storage control, so the library reads the two
    # as one pooled block and reports them together.
    return SUBSYSTEM_SITE_CONTROL


def attachment_identity(component: Battery | Meter, index: int) -> str:
    """Return what tells an attached device apart from the next in its place.

    One that reports a serial number is known by it, so replacing it is a
    different device rather than the same slot with other numbers in it. Not
    every meter or battery reports one, and then the slot it is wired to is all
    there is. That fallback says so, since a bare number could be a serial
    itself.
    """
    return component.serial_number or f"slot_{index}"


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
        super().__init__(coordinator=entry.runtime_data.coordinator_for(subsystem))
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
        subsystem: str = SUBSYSTEM_INVERTER,
    ) -> None:
        """Initialize a SolarEdge Modbus inverter entity."""
        super().__init__(entry=entry, subsystem=subsystem, description=description)
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
        meter = entry.runtime_data.solaredge.meters[index - 1]
        identity = attachment_identity(meter, index)
        super().__init__(
            entry=entry,
            subsystem=f"meters[{index - 1}]",
            description=description,
            key_prefix=f"meter_{identity}_",
        )
        self._index = index

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{self._serial_number}_meter_{identity}")},
            manufacturer=meter.manufacturer or "SolarEdge",
            # What a meter reports is a part number, like "SE-MTR-3Y-400V-A",
            # and there is no shorter name it is sold under to put beside it.
            model_id=meter.model or None,
            name=f"Meter {index}",
            serial_number=meter.serial_number or None,
            via_device_id=entry.runtime_data.inverter_device_id,
        )


class SolarEdgeModbusBatteryEntity(SolarEdgeModbusEntity):
    """Defines a SolarEdge Modbus entity on a battery sub-device."""

    def __init__(
        self,
        *,
        entry: SolarEdgeModbusConfigEntry,
        description: EntityDescription,
        index: int,
    ) -> None:
        """Initialize a SolarEdge Modbus battery entity."""
        battery = entry.runtime_data.solaredge.batteries[index - 1]
        identity = attachment_identity(battery, index)
        super().__init__(
            entry=entry,
            subsystem=f"batteries[{index - 1}]",
            description=description,
            key_prefix=f"battery_{identity}_",
        )
        self._index = index

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{self._serial_number}_battery_{identity}")},
            manufacturer=battery.manufacturer or "SolarEdge",
            # A battery names itself the same way a meter does, with a part
            # number rather than something it is sold under.
            model_id=battery.model or None,
            name=f"Battery {index}",
            sw_version=battery.version or None,
            serial_number=battery.serial_number or None,
            via_device_id=entry.runtime_data.inverter_device_id,
        )


class SolarEdgeModbusControlEntity[ComponentT: ControlComponent](
    SolarEdgeModbusInverterEntity
):
    """Defines a SolarEdge Modbus entity for a writable control block.

    The library refreshes the component instances in place on every poll, so
    the entity holds on to its control component directly.
    """

    def __init__(
        self,
        *,
        entry: SolarEdgeModbusConfigEntry,
        description: EntityDescription,
        component: ComponentT,
    ) -> None:
        """Initialize a SolarEdge Modbus control entity."""
        super().__init__(
            entry=entry,
            subsystem=_control_subsystem(component),
            description=description,
        )
        self._component = component
