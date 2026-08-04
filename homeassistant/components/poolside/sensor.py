"""Sensor platform for Poolside site, body-of-water, and pool device telemetry."""

from collections.abc import Callable
import contextlib
from dataclasses import dataclass, replace
from datetime import datetime
import json
from typing import Any, override

from aiopoolside import (
    PoolsideClient,
    PoolsideControl,
    PoolsideDevice,
    PoolsideGroup,
    PoolsideSite,
)
from aiopoolside.const import (
    ACTUAL_POWER_STATE_FIELD,
    ACTUATOR_FRIENDLY_STATE_FIELD,
    ACTUATOR_POSITION_FIELD,
    BRIGHTNESS_FIELD,
    CALIBRATED_LEFT_TO_RIGHT_FIELD,
    CALIBRATED_RIGHT_TO_LEFT_FIELD,
    CURRENT_STATE_FIELD,
    CURRENT_TEMPERATURE_FIELD,
    FIELD_DISPLAY_NAME_KEY,
    FIELD_DISPLAY_ORDER_KEY,
    FIELD_NAME_KEY,
    FIELD_PROCESSING_LOGIC_KEY,
    FIELD_TYPES_KEY,
    FREEZE_PROTECT_REASON,
    INFORMATION_FIELD_TYPE,
    INFORMATION_FIELDS_FIELD,
    LIGHT_NAME_FIELD,
    POWER_STATE_FIELD,
    SPEED_FIELD,
    TWINKLE_FIELD,
    TWINKLE_INCREMENTS_FIELD,
    WINTERIZED_FIELD,
    WINTERIZED_REASON,
    ActuatorFriendlyState,
    BodyOfWaterState,
    SiteMode,
)

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    REVOLUTIONS_PER_MINUTE,
    EntityCategory,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfPower,
    UnitOfPressure,
    UnitOfRatio,
    UnitOfTemperature,
    UnitOfTime,
    UnitOfVolumeFlowRate,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from . import PoolsideConfigEntry
from .const import DOMAIN, LOGGER, SITE_MODE_KEY
from .entity import (
    PoolsideBaseEntity,
    PoolsideDeviceEntity,
    PoolsideEntity,
    PoolsideGroupEntity,
)


@dataclass(frozen=True, kw_only=True)
class PoolsideBodySensorDescription(SensorEntityDescription):
    """Describes a numeric telemetry field pushed under a body of water's UUID."""

    field: str


TEMPERATURE_SENSOR = PoolsideBodySensorDescription(
    key="temperature",
    field=CURRENT_TEMPERATURE_FIELD,
    device_class=SensorDeviceClass.TEMPERATURE,
    state_class=SensorStateClass.MEASUREMENT,
    # All temperatures on this wire are degrees Fahrenheit.
    native_unit_of_measurement=UnitOfTemperature.FAHRENHEIT,
)

# Water chemistry probes are optional equipment, so each of these is only
# added once its field is actually reported for the body of water.
CHEMISTRY_SENSORS = (
    PoolsideBodySensorDescription(
        key="orp",
        translation_key="orp",
        field="ORP",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricPotential.MILLIVOLT,
    ),
    PoolsideBodySensorDescription(
        key="ph",
        # Icon translation only; the name still comes from the device class.
        translation_key="ph",
        field="PH",
        device_class=SensorDeviceClass.PH,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    PoolsideBodySensorDescription(
        key="free_chlorine",
        translation_key="free_chlorine",
        field="FreeChlorine",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfRatio.PARTS_PER_MILLION,
    ),
    PoolsideBodySensorDescription(
        key="total_chlorine",
        translation_key="total_chlorine",
        field="TotalChlorine",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfRatio.PARTS_PER_MILLION,
    ),
    PoolsideBodySensorDescription(
        key="dissolved_oxygen_concentration",
        translation_key="dissolved_oxygen_concentration",
        field="DissolvedOxygenConcentration",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="mg/L",
    ),
    PoolsideBodySensorDescription(
        key="dissolved_oxygen_saturation",
        translation_key="dissolved_oxygen_saturation",
        field="DissolvedOxygenSaturation",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
    ),
    PoolsideBodySensorDescription(
        key="salt_level",
        translation_key="salt_level",
        field="SaltLevel",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfRatio.PARTS_PER_MILLION,
    ),
)


def _float_value(value: Any) -> float | None:
    """Coerce a telemetry value to a number, or None if it isn't one."""
    try:
        return float(value)
    except TypeError, ValueError:
        return None


def _string_value(value: Any) -> str:
    """Pass a telemetry value through as text."""
    return str(value)


def _on_off_value(value: Any) -> str | None:
    """Map an ONOFF value (ON/OFF/UNKNOWN strings or booleans) to its option.

    UNKNOWN (or anything unrecognized) is a "can't confirm" sentinel, not a
    real state, so it maps to no data.
    """
    if isinstance(value, bool):
        return "on" if value else "off"
    text = str(value).strip().upper()
    if text == "ON":
        return "on"
    if text == "OFF":
        return "off"
    return None


def _bool_value(value: Any) -> bool | None:
    """Coerce a BOOLEAN value (booleans or true/false strings) to a bool."""
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in ("true", "yes"):
        return True
    if text in ("false", "no"):
        return False
    return None


def _yes_no_value(value: Any) -> str | None:
    """Map a BOOLEAN value (booleans or true/false strings) to yes/no."""
    if (result := _bool_value(value)) is None:
        return None
    return "yes" if result else "no"


def _actuator_state_value(value: Any) -> str | None:
    """Map a FriendlyState value to its option, or None if unrecognized."""
    try:
        return ActuatorFriendlyState(str(value).strip().upper()).value.lower()
    except ValueError:
        return None


def _position_percent_value(value: Any) -> float | None:
    """Coerce a position percentage, treating out-of-range values as no data."""
    number = _float_value(value)
    if number is None or not 0 <= number <= 100:
        return None
    return number


def _datetime_value(value: Any) -> datetime | None:
    """Parse an ISO datetime, tolerating double-JSON-encoded values.

    Pump's PrimingUntil arrives as a JSON string encoded inside the string
    value ('"2026-..."'), so one layer of quoting is stripped first.
    """
    if isinstance(value, str) and value.startswith('"'):
        with contextlib.suppress(ValueError):
            value = json.loads(value)
    parsed = dt_util.parse_datetime(str(value))
    if parsed is not None and parsed.tzinfo is None:
        # Naive timestamps are in the controller's (= HA's) local time.
        parsed = parsed.replace(tzinfo=dt_util.get_default_time_zone())
    return parsed


@dataclass(frozen=True, kw_only=True)
class PoolsideFieldSensorDescription(SensorEntityDescription):
    """Describes how one DisplayProcessingLogic renders as a sensor."""

    value_fn: Callable[[Any], float | str | datetime | None] = _string_value


ON_OFF_OPTIONS = ["on", "off"]

# One template per DisplayProcessingLogic value, matching how the vendor UI
# renders each; the per-field description is the template re-keyed to the
# field's Name. Unlisted logics (STRING, LONG_STRING, and any new
# controller-side additions) render as plain text, so they degrade
# gracefully instead of being dropped.
PROCESSING_LOGIC_DESCRIPTIONS: dict[str, PoolsideFieldSensorDescription] = {
    "ONOFF": PoolsideFieldSensorDescription(
        key="ONOFF",
        device_class=SensorDeviceClass.ENUM,
        options=ON_OFF_OPTIONS,
        value_fn=_on_off_value,
    ),
    "TEMP_F": PoolsideFieldSensorDescription(
        key="TEMP_F",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.FAHRENHEIT,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_float_value,
    ),
    "GPM": PoolsideFieldSensorDescription(
        key="GPM",
        device_class=SensorDeviceClass.VOLUME_FLOW_RATE,
        native_unit_of_measurement=UnitOfVolumeFlowRate.GALLONS_PER_MINUTE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_float_value,
    ),
    "PSI": PoolsideFieldSensorDescription(
        key="PSI",
        device_class=SensorDeviceClass.PRESSURE,
        native_unit_of_measurement=UnitOfPressure.PSI,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_float_value,
    ),
    "PERCENT": PoolsideFieldSensorDescription(
        key="PERCENT",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_float_value,
    ),
    "MG_L": PoolsideFieldSensorDescription(
        key="MG_L",
        native_unit_of_measurement="mg/L",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        value_fn=_float_value,
    ),
    "PPM": PoolsideFieldSensorDescription(
        key="PPM",
        native_unit_of_measurement=UnitOfRatio.PARTS_PER_MILLION,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=3,
        value_fn=_float_value,
    ),
    "WATTAGE": PoolsideFieldSensorDescription(
        key="WATTAGE",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_float_value,
    ),
    "RPM": PoolsideFieldSensorDescription(
        key="RPM",
        native_unit_of_measurement=REVOLUTIONS_PER_MINUTE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_float_value,
    ),
    "AMP": PoolsideFieldSensorDescription(
        key="AMP",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_float_value,
    ),
    "UA": PoolsideFieldSensorDescription(
        key="UA",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.MICROAMPERE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_float_value,
    ),
    "MV": PoolsideFieldSensorDescription(
        key="MV",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.MILLIVOLT,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_float_value,
    ),
    "VOLT": PoolsideFieldSensorDescription(
        key="VOLT",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_float_value,
    ),
    "MS_TO_S": PoolsideFieldSensorDescription(
        key="MS_TO_S",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MILLISECONDS,
        suggested_unit_of_measurement=UnitOfTime.SECONDS,
        suggested_display_precision=0,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_float_value,
    ),
    "DATETIME": PoolsideFieldSensorDescription(
        key="DATETIME",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=_datetime_value,
    ),
    "BOOLEAN": PoolsideFieldSensorDescription(
        key="BOOLEAN",
        device_class=SensorDeviceClass.ENUM,
        options=["yes", "no"],
        value_fn=_yes_no_value,
    ),
    "FLOAT": PoolsideFieldSensorDescription(
        key="FLOAT",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_float_value,
    ),
    "INTEGER": PoolsideFieldSensorDescription(
        key="INTEGER",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        value_fn=_float_value,
    ),
    "X": PoolsideFieldSensorDescription(
        key="X",
        native_unit_of_measurement="x",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_float_value,
    ),
    "ACTUATOR_FRIENDLY_STATE": PoolsideFieldSensorDescription(
        key="ACTUATOR_FRIENDLY_STATE",
        translation_key="actuator_state",
        device_class=SensorDeviceClass.ENUM,
        options=[state.value.lower() for state in ActuatorFriendlyState],
        value_fn=_actuator_state_value,
    ),
    "ACTUATOR_POSITION": PoolsideFieldSensorDescription(
        key="ACTUATOR_POSITION",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        value_fn=_position_percent_value,
    ),
}

DEFAULT_FIELD_DESCRIPTION = PoolsideFieldSensorDescription(key="STRING")

TWINKLE_PROCESSING_LOGIC = "TWINKLE"

# Supporting states referenced by other fields' rendering, never shown as
# sensors of their own even when a descriptor marks them INFORMATION.
HIDDEN_INFORMATION_FIELDS = {TWINKLE_INCREMENTS_FIELD}

# Light pool devices never publish an InformationFields document - the
# vendor app hardcodes their screen - so an equivalent fixed field set is
# synthesized for them instead.
LIGHT_DEVICE_FIELDS: list[dict[str, Any]] = [
    {
        FIELD_NAME_KEY: POWER_STATE_FIELD,
        FIELD_DISPLAY_NAME_KEY: "Power",
        FIELD_PROCESSING_LOGIC_KEY: "ONOFF",
    },
    {
        FIELD_NAME_KEY: LIGHT_NAME_FIELD,
        FIELD_DISPLAY_NAME_KEY: "Show",
        FIELD_PROCESSING_LOGIC_KEY: "LIGHT_NAME",
    },
    {
        FIELD_NAME_KEY: BRIGHTNESS_FIELD,
        FIELD_DISPLAY_NAME_KEY: "Brightness",
        FIELD_PROCESSING_LOGIC_KEY: "PERCENT",
    },
    {
        FIELD_NAME_KEY: SPEED_FIELD,
        FIELD_DISPLAY_NAME_KEY: "Speed",
        FIELD_PROCESSING_LOGIC_KEY: "X",
    },
    {
        FIELD_NAME_KEY: TWINKLE_FIELD,
        FIELD_DISPLAY_NAME_KEY: "Twinkle",
        FIELD_PROCESSING_LOGIC_KEY: TWINKLE_PROCESSING_LOGIC,
    },
]

# Actuator pool devices always carry their headline state and position,
# whether or not they publish an InformationFields document.
ACTUATOR_DEVICE_FIELDS: list[dict[str, Any]] = [
    {
        FIELD_NAME_KEY: ACTUATOR_FRIENDLY_STATE_FIELD,
        FIELD_DISPLAY_NAME_KEY: "State",
        FIELD_PROCESSING_LOGIC_KEY: "ACTUATOR_FRIENDLY_STATE",
    },
    {
        FIELD_NAME_KEY: ACTUATOR_POSITION_FIELD,
        FIELD_DISPLAY_NAME_KEY: "Position",
        FIELD_PROCESSING_LOGIC_KEY: "ACTUATOR_POSITION",
    },
]

# Shown for an actuator that publishes no InformationFields document; a
# published document takes its place, like the vendor screen's fallback list.
ACTUATOR_FALLBACK_FIELDS: list[dict[str, Any]] = [
    {
        FIELD_NAME_KEY: CALIBRATED_LEFT_TO_RIGHT_FIELD,
        FIELD_DISPLAY_NAME_KEY: "Calibration left to right",
        FIELD_PROCESSING_LOGIC_KEY: "MS_TO_S",
    },
    {
        FIELD_NAME_KEY: CALIBRATED_RIGHT_TO_LEFT_FIELD,
        FIELD_DISPLAY_NAME_KEY: "Calibration right to left",
        FIELD_PROCESSING_LOGIC_KEY: "MS_TO_S",
    },
]


def _device_field_description(field: dict[str, Any]) -> PoolsideFieldSensorDescription:
    """Build the sensor description for one InformationFields entry."""
    logic = str(field.get(FIELD_PROCESSING_LOGIC_KEY) or "")
    template = PROCESSING_LOGIC_DESCRIPTIONS.get(logic, DEFAULT_FIELD_DESCRIPTION)
    return replace(template, key=field[FIELD_NAME_KEY])


def _information_fields(
    client: PoolsideClient, device: PoolsideDevice
) -> list[dict[str, Any]]:
    """Return a pool device's telemetry field descriptors, in display order.

    The InformationFields document is a JSON list (possibly encoded inside a
    string, like other capability documents) pushed under the device's UUID.
    Entries without the INFORMATION field type aren't telemetry and are
    skipped.
    """
    value = client.get_status(device.uuid, INFORMATION_FIELDS_FIELD)
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except ValueError:
            LOGGER.warning(
                "%s: unparsable %s: %r", device.uuid, INFORMATION_FIELDS_FIELD, value
            )
            return []
    if not isinstance(value, list):
        return []
    fields = [
        field
        for field in value
        if isinstance(field, dict)
        and field.get(FIELD_NAME_KEY)
        and field.get(FIELD_NAME_KEY) not in HIDDEN_INFORMATION_FIELDS
        and INFORMATION_FIELD_TYPE in (field.get(FIELD_TYPES_KEY) or [])
    ]
    fields.sort(key=lambda field: field.get(FIELD_DISPLAY_ORDER_KEY) or 0)
    return fields


def _device_fields(
    client: PoolsideClient, device: PoolsideDevice
) -> list[dict[str, Any]]:
    """Return a pool device's telemetry field descriptors.

    Light devices never publish InformationFields, so their fixed vendor
    screen layout is used instead. Actuators always carry their state and
    position fields, plus their published InformationFields document or the
    fixed fallback list when there is none. Every other device type is
    described by its InformationFields document alone.
    """
    if device.is_light:
        return LIGHT_DEVICE_FIELDS
    if device.is_actuator:
        return ACTUATOR_DEVICE_FIELDS + (
            _information_fields(client, device) or ACTUATOR_FALLBACK_FIELDS
        )
    return _information_fields(client, device)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PoolsideConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up sensors per body of water, per pool device, and the site mode sensor.

    Every body gets a temperature sensor. Chemistry sensors are added the
    first time their field is reported - usually straight from the initial
    status snapshot, otherwise on a later push - since probes are optional
    equipment a body may simply not have. Pool device sensors follow the
    same pattern, keyed on the device's InformationFields document - except
    for light devices, whose fixed field set never waits on a descriptor.
    """
    data = entry.runtime_data
    client = data.client
    groups = {control.group.uuid: control.group for control in data.controls}
    bodies = [
        (group, body_of_water_uuid)
        for group in groups.values()
        if (body_of_water_uuid := group.body_of_water_uuid) is not None
    ]

    entities: list[SensorEntity] = []
    for group, body_of_water_uuid in bodies:
        entities.append(
            PoolsideBodySensor(client, group, body_of_water_uuid, TEMPERATURE_SENSOR)
        )
        entities.append(PoolsideBodyStateSensor(client, group, body_of_water_uuid))
    entities.extend(
        PoolsideControlDisabledReasonSensor(client, control)
        for control in data.controls
    )
    # ActualPowerState and Winterized are pushed for every pool device
    # regardless of what its InformationFields document lists, so their
    # sensors are created eagerly. Actuators are the exception: they are not
    # on/off-able and report no power state at all.
    entities.extend(
        PoolsideDevicePowerSensor(client, device)
        for device in data.pool_devices
        if not device.is_actuator
    )
    entities.extend(
        PoolsideDeviceWinterizedSensor(client, device) for device in data.pool_devices
    )
    if (site_uuid := data.site.uuid) is not None:
        entities.append(PoolsideSiteModeSensor(client, data.site, site_uuid))
    async_add_entities(entities)

    added: set[str] = set()

    @callback
    def _async_add_reported_chemistry() -> None:
        new_entities: list[PoolsideBodySensor] = []
        for group, body_of_water_uuid in bodies:
            for description in CHEMISTRY_SENSORS:
                added_key = f"{body_of_water_uuid}_{description.key}"
                if (
                    added_key in added
                    or client.get_status(body_of_water_uuid, description.field) is None
                ):
                    continue
                added.add(added_key)
                new_entities.append(
                    PoolsideBodySensor(client, group, body_of_water_uuid, description)
                )
        if new_entities:
            async_add_entities(new_entities)

    _async_add_reported_chemistry()
    for _group, body_of_water_uuid in bodies:
        entry.async_on_unload(
            client.subscribe_status(body_of_water_uuid, _async_add_reported_chemistry)
        )

    # Pre-seeded so a descriptor that lists ActualPowerState or Winterized
    # itself doesn't collide with the dedicated sensors created above.
    added_device_fields: set[str] = {
        f"{device.uuid}_{dedicated_field}"
        for device in data.pool_devices
        for dedicated_field in (ACTUAL_POWER_STATE_FIELD, WINTERIZED_FIELD)
    }

    @callback
    def _async_add_described_device_sensors() -> None:
        new_entities: list[PoolsideDeviceSensor] = []
        for device in data.pool_devices:
            for field in _device_fields(client, device):
                added_key = f"{device.uuid}_{field[FIELD_NAME_KEY]}"
                if added_key in added_device_fields:
                    continue
                added_device_fields.add(added_key)
                sensor_cls = (
                    PoolsideDeviceTwinkleSensor
                    if field.get(FIELD_PROCESSING_LOGIC_KEY) == TWINKLE_PROCESSING_LOGIC
                    else PoolsideDeviceSensor
                )
                new_entities.append(sensor_cls(client, device, field))
        if new_entities:
            async_add_entities(new_entities)

    _async_add_described_device_sensors()
    for device in data.pool_devices:
        entry.async_on_unload(
            client.subscribe_status(device.uuid, _async_add_described_device_sensors)
        )


class PoolsideBodySensor(PoolsideGroupEntity, SensorEntity):
    """A numeric telemetry value for a body of water.

    Confirmed telemetry pushed by the controller, keyed by the group's
    BodyOfWaterUUID rather than any control's UUID.
    """

    entity_description: PoolsideBodySensorDescription

    def __init__(
        self,
        client: PoolsideClient,
        group: PoolsideGroup,
        body_of_water_uuid: str,
        description: PoolsideBodySensorDescription,
    ) -> None:
        """Set up one telemetry sensor for a given body of water."""
        super().__init__(client, group)
        self.entity_description = description
        self._body_of_water_uuid = body_of_water_uuid
        self._attr_unique_id = (
            f"{client.controller_uuid}_{body_of_water_uuid}_{description.key}"
        )

    @override
    def _status_keys(self) -> set[str]:
        """Return the body-of-water key its telemetry arrives under."""
        return {self._body_of_water_uuid}

    @property
    @override
    def native_value(self) -> float | None:
        """Return the last reported value."""
        value = self._client.get_status(
            self._body_of_water_uuid, self.entity_description.field
        )
        return None if value is None else float(value)


class PoolsideBodyStateSensor(PoolsideGroupEntity, SensorEntity):
    """A body of water's overall FRIENDLY_STATE (its CurrentState field)."""

    _attr_device_class = SensorDeviceClass.ENUM
    _attr_translation_key = "current_state"
    _attr_options = [state.value.lower() for state in BodyOfWaterState]

    def __init__(
        self, client: PoolsideClient, group: PoolsideGroup, body_of_water_uuid: str
    ) -> None:
        """Set up the state sensor for a given body of water."""
        super().__init__(client, group)
        self._body_of_water_uuid = body_of_water_uuid
        self._attr_unique_id = (
            f"{client.controller_uuid}_{body_of_water_uuid}_current_state"
        )

    @override
    def _status_keys(self) -> set[str]:
        """Return the body-of-water key its state arrives under."""
        return {self._body_of_water_uuid}

    @property
    @override
    def native_value(self) -> str | None:
        """Return the body of water's last reported state."""
        value = self._client.get_status(self._body_of_water_uuid, CURRENT_STATE_FIELD)
        if value is None:
            return None
        try:
            return BodyOfWaterState(value).value.lower()
        except ValueError:
            return None


class PoolsideDeviceSensor(PoolsideDeviceEntity, SensorEntity):
    """One telemetry field of a physical pool device.

    Synthesized from the device's InformationFields descriptor rather than a
    fixed catalog: the descriptor names the status field and how to render
    it, and the value itself streams in under the device's UUID.
    """

    entity_description: PoolsideFieldSensorDescription

    def __init__(
        self, client: PoolsideClient, device: PoolsideDevice, field: dict[str, Any]
    ) -> None:
        """Set up one telemetry sensor from its InformationFields entry."""
        super().__init__(client, device)
        field_name: str = field[FIELD_NAME_KEY]
        self.entity_description = _device_field_description(field)
        self._attr_name = str(field.get(FIELD_DISPLAY_NAME_KEY) or field_name)
        self._attr_unique_id = f"{client.controller_uuid}_{device.uuid}_{field_name}"

    @property
    @override
    def native_value(self) -> float | str | datetime | None:
        """Return the last reported value, coerced per the field's processing logic."""
        value = self._client.get_status(self._device.uuid, self.entity_description.key)
        if value is None:
            return None
        return self.entity_description.value_fn(value)


class PoolsideDeviceTwinkleSensor(PoolsideDeviceSensor):
    """A TWINKLE field, translated through the device's TwinkleIncrements state.

    The raw Twinkle value is an increment the device's TwinkleIncrements
    document (a JSON array of {value, description} entries) gives a display
    name; a value the document doesn't list - or a missing/unparsable
    document - degrades to the raw value as text.
    """

    @property
    @override
    def native_value(self) -> str | None:
        """Return the increment's description, or the raw value as text."""
        value = self._client.get_status(self._device.uuid, self.entity_description.key)
        if value is None:
            return None
        return self._increment_description(value) or str(value)

    def _increment_description(self, value: Any) -> str | None:
        """Look the raw value up in the device's TwinkleIncrements document."""
        increments = self._client.get_status(
            self._device.uuid, TWINKLE_INCREMENTS_FIELD
        )
        if isinstance(increments, str):
            try:
                increments = json.loads(increments)
            except ValueError:
                LOGGER.warning(
                    "%s: unparsable %s: %r",
                    self._device.uuid,
                    TWINKLE_INCREMENTS_FIELD,
                    increments,
                )
                return None
        if not isinstance(increments, list):
            return None
        number = _float_value(value)
        for item in increments:
            if not isinstance(item, dict) or "description" not in item:
                continue
            candidate = item.get("value")
            if str(candidate) == str(value) or (
                number is not None and _float_value(candidate) == number
            ):
                return str(item["description"])
        return None


class PoolsideDevicePowerSensor(PoolsideDeviceEntity, SensorEntity):
    """Whether a physical pool device is actually running.

    ActualPowerState is ground truth from the hardware, pushed for every
    pool device independent of its InformationFields document, so this
    sensor exists from setup rather than waiting on the descriptor.
    """

    _attr_device_class = SensorDeviceClass.ENUM
    _attr_translation_key = "actual_power_state"
    _attr_options = ON_OFF_OPTIONS

    def __init__(self, client: PoolsideClient, device: PoolsideDevice) -> None:
        """Set up the power state sensor for a pool device."""
        super().__init__(client, device)
        self._attr_unique_id = (
            f"{client.controller_uuid}_{device.uuid}_{ACTUAL_POWER_STATE_FIELD}"
        )

    @property
    @override
    def native_value(self) -> str | None:
        """Return on/off ground truth; UNKNOWN means the hardware can't confirm."""
        value = self._client.get_status(self._device.uuid, ACTUAL_POWER_STATE_FIELD)
        if value is None:
            return None
        return _on_off_value(value)


class PoolsideDeviceWinterizedSensor(PoolsideDeviceEntity, SensorEntity):
    """Whether a physical pool device has been taken offline for the season.

    Winterized is pushed for every pool device independent of its
    InformationFields document, so this sensor exists from setup rather
    than waiting on the descriptor.
    """

    _attr_device_class = SensorDeviceClass.ENUM
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_translation_key = "winterized"
    _attr_options = ["true", "false"]

    def __init__(self, client: PoolsideClient, device: PoolsideDevice) -> None:
        """Set up the winterized sensor for a pool device."""
        super().__init__(client, device)
        self._attr_unique_id = (
            f"{client.controller_uuid}_{device.uuid}_{WINTERIZED_FIELD}"
        )

    @property
    @override
    def native_value(self) -> str | None:
        """Return true/false, or no data if the field is absent or malformed."""
        value = self._client.get_status(self._device.uuid, WINTERIZED_FIELD)
        if (winterized := _bool_value(value)) is None:
            return None
        return "true" if winterized else "false"


class PoolsideControlDisabledReasonSensor(PoolsideEntity, SensorEntity):
    """Why a control is out of service, or none while it is operable.

    Deliberately NOT gated on the control's own availability - it exists to
    explain why the control's entity went unavailable, so it only follows
    the connection. Site-wide INSTALLER mode is explained by the site mode
    sensor instead, and covers every control at once, so it isn't repeated
    here.
    """

    _attr_device_class = SensorDeviceClass.ENUM
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_translation_key = "disabled_reason"
    _attr_options = ["none", "winterized", "freeze_protect", "pool_cover"]
    _use_translated_name = True

    def __init__(self, client: PoolsideClient, control: PoolsideControl) -> None:
        """Set up the disabled reason sensor for a control."""
        super().__init__(client, control)
        self._attr_unique_id = (
            f"{client.controller_uuid}_{control.uuid}_disabled_reason"
        )
        self._attr_translation_placeholders = {"control_name": control.name}

    @property
    @override
    def available(self) -> bool:
        """Return True while connected, regardless of the control's own state."""
        return self._client.available

    @property
    @override
    def native_value(self) -> str:
        """Return the strongest reason the control is out of service."""
        reasons = self._disabled_reasons()
        if self._control.winterized or WINTERIZED_REASON in reasons:
            return "winterized"
        if FREEZE_PROTECT_REASON in reasons:
            return "freeze_protect"
        if reasons:
            return "pool_cover"
        return "none"


class PoolsideSiteModeSensor(PoolsideBaseEntity, SensorEntity):
    """The controller's site-wide operating mode.

    Read-only: the mode is changed on the controller itself (or by an
    installer), never from Home Assistant. Deliberately NOT gated on the
    mode itself - it must stay readable in INSTALLER mode so the user can
    see why all their controls are unavailable.
    """

    _attr_device_class = SensorDeviceClass.ENUM
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_translation_key = "site_mode"
    _attr_options = [mode.value.lower() for mode in SiteMode]

    def __init__(
        self, client: PoolsideClient, site: PoolsideSite, site_uuid: str
    ) -> None:
        """Set up the mode sensor on its own controller-level device."""
        super().__init__(client)
        self._site_uuid = site_uuid
        self._attr_unique_id = f"{client.controller_uuid}_{SITE_MODE_KEY}"
        # Keyed by the stable controller UUID, not the site UUID, which
        # changes whenever the attendant edits the site's configuration.
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, client.controller_uuid)},
            name=site.name,
            manufacturer="Poolside",
            model="Controller",
        )

    @override
    def _status_keys(self) -> set[str]:
        """Return the site key its Mode pushes arrive under."""
        return {self._site_uuid}

    @property
    @override
    def native_value(self) -> str | None:
        """Return the last reported site mode."""
        if (value := self._client.site_mode) is None:
            return None
        try:
            return SiteMode(value).value.lower()
        except ValueError:
            return None
