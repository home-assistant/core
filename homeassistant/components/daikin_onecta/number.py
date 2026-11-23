"""Number entities for Daikin Onecta."""

from typing import override

from daikin_onecta import ClimateControl
from daikin_onecta.client import OnectaClient
from daikin_onecta.models import Setpoint

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.const import EntityCategory, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import LEAVING_WATER_OFFSET
from .coordinator import DaikinOnectaConfigEntry, OnectaDataUpdateCoordinator
from .device import DaikinOnectaDevice
from .entity import (
    DaikinManagementPointEntity,
    EntityIdChecker,
    add_entities_on_coordinator_update,
    iter_management_points,
    management_point_unique_id,
)
from .utils import round_temperature_to_step, temperature_unit_or_celsius

PARALLEL_UPDATES = 0

LEAVING_WATER_OFFSET_DESCRIPTION = NumberEntityDescription(
    key="leaving_water_offset",
    translation_key="leaving_water_offset",
    device_class=NumberDeviceClass.TEMPERATURE_DELTA,
    entity_category=EntityCategory.CONFIG,
    mode=NumberMode.BOX,
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: DaikinOnectaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Daikin leaving-water offset numbers."""
    coordinator: OnectaDataUpdateCoordinator = config_entry.runtime_data
    add_entities_on_coordinator_update(
        hass,
        config_entry,
        coordinator,
        async_add_entities,
        lambda is_known: _create_numbers(coordinator, is_known),
    )


def _create_numbers(
    coordinator: OnectaDataUpdateCoordinator,
    is_known: EntityIdChecker,
) -> list[DaikinLeavingWaterOffsetNumber]:
    """Create one number for each point advertising the offset setpoint."""
    return [
        DaikinLeavingWaterOffsetNumber(device, coordinator, point.embedded_id)
        for device, point in iter_management_points(coordinator)
        if (climate_control := point.climate_control) is not None
        and LEAVING_WATER_OFFSET in climate_control.setpoint_types
        and not is_known(
            Platform.NUMBER,
            management_point_unique_id(
                device.id, point.embedded_id, LEAVING_WATER_OFFSET
            ),
        )
    ]


class DaikinLeavingWaterOffsetNumber(DaikinManagementPointEntity, NumberEntity):
    """Set a Daikin climate-control leaving-water temperature offset."""

    entity_description = LEAVING_WATER_OFFSET_DESCRIPTION
    _attr_native_min_value = -10.0
    _attr_native_max_value = 10.0
    _attr_native_step = 1.0

    def __init__(
        self,
        device: DaikinOnectaDevice,
        coordinator: OnectaDataUpdateCoordinator,
        embedded_id: str,
    ) -> None:
        """Initialize the number from the management point."""
        super().__init__(device, coordinator, embedded_id)
        self._attr_unique_id = management_point_unique_id(
            self._device_id, embedded_id, LEAVING_WATER_OFFSET
        )
        self._is_settable = False
        self.update_state()

    def _climate_control(self) -> ClimateControl | None:
        """Return the current typed climate-control data."""
        point = self._management_point
        return point.climate_control if point is not None else None

    def _current_setpoint(self) -> tuple[str, Setpoint] | None:
        """Return the leaving-water offset for the current operation mode."""
        climate_control = self._climate_control()
        if (
            climate_control is None
            or (operation_mode := climate_control.current_operation_mode) is None
            or (
                setpoint := climate_control.setpoint(
                    LEAVING_WATER_OFFSET, operation_mode
                )
            )
            is None
        ):
            return None
        return operation_mode, setpoint

    @override
    def update_state(self) -> None:
        """Refresh offset value and range from the current operation mode."""
        current = self._current_setpoint()
        setpoint = current[1] if current is not None else None
        self._is_settable = setpoint is not None and setpoint.settable
        self._attr_native_value = (
            float(setpoint.value) if setpoint is not None else None
        )
        self._attr_native_min_value = (
            float(setpoint.min_value)
            if setpoint is not None and setpoint.min_value is not None
            else -10.0
        )
        self._attr_native_max_value = (
            float(setpoint.max_value)
            if setpoint is not None and setpoint.max_value is not None
            else 10.0
        )
        self._attr_native_step = (
            float(setpoint.step_value)
            if setpoint is not None and setpoint.step_value is not None
            else 1.0
        )
        self._attr_native_unit_of_measurement = temperature_unit_or_celsius(
            setpoint.unit if setpoint is not None else None
        )

    @property
    @override
    def available(self) -> bool:
        """Return whether the current offset can be changed."""
        return super().available and self._is_settable

    @override
    async def async_set_native_value(self, value: float) -> None:
        """Set the offset in the current Daikin operation mode."""
        current = self._current_setpoint()
        if current is None or not current[1].settable:
            self._raise_service_validation_error("climate_temperature_unavailable")
        operation_mode, setpoint = current
        rounded_value = round_temperature_to_step(
            value,
            setpoint.step_value,
            setpoint.min_value,
            setpoint.max_value,
            default_step=1,
            fallback_minimum=-10,
            fallback_maximum=10,
        )
        if rounded_value == setpoint.value:
            return

        await self._async_execute_sub_client_command(
            OnectaClient.climate_control,
            lambda climate: climate.set_temperature(
                operation_mode, LEAVING_WATER_OFFSET, rounded_value
            ),
            "set_temperature_failed",
        )
        if (climate_control := self._climate_control()) is not None and (
            updated_setpoint := climate_control.setpoint(
                LEAVING_WATER_OFFSET, operation_mode
            )
        ) is not None:
            updated_setpoint.value = rounded_value
            self._publish_write_update()
