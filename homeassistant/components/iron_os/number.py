"""Number platform for IronOS integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum

from pynecil import CharSetting, LiveDataResponse, SettingsDataResponse, TempUnit

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.const import (
    EntityCategory,
    UnitOfElectricPotential,
    UnitOfPower,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util.unit_conversion import TemperatureConverter

from . import IronOSConfigEntry
from .const import (
    MAX_TEMP,
    MAX_TEMP_F,
    MIN_BOOST_TEMP,
    MIN_BOOST_TEMP_F,
    MIN_TEMP,
    MIN_TEMP_F,
)
from .coordinator import IronOSCoordinators
from .entity import IronOSBaseEntity

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class IronOSNumberEntityDescription(NumberEntityDescription):
    """Describes IronOS number entity."""

    value_fn: Callable[[LiveDataResponse, SettingsDataResponse], float | int | None]
    characteristic: CharSetting
    raw_value_fn: Callable[[float], float | int] | None = None
    native_max_value_f: float | None = None
    native_min_value_f: float | None = None


class PinecilNumber(StrEnum):
    """Number controls for Pinecil device."""

    SETPOINT_TEMP = "setpoint_temperature"
    SLEEP_TEMP = "sleep_temperature"
    SLEEP_TIMEOUT = "sleep_timeout"
    QC_MAX_VOLTAGE = "qc_max_voltage"
    PD_TIMEOUT = "pd_timeout"
    BOOST_TEMP = "boost_temp"
    SHUTDOWN_TIMEOUT = "shutdown_timeout"
    DISPLAY_BRIGHTNESS = "display_brightness"
    POWER_LIMIT = "power_limit"
    CALIBRATION_OFFSET = "calibration_offset"
    HALL_SENSITIVITY = "hall_sensitivity"
    MIN_VOLTAGE_PER_CELL = "min_voltage_per_cell"
    ACCEL_SENSITIVITY = "accel_sensitivity"
    KEEP_AWAKE_PULSE_POWER = "keep_awake_pulse_power"
    KEEP_AWAKE_PULSE_DELAY = "keep_awake_pulse_delay"
    KEEP_AWAKE_PULSE_DURATION = "keep_awake_pulse_duration"
    VOLTAGE_DIV = "voltage_div"
    TEMP_INCREMENT_SHORT = "temp_increment_short"
    TEMP_INCREMENT_LONG = "temp_increment_long"
    HALL_EFFECT_SLEEP_TIME = "hall_effect_sleep_time"


def multiply(value: float | None, multiplier: float) -> float | None:
    """Multiply if not None."""
    return value * multiplier if value is not None else None


PINECIL_NUMBER_DESCRIPTIONS: tuple[IronOSNumberEntityDescription, ...] = (
    IronOSNumberEntityDescription(
        key=PinecilNumber.QC_MAX_VOLTAGE,
        translation_key=PinecilNumber.QC_MAX_VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=NumberDeviceClass.VOLTAGE,
        value_fn=lambda _, settings: settings.get("qc_ideal_voltage"),
        characteristic=CharSetting.QC_IDEAL_VOLTAGE,
        mode=NumberMode.BOX,
        native_min_value=9.0,
        native_max_value=22.0,
        native_step=0.1,
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
    ),
    IronOSNumberEntityDescription(
        key=PinecilNumber.PD_TIMEOUT,
        translation_key=PinecilNumber.PD_TIMEOUT,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        device_class=NumberDeviceClass.DURATION,
        value_fn=lambda _, settings: settings.get("pd_negotiation_timeout"),
        characteristic=CharSetting.PD_NEGOTIATION_TIMEOUT,
        mode=NumberMode.BOX,
        native_min_value=0,
        native_max_value=5.0,
        native_step=1,
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
    ),
    IronOSNumberEntityDescription(
        key=PinecilNumber.SHUTDOWN_TIMEOUT,
        translation_key=PinecilNumber.SHUTDOWN_TIMEOUT,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        device_class=NumberDeviceClass.DURATION,
        value_fn=lambda _, settings: settings.get("shutdown_time"),
        characteristic=CharSetting.SHUTDOWN_TIME,
        mode=NumberMode.BOX,
        native_min_value=0,
        native_max_value=60,
        native_step=1,
        entity_category=EntityCategory.CONFIG,
    ),
    IronOSNumberEntityDescription(
        key=PinecilNumber.DISPLAY_BRIGHTNESS,
        translation_key=PinecilNumber.DISPLAY_BRIGHTNESS,
        value_fn=lambda _, settings: settings.get("display_brightness"),
        characteristic=CharSetting.DISPLAY_BRIGHTNESS,
        mode=NumberMode.SLIDER,
        native_min_value=1,
        native_max_value=5,
        native_step=1,
        entity_category=EntityCategory.CONFIG,
    ),
    IronOSNumberEntityDescription(
        key=PinecilNumber.SLEEP_TIMEOUT,
        translation_key=PinecilNumber.SLEEP_TIMEOUT,
        value_fn=lambda _, settings: settings.get("sleep_timeout"),
        characteristic=CharSetting.SLEEP_TIMEOUT,
        mode=NumberMode.BOX,
        native_min_value=0,
        native_max_value=15,
        native_step=1,
        entity_category=EntityCategory.CONFIG,
        native_unit_of_measurement=UnitOfTime.MINUTES,
    ),
    IronOSNumberEntityDescription(
        key=PinecilNumber.POWER_LIMIT,
        translation_key=PinecilNumber.POWER_LIMIT,
        value_fn=lambda _, settings: settings.get("power_limit"),
        characteristic=CharSetting.POWER_LIMIT,
        mode=NumberMode.BOX,
        native_min_value=0,
        native_max_value=120,
        native_step=5,
        entity_category=EntityCategory.CONFIG,
        native_unit_of_measurement=UnitOfPower.WATT,
        entity_registry_enabled_default=False,
    ),
    IronOSNumberEntityDescription(
        key=PinecilNumber.CALIBRATION_OFFSET,
        translation_key=PinecilNumber.CALIBRATION_OFFSET,
        value_fn=lambda _, settings: settings.get("calibration_offset"),
        characteristic=CharSetting.CALIBRATION_OFFSET,
        mode=NumberMode.BOX,
        native_min_value=100,
        native_max_value=2500,
        native_step=1,
        entity_category=EntityCategory.CONFIG,
        native_unit_of_measurement=UnitOfElectricPotential.MICROVOLT,
        entity_registry_enabled_default=False,
    ),
    IronOSNumberEntityDescription(
        key=PinecilNumber.HALL_SENSITIVITY,
        translation_key=PinecilNumber.HALL_SENSITIVITY,
        value_fn=lambda _, settings: settings.get("hall_sensitivity"),
        characteristic=CharSetting.HALL_SENSITIVITY,
        mode=NumberMode.SLIDER,
        native_min_value=0,
        native_max_value=9,
        native_step=1,
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
    ),
    IronOSNumberEntityDescription(
        key=PinecilNumber.MIN_VOLTAGE_PER_CELL,
        translation_key=PinecilNumber.MIN_VOLTAGE_PER_CELL,
        value_fn=lambda _, settings: settings.get("min_voltage_per_cell"),
        characteristic=CharSetting.MIN_VOLTAGE_PER_CELL,
        mode=NumberMode.BOX,
        native_min_value=2.4,
        native_max_value=3.8,
        native_step=0.1,
        entity_category=EntityCategory.CONFIG,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        entity_registry_enabled_default=False,
    ),
    IronOSNumberEntityDescription(
        key=PinecilNumber.ACCEL_SENSITIVITY,
        translation_key=PinecilNumber.ACCEL_SENSITIVITY,
        value_fn=lambda _, settings: settings.get("accel_sensitivity"),
        characteristic=CharSetting.ACCEL_SENSITIVITY,
        mode=NumberMode.SLIDER,
        native_min_value=0,
        native_max_value=9,
        native_step=1,
        entity_category=EntityCategory.CONFIG,
    ),
    IronOSNumberEntityDescription(
        key=PinecilNumber.KEEP_AWAKE_PULSE_POWER,
        translation_key=PinecilNumber.KEEP_AWAKE_PULSE_POWER,
        value_fn=lambda _, settings: settings.get("keep_awake_pulse_power"),
        characteristic=CharSetting.KEEP_AWAKE_PULSE_POWER,
        mode=NumberMode.BOX,
        native_min_value=0,
        native_max_value=9.9,
        native_step=0.1,
        entity_category=EntityCategory.CONFIG,
        native_unit_of_measurement=UnitOfPower.WATT,
        entity_registry_enabled_default=False,
    ),
    IronOSNumberEntityDescription(
        key=PinecilNumber.KEEP_AWAKE_PULSE_DELAY,
        translation_key=PinecilNumber.KEEP_AWAKE_PULSE_DELAY,
        value_fn=(
            lambda _, settings: multiply(settings.get("keep_awake_pulse_delay"), 2.5)
        ),
        characteristic=CharSetting.KEEP_AWAKE_PULSE_DELAY,
        raw_value_fn=lambda value: value / 2.5,
        mode=NumberMode.BOX,
        native_min_value=2.5,
        native_max_value=22.5,
        native_step=2.5,
        entity_category=EntityCategory.CONFIG,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        entity_registry_enabled_default=False,
    ),
    IronOSNumberEntityDescription(
        key=PinecilNumber.KEEP_AWAKE_PULSE_DURATION,
        translation_key=PinecilNumber.KEEP_AWAKE_PULSE_DURATION,
        value_fn=(
            lambda _, settings: multiply(settings.get("keep_awake_pulse_duration"), 250)
        ),
        characteristic=CharSetting.KEEP_AWAKE_PULSE_DURATION,
        raw_value_fn=lambda value: value / 250,
        mode=NumberMode.BOX,
        native_min_value=250,
        native_max_value=2250,
        native_step=250,
        entity_category=EntityCategory.CONFIG,
        native_unit_of_measurement=UnitOfTime.MILLISECONDS,
        entity_registry_enabled_default=False,
    ),
    IronOSNumberEntityDescription(
        key=PinecilNumber.VOLTAGE_DIV,
        translation_key=PinecilNumber.VOLTAGE_DIV,
        value_fn=(lambda _, settings: settings.get("voltage_div")),
        characteristic=CharSetting.VOLTAGE_DIV,
        raw_value_fn=lambda value: value,
        mode=NumberMode.BOX,
        native_min_value=360,
        native_max_value=900,
        native_step=1,
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
    ),
)

PINECIL_NUMBER_DESCRIPTIONS_V223: tuple[IronOSNumberEntityDescription, ...] = (
    IronOSNumberEntityDescription(
        key=PinecilNumber.HALL_EFFECT_SLEEP_TIME,
        translation_key=PinecilNumber.HALL_EFFECT_SLEEP_TIME,
        value_fn=(lambda _, settings: settings.get("hall_sleep_time")),
        characteristic=CharSetting.HALL_SLEEP_TIME,
        raw_value_fn=lambda value: value,
        mode=NumberMode.BOX,
        native_min_value=0,
        native_max_value=60,
        native_step=5,
        entity_category=EntityCategory.CONFIG,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        entity_registry_enabled_default=False,
    ),
)

"""
The `device_class` attribute was removed from the `setpoint_temperature`, `sleep_temperature`, and `boost_temp` entities.
These entities represent user-defined input values, not measured temperatures, and their
interpretation depends on the device's current unit configuration. Applying a device_class
results in automatic unit conversions, which introduce rounding errors due to the use of integers.
This can prevent the correct value from being set, as the input is modified during synchronization with the device.
"""
PINECIL_TEMP_NUMBER_DESCRIPTIONS: tuple[IronOSNumberEntityDescription, ...] = (
    IronOSNumberEntityDescription(
        key=PinecilNumber.SLEEP_TEMP,
        translation_key=PinecilNumber.SLEEP_TEMP,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_fn=lambda _, settings: settings.get("sleep_temp"),
        characteristic=CharSetting.SLEEP_TEMP,
        mode=NumberMode.BOX,
        native_min_value=MIN_TEMP,
        native_max_value=MAX_TEMP,
        native_min_value_f=MIN_TEMP_F,
        native_max_value_f=MAX_TEMP_F,
        native_step=10,
        entity_category=EntityCategory.CONFIG,
    ),
    IronOSNumberEntityDescription(
        key=PinecilNumber.BOOST_TEMP,
        translation_key=PinecilNumber.BOOST_TEMP,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_fn=lambda _, settings: settings.get("boost_temp"),
        characteristic=CharSetting.BOOST_TEMP,
        mode=NumberMode.BOX,
        native_min_value=MIN_BOOST_TEMP,
        native_min_value_f=MIN_BOOST_TEMP_F,
        native_max_value=MAX_TEMP,
        native_max_value_f=MAX_TEMP_F,
        native_step=10,
        entity_category=EntityCategory.CONFIG,
    ),
    IronOSNumberEntityDescription(
        key=PinecilNumber.TEMP_INCREMENT_SHORT,
        translation_key=PinecilNumber.TEMP_INCREMENT_SHORT,
        value_fn=(lambda _, settings: settings.get("temp_increment_short")),
        characteristic=CharSetting.TEMP_INCREMENT_SHORT,
        raw_value_fn=lambda value: value,
        mode=NumberMode.BOX,
        native_min_value=1,
        native_max_value=50,
        native_step=1,
        entity_category=EntityCategory.CONFIG,
    ),
    IronOSNumberEntityDescription(
        key=PinecilNumber.TEMP_INCREMENT_LONG,
        translation_key=PinecilNumber.TEMP_INCREMENT_LONG,
        value_fn=(lambda _, settings: settings.get("temp_increment_long")),
        characteristic=CharSetting.TEMP_INCREMENT_LONG,
        raw_value_fn=lambda value: value,
        mode=NumberMode.BOX,
        native_min_value=5,
        native_max_value=90,
        native_step=5,
        entity_category=EntityCategory.CONFIG,
    ),
)

PINECIL_SETPOINT_NUMBER_DESCRIPTION = IronOSNumberEntityDescription(
    key=PinecilNumber.SETPOINT_TEMP,
    translation_key=PinecilNumber.SETPOINT_TEMP,
    native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    value_fn=lambda data, _: data.setpoint_temp,
    characteristic=CharSetting.SETPOINT_TEMP,
    mode=NumberMode.BOX,
    native_min_value=MIN_TEMP,
    native_max_value=MAX_TEMP,
    native_min_value_f=MIN_TEMP_F,
    native_max_value_f=MAX_TEMP_F,
    native_step=5,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: IronOSConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up number entities from a config entry."""
    coordinators = entry.runtime_data
    descriptions = PINECIL_NUMBER_DESCRIPTIONS

    if coordinators.live_data.v223_features:
        descriptions += PINECIL_NUMBER_DESCRIPTIONS_V223

    entities = [
        IronOSNumberEntity(coordinators, description) for description in descriptions
    ]

    entities.extend(
        IronOSTemperatureNumberEntity(coordinators, description)
        for description in PINECIL_TEMP_NUMBER_DESCRIPTIONS
    )
    entities.append(
        IronOSSetpointNumberEntity(coordinators, PINECIL_SETPOINT_NUMBER_DESCRIPTION)
    )
    async_add_entities(entities)


class IronOSNumberEntity(IronOSBaseEntity, NumberEntity):
    """Implementation of a IronOS number entity."""

    entity_description: IronOSNumberEntityDescription

    def __init__(
        self,
        coordinators: IronOSCoordinators,
        entity_description: IronOSNumberEntityDescription,
    ) -> None:
        """Initialize the number entity."""
        super().__init__(coordinators.live_data, entity_description)

        self.settings = coordinators.settings

    async def async_set_native_value(self, value: float) -> None:
        """Update the current value."""
        if raw_value_fn := self.entity_description.raw_value_fn:
            value = raw_value_fn(value)

        await self.settings.write(self.entity_description.characteristic, value)

    @property
    def native_value(self) -> float | int | None:
        """Return sensor state."""
        return self.entity_description.value_fn(
            self.coordinator.data, self.settings.data
        )

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added to hass."""

        await super().async_added_to_hass()
        self.async_on_remove(
            self.settings.async_add_listener(
                self._handle_coordinator_update, self.entity_description.characteristic
            )
        )
        await self.settings.async_request_refresh()


class IronOSTemperatureNumberEntity(IronOSNumberEntity):
    """Implementation of a IronOS temperature number entity."""

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return the unit of measurement of the sensor, if any."""

        return (
            UnitOfTemperature.FAHRENHEIT
            if self.settings.data.get("temp_unit") is TempUnit.FAHRENHEIT
            else UnitOfTemperature.CELSIUS
        )

    @property
    def native_min_value(self) -> float:
        """Return the minimum value."""

        return (
            self.entity_description.native_min_value_f
            if self.entity_description.native_min_value_f
            and self.native_unit_of_measurement is UnitOfTemperature.FAHRENHEIT
            else super().native_min_value
        )

    @property
    def native_max_value(self) -> float:
        """Return the maximum value."""

        return (
            self.entity_description.native_max_value_f
            if self.entity_description.native_max_value_f
            and self.native_unit_of_measurement is UnitOfTemperature.FAHRENHEIT
            else super().native_max_value
        )

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        if (
            self.entity_description.key is PinecilNumber.BOOST_TEMP
            and self.native_value == 0
        ):
            return False
        return super().available


class IronOSSetpointNumberEntity(IronOSTemperatureNumberEntity):
    """IronOS setpoint temperature entity."""

    @property
    def native_max_value(self) -> float:
        """Return the maximum value."""

        return (
            min(
                TemperatureConverter.convert(
                    float(max_tip_c),
                    UnitOfTemperature.CELSIUS,
                    self.native_unit_of_measurement,
                ),
                super().native_max_value,
            )
            if (max_tip_c := self.coordinator.data.max_tip_temp_ability) is not None
            else super().native_max_value
        )
