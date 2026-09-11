"""Switch platform for the SMA integration."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, override

from pysma import (
    ModbusControl,
    SmaConnectionException,
    SmaTimeoutException,
    SmaWriteException,
)
from pysma.sensor import Sensor

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import SMAConfigEntry
from .const import DOMAIN
from .coordinator import SMADataUpdateCoordinator

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class SMASwitchEntityDescription(SwitchEntityDescription):
    """Class to hold SMA Modbus switch description."""

    control: ModbusControl
    status_sensor_key: str
    is_on_fn: Callable[[Sensor], bool | None]


SWITCH_DESCRIPTIONS: tuple[SMASwitchEntityDescription, ...] = (
    SMASwitchEntityDescription(
        key="inverter_enabled",
        translation_key="inverter_enabled",
        control=ModbusControl.INVERTER_ENABLED,
        entity_category=EntityCategory.CONFIG,
        status_sensor_key="operating_status_general",
        is_on_fn=lambda sensor: (
            None if sensor.raw_value is None else sensor.raw_value != 303
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
    added_controls: set[ModbusControl] = set()

    @callback
    def _add_new_entities() -> None:
        """Add switches for controls discovered after initial setup."""
        new_descriptions = [
            description
            for description in SWITCH_DESCRIPTIONS
            if description.control not in added_controls
            and description.control in coordinator.supported_modbus_controls
        ]
        if not new_descriptions:
            return

        added_controls.update(description.control for description in new_descriptions)
        async_add_entities(
            SMAModbusSwitch(coordinator, description, entry)
            for description in new_descriptions
        )

    _add_new_entities()
    entry.async_on_unload(coordinator.async_add_listener(_add_new_entities))


async def _perform_modbus_action(
    coordinator: SMADataUpdateCoordinator,
    control: ModbusControl,
    value: float,
) -> None:
    """Perform a Modbus action and refresh the coordinator."""
    try:
        await coordinator.sma_modbus.set_control(control, value)
    except (SmaConnectionException, SmaTimeoutException) as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="modbus_action_failed",
            translation_placeholders={"control": control, "value": str(value)},
        ) from err
    except SmaWriteException as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="modbus_write_failed",
            translation_placeholders={"control": control, "value": str(value)},
        ) from err
    else:
        await coordinator.async_request_refresh()


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
        if TYPE_CHECKING:
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
        if description.status_sensor_key in coordinator.data.sensors:
            coordinator.data.sensors[description.status_sensor_key].enabled = True

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
        """Return true if the entity description's status sensor reports on."""
        if (
            self.entity_description.status_sensor_key
            not in self.coordinator.data.sensors
        ):
            return None
        return self.entity_description.is_on_fn(
            self.coordinator.data.sensors[self.entity_description.status_sensor_key]
        )

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the control on."""
        await _perform_modbus_action(
            self.coordinator, self.entity_description.control, 1
        )

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the control off."""
        await _perform_modbus_action(
            self.coordinator, self.entity_description.control, 0
        )
