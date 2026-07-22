"""Sensor platform for Poolside site and body-of-water telemetry."""

from dataclasses import dataclass
from typing import override

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    EntityCategory,
    UnitOfElectricPotential,
    UnitOfRatio,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import PoolsideConfigEntry
from .client import PoolsideClient
from .const import (
    CURRENT_STATE_FIELD,
    CURRENT_TEMPERATURE_FIELD,
    DOMAIN,
    SITE_MODE_KEY,
    BodyOfWaterState,
    SiteMode,
)
from .entity import PoolsideBaseEntity, PoolsideGroupEntity
from .models import PoolsideGroup, PoolsideSite


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


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PoolsideConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up sensors per body of water plus the site mode sensor.

    Every body gets a temperature sensor. Chemistry sensors are added the
    first time their field is reported - usually straight from the initial
    status snapshot, otherwise on a later push - since probes are optional
    equipment a body may simply not have.
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
