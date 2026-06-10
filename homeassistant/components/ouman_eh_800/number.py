"""Number platform for the Ouman EH-800 integration."""

from dataclasses import dataclass

from ouman_eh_800_api import (
    FloatControlOumanEndpoint,
    IntControlOumanEndpoint,
    L1BaseEndpoints,
    L1ConstantTempMode,
    L1FivePointCurve,
    L1NoRoomSensor,
    L1RoomSensor,
    L1ThreePointCurve,
    L2BaseEndpoints,
    L2FivePointCurve,
    L2NoRoomSensor,
    L2RoomSensor,
    L2ThreePointCurve,
    SystemEndpoints,
)

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.const import EntityCategory, UnitOfTemperature, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import OumanDevice
from .coordinator import OumanEh800ConfigEntry, OumanEh800Coordinator
from .entity import OumanEh800Entity, OumanEh800EntityDescription

PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class OumanEh800NumberEntityDescription(
    OumanEh800EntityDescription, NumberEntityDescription
):
    """Number description with main/L1/L2 device assignment."""


def _temperature_number(
    *,
    device: OumanDevice,
    key: str,
    device_class: NumberDeviceClass = NumberDeviceClass.TEMPERATURE,
    entity_category: EntityCategory | None = EntityCategory.CONFIG,
    enabled_by_default: bool = True,
) -> OumanEh800NumberEntityDescription:
    return OumanEh800NumberEntityDescription(
        device=device,
        key=key,
        translation_key=key,
        device_class=device_class,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        mode=NumberMode.BOX,
        entity_category=entity_category,
        entity_registry_enabled_default=enabled_by_default,
    )


NUMBER_DESCRIPTIONS: dict[
    IntControlOumanEndpoint | FloatControlOumanEndpoint,
    OumanEh800NumberEntityDescription,
] = {
    SystemEndpoints.TREND_SAMPLE_INTERVAL: OumanEh800NumberEntityDescription(
        device=OumanDevice.MAIN,
        key="trend_sampling_interval",
        translation_key="trend_sampling_interval",
        native_unit_of_measurement=UnitOfTime.SECONDS,
        mode=NumberMode.BOX,
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
    ),
    # L1 base water-out temperature limits.
    L1BaseEndpoints.WATER_OUT_MIN_TEMP: _temperature_number(
        device=OumanDevice.L1, key="water_out_minimum_temperature"
    ),
    L1BaseEndpoints.WATER_OUT_MAX_TEMP: _temperature_number(
        device=OumanDevice.L1, key="water_out_maximum_temperature"
    ),
    # L1 heating curve. Three-point and five-point variants share keys
    # where their meaning overlaps.
    L1ThreePointCurve.CURVE_MINUS_20_TEMP: _temperature_number(
        device=OumanDevice.L1, key="curve_minus_20_temperature"
    ),
    L1ThreePointCurve.CURVE_0_TEMP: _temperature_number(
        device=OumanDevice.L1, key="curve_0_temperature"
    ),
    L1ThreePointCurve.CURVE_20_TEMP: _temperature_number(
        device=OumanDevice.L1, key="curve_20_temperature"
    ),
    L1FivePointCurve.CURVE_MINUS_20_TEMP: _temperature_number(
        device=OumanDevice.L1, key="curve_minus_20_temperature"
    ),
    L1FivePointCurve.CURVE_MINUS_10_TEMP: _temperature_number(
        device=OumanDevice.L1, key="curve_minus_10_temperature"
    ),
    L1FivePointCurve.CURVE_0_TEMP: _temperature_number(
        device=OumanDevice.L1, key="curve_0_temperature"
    ),
    L1FivePointCurve.CURVE_10_TEMP: _temperature_number(
        device=OumanDevice.L1, key="curve_10_temperature"
    ),
    L1FivePointCurve.CURVE_20_TEMP: _temperature_number(
        device=OumanDevice.L1, key="curve_20_temperature"
    ),
    # L1 no-room-sensor and room-sensor variants share keys for the offsets
    # that conceptually mean the same thing on both axes.
    L1NoRoomSensor.TEMPERATURE_DROP: _temperature_number(
        device=OumanDevice.L1,
        key="temperature_drop",
        device_class=NumberDeviceClass.TEMPERATURE_DELTA,
    ),
    L1NoRoomSensor.BIG_TEMPERATURE_DROP: _temperature_number(
        device=OumanDevice.L1,
        key="big_temperature_drop",
        device_class=NumberDeviceClass.TEMPERATURE_DELTA,
    ),
    L1NoRoomSensor.ROOM_TEMPERATURE_FINE_TUNING: _temperature_number(
        device=OumanDevice.L1,
        key="room_temperature_fine_tuning",
        device_class=NumberDeviceClass.TEMPERATURE_DELTA,
    ),
    L1RoomSensor.TEMPERATURE_DROP: _temperature_number(
        device=OumanDevice.L1,
        key="temperature_drop",
        device_class=NumberDeviceClass.TEMPERATURE_DELTA,
    ),
    L1RoomSensor.BIG_TEMPERATURE_DROP: _temperature_number(
        device=OumanDevice.L1,
        key="big_temperature_drop",
        device_class=NumberDeviceClass.TEMPERATURE_DELTA,
    ),
    L1RoomSensor.ROOM_TEMPERATURE_FINE_TUNING: _temperature_number(
        device=OumanDevice.L1,
        key="room_temperature_fine_tuning",
        device_class=NumberDeviceClass.TEMPERATURE_DELTA,
    ),
    L1ConstantTempMode.CONSTANT_TEMP_SETPOINT: _temperature_number(
        device=OumanDevice.L1,
        key="constant_temp_setpoint",
        entity_category=None,
    ),
    # L2 mirrors L1.
    L2BaseEndpoints.WATER_OUT_MIN_TEMP: _temperature_number(
        device=OumanDevice.L2, key="water_out_minimum_temperature"
    ),
    L2BaseEndpoints.WATER_OUT_MAX_TEMP: _temperature_number(
        device=OumanDevice.L2, key="water_out_maximum_temperature"
    ),
    L2ThreePointCurve.CURVE_MINUS_20_TEMP: _temperature_number(
        device=OumanDevice.L2, key="curve_minus_20_temperature"
    ),
    L2ThreePointCurve.CURVE_0_TEMP: _temperature_number(
        device=OumanDevice.L2, key="curve_0_temperature"
    ),
    L2ThreePointCurve.CURVE_20_TEMP: _temperature_number(
        device=OumanDevice.L2, key="curve_20_temperature"
    ),
    L2FivePointCurve.CURVE_MINUS_20_TEMP: _temperature_number(
        device=OumanDevice.L2, key="curve_minus_20_temperature"
    ),
    L2FivePointCurve.CURVE_MINUS_10_TEMP: _temperature_number(
        device=OumanDevice.L2, key="curve_minus_10_temperature"
    ),
    L2FivePointCurve.CURVE_0_TEMP: _temperature_number(
        device=OumanDevice.L2, key="curve_0_temperature"
    ),
    L2FivePointCurve.CURVE_10_TEMP: _temperature_number(
        device=OumanDevice.L2, key="curve_10_temperature"
    ),
    L2FivePointCurve.CURVE_20_TEMP: _temperature_number(
        device=OumanDevice.L2, key="curve_20_temperature"
    ),
    L2NoRoomSensor.TEMPERATURE_DROP: _temperature_number(
        device=OumanDevice.L2,
        key="temperature_drop",
        device_class=NumberDeviceClass.TEMPERATURE_DELTA,
    ),
    L2NoRoomSensor.BIG_TEMPERATURE_DROP: _temperature_number(
        device=OumanDevice.L2,
        key="big_temperature_drop",
        device_class=NumberDeviceClass.TEMPERATURE_DELTA,
    ),
    L2NoRoomSensor.ROOM_TEMPERATURE_FINE_TUNING: _temperature_number(
        device=OumanDevice.L2,
        key="room_temperature_fine_tuning",
        device_class=NumberDeviceClass.TEMPERATURE_DELTA,
    ),
    L2RoomSensor.TEMPERATURE_DROP: _temperature_number(
        device=OumanDevice.L2,
        key="temperature_drop",
        device_class=NumberDeviceClass.TEMPERATURE_DELTA,
    ),
    L2RoomSensor.BIG_TEMPERATURE_DROP: _temperature_number(
        device=OumanDevice.L2,
        key="big_temperature_drop",
        device_class=NumberDeviceClass.TEMPERATURE_DELTA,
    ),
    L2RoomSensor.ROOM_TEMPERATURE_FINE_TUNING: _temperature_number(
        device=OumanDevice.L2,
        key="room_temperature_fine_tuning",
        device_class=NumberDeviceClass.TEMPERATURE_DELTA,
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: OumanEh800ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Ouman EH-800 number entities based on a config entry."""
    coordinator = entry.runtime_data
    async_add_entities(
        OumanEh800NumberEntity(coordinator, endpoint, description)
        for endpoint in coordinator.data
        if isinstance(endpoint, IntControlOumanEndpoint | FloatControlOumanEndpoint)
        and (description := NUMBER_DESCRIPTIONS.get(endpoint)) is not None
    )


class OumanEh800NumberEntity(OumanEh800Entity, NumberEntity):
    """Ouman EH-800 number entity."""

    entity_description: OumanEh800NumberEntityDescription
    _endpoint: IntControlOumanEndpoint | FloatControlOumanEndpoint

    def __init__(
        self,
        coordinator: OumanEh800Coordinator,
        endpoint: IntControlOumanEndpoint | FloatControlOumanEndpoint,
        description: OumanEh800NumberEntityDescription,
    ) -> None:
        """Initialize the number entity."""
        super().__init__(coordinator, endpoint, description)
        self._attr_native_min_value = float(endpoint.min_val)
        self._attr_native_max_value = float(endpoint.max_val)
        self._attr_native_step = (
            1 if isinstance(endpoint, IntControlOumanEndpoint) else 0.1
        )

    @property
    def native_value(self) -> float:
        """Return the current value."""
        value = self.coordinator.data[self._endpoint]
        assert isinstance(value, float)
        return value

    async def async_set_native_value(self, value: float) -> None:
        """Set a new value on the device."""
        final_value: int | float = (
            int(value) if isinstance(self._endpoint, IntControlOumanEndpoint) else value
        )
        await self.coordinator.async_set_endpoint_value(self._endpoint, final_value)
