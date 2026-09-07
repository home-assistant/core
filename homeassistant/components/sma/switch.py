"""Switch platform for the SMA integration."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, override

from pysma import ModbusControl

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import SMAConfigEntry
from .const import DOMAIN
from .coordinator import SMADataUpdateCoordinator

PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class SMASwitchEntityDescription(SwitchEntityDescription):
    """Class to hold SMA Modbus switch description."""

    control: ModbusControl
    is_on_fn: Callable[[float], bool] = bool
    supported_fn: Callable[[SMADataUpdateCoordinator], bool] = lambda _: True


SWITCH_DESCRIPTIONS: tuple[SMASwitchEntityDescription, ...] = (
    SMASwitchEntityDescription(
        key="inverter_enabled",
        translation_key="inverter_enabled",
        control=ModbusControl.INVERTER_ENABLED,
        entity_category=EntityCategory.CONFIG,
        supported_fn=lambda coordinator: (
            ModbusControl.INVERTER_ENABLED in coordinator.supported_modbus_controls
        ),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SMAConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up SMA switch entities."""
    coordinator = entry.runtime_data

    async_add_entities(
        SMAModbusSwitch(coordinator, description, entry)
        for description in SWITCH_DESCRIPTIONS
        if description.supported_fn(coordinator)
    )


class SMAModbusSwitch(CoordinatorEntity[SMADataUpdateCoordinator], SwitchEntity):
    """Switch to control an SMA Modbus control."""

    entity_description: SMASwitchEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: SMADataUpdateCoordinator,
        description: SMASwitchEntityDescription,
        entry: SMAConfigEntry,
    ) -> None:
        """Initialize the switch."""
        super().__init__(coordinator)
        assert entry.unique_id
        self.entity_description = description

        self._attr_unique_id = f"{entry.unique_id}-{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.unique_id)},
            manufacturer=coordinator.data.sma_device_info.manufacturer,
            model=coordinator.data.sma_device_info.type,
            name=coordinator.data.sma_device_info.name,
            sw_version=coordinator.data.sma_device_info.sw_version,
            serial_number=coordinator.data.sma_device_info.serial,
        )

    @property
    @override
    def available(self) -> bool:
        """Return if the switch is available."""
        return (
            super().available
            and self.coordinator.data.modbus_controls.get(
                self.entity_description.control
            )
            is not None
        )

    @property
    @override
    def is_on(self) -> bool | None:
        """Return true if the control is enabled."""
        value = self.coordinator.data.modbus_controls.get(
            self.entity_description.control
        )
        return None if value is None else self.entity_description.is_on_fn(value)

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the control on."""
        await self.coordinator.perform_action(self.entity_description.control, 1)
        await self.coordinator.async_request_refresh()

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the control off."""
        await self.coordinator.perform_action(self.entity_description.control, 0)
        await self.coordinator.async_request_refresh()
