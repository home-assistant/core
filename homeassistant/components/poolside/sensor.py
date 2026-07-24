"""Sensor platform for Poolside site, body-of-water, and pool device telemetry."""

from dataclasses import dataclass
from datetime import datetime
import json
from typing import Any, override

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
    UnitOfElectricPotential,
    UnitOfPower,
    UnitOfPressure,
    UnitOfRatio,
    UnitOfTemperature,
    UnitOfVolumeFlowRate,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from . import PoolsideConfigEntry
from .client import PoolsideClient
from .const import (
    CURRENT_STATE_FIELD,
    CURRENT_TEMPERATURE_FIELD,
    DOMAIN,
    FIELD_DISPLAY_NAME_KEY,
    FIELD_DISPLAY_ORDER_KEY,
    FIELD_NAME_KEY,
    FIELD_PROCESSING_LOGIC_KEY,
    FIELD_TYPES_KEY,
    INFORMATION_FIELD_TYPE,
    INFORMATION_FIELDS_FIELD,
    LOGGER,
    SITE_MODE_KEY,
    BodyOfWaterState,
    SiteMode,
)
from .entity import PoolsideBaseEntity, PoolsideDeviceEntity, PoolsideGroupEntity
from .models import PoolsideDevice, PoolsideGroup, PoolsideSite


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


# DisplayProcessingLogic values that mark numeric telemetry, mapped to the
# device class and unit they render with.
NUMERIC_PROCESSING_LOGIC: dict[str, tuple[SensorDeviceClass | None, str | None]] = {
    "WATTAGE": (SensorDeviceClass.POWER, UnitOfPower.WATT),
    "RPM": (None, REVOLUTIONS_PER_MINUTE),
    "GPM": (
        SensorDeviceClass.VOLUME_FLOW_RATE,
        UnitOfVolumeFlowRate.GALLONS_PER_MINUTE,
    ),
    "PSI": (SensorDeviceClass.PRESSURE, UnitOfPressure.PSI),
}

DATETIME_PROCESSING_LOGIC = "DATETIME"


def _device_field_description(field: dict[str, Any]) -> SensorEntityDescription:
    """Build the sensor description for one InformationFields entry.

    LONG_STRING and any processing logic this integration doesn't recognize
    render as plain text, so new controller-side field types degrade
    gracefully instead of being dropped.
    """
    name: str = field[FIELD_NAME_KEY]
    logic = field.get(FIELD_PROCESSING_LOGIC_KEY)
    if logic in NUMERIC_PROCESSING_LOGIC:
        device_class, unit = NUMERIC_PROCESSING_LOGIC[logic]
        return SensorEntityDescription(
            key=name,
            device_class=device_class,
            native_unit_of_measurement=unit,
            state_class=SensorStateClass.MEASUREMENT,
        )
    if logic == DATETIME_PROCESSING_LOGIC:
        return SensorEntityDescription(
            key=name, device_class=SensorDeviceClass.TIMESTAMP
        )
    return SensorEntityDescription(key=name)


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
        and INFORMATION_FIELD_TYPE in (field.get(FIELD_TYPES_KEY) or [])
    ]
    fields.sort(key=lambda field: field.get(FIELD_DISPLAY_ORDER_KEY) or 0)
    return fields


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
    same pattern, keyed on the device's InformationFields document.
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

    added_device_fields: set[str] = set()

    @callback
    def _async_add_described_device_sensors() -> None:
        new_entities: list[PoolsideDeviceSensor] = []
        for device in data.pool_devices:
            for field in _information_fields(client, device):
                added_key = f"{device.uuid}_{field[FIELD_NAME_KEY]}"
                if added_key in added_device_fields:
                    continue
                added_device_fields.add(added_key)
                new_entities.append(PoolsideDeviceSensor(client, device, field))
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
        if self.entity_description.device_class is SensorDeviceClass.TIMESTAMP:
            parsed = dt_util.parse_datetime(str(value))
            if parsed is not None and parsed.tzinfo is None:
                # Naive timestamps are in the controller's (= HA's) local time.
                parsed = parsed.replace(tzinfo=dt_util.get_default_time_zone())
            return parsed
        if self.entity_description.state_class is SensorStateClass.MEASUREMENT:
            try:
                return float(value)
            except TypeError, ValueError:
                return None
        return str(value)


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
