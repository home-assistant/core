"""Platform for sensor integration."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, override

from habitron_client import BusMember, Logic, Module

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    LIGHT_LUX,
    PERCENTAGE,
    EntityCategory,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfFrequency,
    UnitOfSpeed,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import area_registry as ar, entity_registry as er
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import HabitronConfigEntry, HbtnCoordinator

PARALLEL_UPDATES = 0
TYPE_DIAG = 10  # diagnostic entity, hidden by default (was interfaces.TYPE_DIAG)

# Stable, language-independent enum keys ordered by the hub's raw finger value
# (1..10). Localized labels live in strings.json under
# ``entity.sensor.ekey_finger_name.state`` — the state itself carries no display
# text.
_FINGER_KEYS: tuple[str, ...] = (
    "left_pinky",
    "left_ring",
    "left_middle",
    "left_index",
    "left_thumb",
    "right_thumb",
    "right_index",
    "right_middle",
    "right_ring",
    "right_pinky",
)


def _device_info(uid: str) -> DeviceInfo:
    """Link an entity to its Habitron module device via ``(DOMAIN, uid)``."""
    return DeviceInfo(identifiers={(DOMAIN, uid)})


def _ekey_user_value(module: Any, idx: int) -> str:
    """Translate a raw ekey identifier value into a user-name string."""
    id_val = int(module.sensors[idx].value or 0)
    if id_val == 0:
        return "None"
    if id_val == 255:
        return "Error"
    if (id_val - 1) in range(len(module.ids)):
        return str(module.ids[id_val - 1].name)
    if (abs(id_val) - 1) in range(len(module.ids)):
        return str(module.ids[abs(id_val) - 1].name) + "-disabled"
    return "Unknown"


def _ekey_finger_value(module: Any, idx: int) -> str | None:
    """Translate a raw ekey finger value into a stable finger-key string."""
    id_val = int(module.sensors[idx].value or 0)
    if id_val in range(1, 11):
        return _FINGER_KEYS[id_val - 1]
    # 0 (idle), 255 (error) or out of range → no current finger.
    return None


async def async_setup_entry(  # noqa: C901
    hass: HomeAssistant,
    entry: HabitronConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add sensors for passed config_entry in HA."""
    hbtn_cord = entry.runtime_data
    smhub = hbtn_cord.smart_hub
    hbtn_rt = smhub.router

    registry = er.async_get(hass)
    area_reg = ar.async_get(hass)
    # Map each bus area number to its HA area-registry id (creating the area on
    # first sight). Used to place analog inputs whose area deviates from their
    # module's area (see below).
    area_ids = {a.nmbr: area_reg.async_get_or_create(a.name).id for a in hbtn_rt.areas}

    # Analog inputs may be assigned an area that deviates from their module's
    # area. HA has no per-entity ``suggested_area``, so the only way to honour
    # this is the entity registry. We apply the hub's area once, when the entity
    # is first created, and never on a reload -- overwriting on every reload
    # would clobber a user's manual area move. Collected here, applied after the
    # entities are added.
    pending_areas: list[tuple[str, str]] = []

    new_devices: list[SensorEntity] = []
    for smhub_sensor in smhub.sensors:
        if smhub_sensor.name == "Memory free":
            new_devices.append(
                HbtnDescribedSensor(
                    smhub, smhub_sensor, hbtn_cord, len(new_devices), MEMORY_DESCRIPTION
                )
            )
        if smhub_sensor.name == "Disk free":
            new_devices.append(
                HbtnDescribedSensor(
                    smhub, smhub_sensor, hbtn_cord, len(new_devices), DISK_DESCRIPTION
                )
            )
    for smhub_diag in smhub.diags:
        if smhub_diag.name == "CPU Frequency":
            new_devices.append(
                HbtnDescribedSensor(
                    smhub,
                    smhub_diag,
                    hbtn_cord,
                    len(new_devices),
                    CPU_FREQUENCY_DESCRIPTION,
                )
            )
        if smhub_diag.name == "CPU load":
            new_devices.append(
                HbtnDescribedSensor(
                    smhub, smhub_diag, hbtn_cord, len(new_devices), CPU_LOAD_DESCRIPTION
                )
            )
        if smhub_diag.name == "CPU Temperature":
            new_devices.append(
                HbtnDescribedSensor(
                    smhub,
                    smhub_diag,
                    hbtn_cord,
                    len(new_devices),
                    CPU_TEMPERATURE_DESCRIPTION,
                )
            )

    # --- Module Iteration ---
    for hbt_module in hbtn_rt.modules:
        if hbt_module.typ in [b"\x01\x03", b"\x0b\x1f"]:
            for ain in hbt_module.analogins:
                if ain.type == 3:
                    analog = HbtnDescribedSensor(
                        hbt_module,
                        ain,
                        hbtn_cord,
                        len(new_devices),
                        ANALOG_DESCRIPTION,
                    )
                    new_devices.append(analog)
                    # ain.area == 0 means "the module's own area"; only a value
                    # that differs from the module's area is a real deviation.
                    if (
                        ain.area not in (0, hbt_module.area)
                        and ain.area in area_ids
                        and (unique_id := analog.unique_id) is not None
                    ):
                        pending_areas.append((unique_id, area_ids[ain.area]))
        for mod_sensor in hbt_module.sensors:
            if mod_sensor.name[0:11] == "Temperature":
                # The external probe is disabled by default; the two descriptions
                # differ only in entity_registry_enabled_default.
                temp_description = (
                    TEMP_EXT_DESCRIPTION
                    if mod_sensor.name == "Temperature ext."
                    else TEMP_DESCRIPTION
                )
                new_devices.append(
                    HbtnDescribedSensor(
                        hbt_module,
                        mod_sensor,
                        hbtn_cord,
                        len(new_devices),
                        temp_description,
                    )
                )
            elif mod_sensor.name == "Humidity":
                new_devices.append(
                    HbtnDescribedSensor(
                        hbt_module,
                        mod_sensor,
                        hbtn_cord,
                        len(new_devices),
                        HUMIDITY_DESCRIPTION,
                    )
                )
            elif mod_sensor.name == "Illuminance":
                new_devices.append(
                    HbtnDescribedSensor(
                        hbt_module,
                        mod_sensor,
                        hbtn_cord,
                        len(new_devices),
                        ILLUMINANCE_DESCRIPTION,
                    )
                )
            elif mod_sensor.name in ("Wind", "Windpeak"):
                new_devices.append(
                    HbtnDescribedSensor(
                        hbt_module,
                        mod_sensor,
                        hbtn_cord,
                        len(new_devices),
                        WIND_DESCRIPTION,
                    )
                )
            elif mod_sensor.name == "Airquality":
                new_devices.append(
                    HbtnDescribedSensor(
                        hbt_module,
                        mod_sensor,
                        hbtn_cord,
                        len(new_devices),
                        AIRQUALITY_DESCRIPTION,
                    )
                )
            elif mod_sensor.name == "Identifier":
                new_devices.append(
                    HbtnDescribedSensor(
                        hbt_module,
                        mod_sensor,
                        hbtn_cord,
                        len(new_devices),
                        EKEY_ID_DESCRIPTION,
                    )
                )
                new_devices.append(
                    HbtnDescribedSensor(
                        hbt_module,
                        mod_sensor,
                        hbtn_cord,
                        len(new_devices),
                        EKEY_USER_NAME_DESCRIPTION,
                    )
                )
            elif mod_sensor.name == "Finger":
                new_devices.append(
                    HbtnDescribedSensor(
                        hbt_module,
                        mod_sensor,
                        hbtn_cord,
                        len(new_devices),
                        EKEY_FINGER_DESCRIPTION,
                    )
                )
                new_devices.append(
                    HbtnDescribedSensor(
                        hbt_module,
                        mod_sensor,
                        hbtn_cord,
                        len(new_devices),
                        EKEY_FINGER_NAME_DESCRIPTION,
                    )
                )
        for mod_logic in hbt_module.logic:
            if mod_logic.type > 0:
                new_devices.append(
                    LogicSensor(hbt_module, mod_logic, hbtn_cord, len(new_devices))
                )
        for mod_diag in hbt_module.diags:
            if mod_diag.name == "Status":
                new_devices.append(
                    HbtnDescribedSensor(
                        hbt_module,
                        mod_diag,
                        hbtn_cord,
                        len(new_devices),
                        STATUS_DESCRIPTION,
                    )
                )
            elif mod_diag.name == "PowerTemp":
                new_devices.append(
                    HbtnDescribedSensor(
                        hbt_module,
                        mod_diag,
                        hbtn_cord,
                        len(new_devices),
                        POWER_TEMP_DESCRIPTION,
                    )
                )
    for time_out in hbtn_rt.chan_timeouts:
        new_devices.append(
            HbtnDescribedSensor(
                hbtn_rt, time_out, hbtn_cord, len(new_devices), TIMEOUT_DESCRIPTION
            )
        )
    for ch_curr in hbtn_rt.chan_currents:
        new_devices.append(
            HbtnDescribedSensor(
                hbtn_rt, ch_curr, hbtn_cord, len(new_devices), CURRENT_DESCRIPTION
            )
        )
    for rt_vtg in hbtn_rt.voltages:
        new_devices.append(
            HbtnDescribedSensor(
                hbtn_rt, rt_vtg, hbtn_cord, len(new_devices), VOLTAGE_DESCRIPTION
            )
        )

    if new_devices:
        # Snapshot the unique_ids already registered for this entry *before*
        # adding: entries present here existed on a prior run (a reload), so
        # their area must be left untouched.
        existing = {
            e.unique_id
            for e in er.async_entries_for_config_entry(registry, entry.entry_id)
        }
        async_add_entities(new_devices)
        for unique_id, area_id in pending_areas:
            if unique_id in existing:
                # Already existed -> respect the current (possibly user-set) area.
                continue
            entity_id = registry.async_get_entity_id("sensor", DOMAIN, unique_id)
            if entity_id is not None:
                registry.async_update_entity(entity_id, area_id=area_id)


class HbtnSensor(CoordinatorEntity[HbtnCoordinator], SensorEntity):
    """Base representation of a Habitron sensor."""

    _attr_has_entity_name = True
    _attr_state_class: SensorStateClass | None = SensorStateClass.MEASUREMENT

    def __init__(
        self,
        module: Module,
        sensor: BusMember,
        coord: HbtnCoordinator,
        idx: int,
    ) -> None:
        """Initialize a Habitron sensor, pass coordinator to CoordinatorEntity."""
        super().__init__(coord, context=idx)
        self.idx = idx
        self._module: Module = module
        self._sensor_idx = sensor.nmbr
        self._value = 0
        self._attr_unique_id = f"Mod_{self._module.uid}_snsr{sensor.nmbr}"
        self._attr_name = sensor.name

    # To link this entity to its device, this property must return an
    # identifiers value matching that used in the module
    @property
    @override
    def device_info(self) -> DeviceInfo:
        """Return information to link this entity with the correct device."""
        return _device_info(self._module.uid)

    @callback
    @override
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._attr_native_value = self._module.sensors[self._sensor_idx].value
        self.async_write_ha_state()


@dataclass(frozen=True, kw_only=True)
class HbtnSensorEntityDescription(SensorEntityDescription):
    """Habitron-specific sensor description.

    ``value_fn`` lets each description point at its own module attribute
    (``module.sensors``, ``module.diags``, ``module.chan_currents``, …) so all
    variants share a single entity class, including the text/enum sensors whose
    ``value_fn`` derives a string from the raw member value.

    ``subscribe_fn`` returns the bus member to push-subscribe to (or ``None`` for
    the coordinator-polled sensors).

    ``diag_check`` enables the common pattern of falling back to a hidden
    diagnostic entity when the underlying descriptor's ``type`` field is flagged
    as diagnostic (used by the router current/voltage/timeout streams whose
    diag-ness is only known at runtime).

    ``translated_name`` drops the bus name so the display name comes from the
    ``translation_key`` (+ per-instance ``translation_placeholders``) instead.
    """

    value_fn: Callable[[Any, int], Any]
    subscribe_fn: Callable[[Any, int], Any] | None = None
    options: list[str] | None = None
    diag_check: bool = False
    translated_name: bool = False
    initial_value: Any = None


class HbtnDescribedSensor(HbtnSensor):
    """Generic Habitron sensor driven by a ``HbtnSensorEntityDescription``."""

    entity_description: HbtnSensorEntityDescription

    def __init__(
        self,
        module: Any,
        sensor: Any,
        coord: Any,
        idx: int,
        description: HbtnSensorEntityDescription,
    ) -> None:
        """Initialize the described sensor."""
        super().__init__(module, sensor, coord, idx)
        self.entity_description = description
        # The base unique_id is ``Mod_{uid}_snsr{nmbr}``. Described sensors are
        # built against the same device with independently numbered streams, so
        # timeout/current/voltage/… would all collide on ``snsr0``. Append the
        # description key to keep each entity's unique_id distinct.
        self._attr_unique_id = f"{self._attr_unique_id}_{description.key}"
        # State class comes from the description; text/enum sensors carry None.
        self._attr_state_class = description.state_class
        if description.options is not None:
            self._attr_options = description.options
        if description.initial_value is not None:
            self._attr_native_value = description.initial_value
        if description.translated_name:
            # Let the translation_key (not the bus name) drive the display name.
            del self._attr_name
        if description.diag_check and abs(sensor.type) == TYPE_DIAG:
            self._attr_entity_category = EntityCategory.DIAGNOSTIC
            self._attr_entity_registry_enabled_default = False

    @override
    async def async_added_to_hass(self) -> None:
        """Run when this Entity has been added to HA."""
        await super().async_added_to_hass()
        if (subscribe_fn := self.entity_description.subscribe_fn) is not None:
            # Push subscription: keep HA state in sync whenever the member changes.
            subscribe_fn(self._module, self._sensor_idx).add_listener(
                self._handle_coordinator_update
            )
        # CoordinatorEntity.async_added_to_hass does not write an initial state,
        # and the coordinator's first refresh completed before this platform was
        # set up, so without this the entity would read "unknown" until the next
        # coordinator tick.
        self._handle_coordinator_update()

    @override
    async def async_will_remove_from_hass(self) -> None:
        """Entity being removed from hass."""
        if (subscribe_fn := self.entity_description.subscribe_fn) is not None:
            subscribe_fn(self._module, self._sensor_idx).remove_listener(
                self._handle_coordinator_update
            )

    @callback
    @override
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator via the description."""
        self._attr_native_value = self.entity_description.value_fn(
            self._module, self._sensor_idx
        )
        self.async_write_ha_state()


class LogicSensor(HbtnDescribedSensor):
    """Logic/counter sensor with a computed, per-instance display name.

    Kept as a thin subclass because the value/subscription index is the logic's
    list position (``logic.idx``) while the unique_id is keyed on ``logic.nmbr``,
    and the name is templated from both — expressing that purely through the
    shared description would need per-instance hooks that only this member uses.
    """

    def __init__(
        self,
        module: Module,
        logic: Logic,
        coord: HbtnCoordinator,
        idx: int,
    ) -> None:
        """Initialize the logic sensor."""
        super().__init__(module, logic, coord, idx, LOGIC_DESCRIPTION)
        # Value/subscription index is the logic's list position, not its nmbr.
        self._sensor_idx = logic.idx
        self._attr_unique_id = f"Mod_{self._module.uid}_logic{logic.nmbr}"
        self._attr_translation_placeholders = {
            "number": str(logic.nmbr + 1),
            "name": logic.name,
        }


HUMIDITY_DESCRIPTION = HbtnSensorEntityDescription(
    key="humidity",
    device_class=SensorDeviceClass.HUMIDITY,
    native_unit_of_measurement=PERCENTAGE,
    state_class=SensorStateClass.MEASUREMENT,
    value_fn=lambda module, idx: module.sensors[idx].value,
)
ILLUMINANCE_DESCRIPTION = HbtnSensorEntityDescription(
    key="illuminance",
    device_class=SensorDeviceClass.ILLUMINANCE,
    native_unit_of_measurement=LIGHT_LUX,
    state_class=SensorStateClass.MEASUREMENT,
    value_fn=lambda module, idx: module.sensors[idx].value,
)
WIND_DESCRIPTION = HbtnSensorEntityDescription(
    key="wind",
    translation_key="wind",
    device_class=SensorDeviceClass.WIND_SPEED,
    native_unit_of_measurement=UnitOfSpeed.METERS_PER_SECOND,
    state_class=SensorStateClass.MEASUREMENT,
    suggested_display_precision=1,
    value_fn=lambda module, idx: module.sensors[idx].value,
)
AIRQUALITY_DESCRIPTION = HbtnSensorEntityDescription(
    key="airquality",
    translation_key="airquality",
    native_unit_of_measurement=PERCENTAGE,
    state_class=SensorStateClass.MEASUREMENT,
    value_fn=lambda module, idx: module.sensors[idx].value,
)
TEMP_DESCRIPTION = HbtnSensorEntityDescription(
    key="temperature",
    device_class=SensorDeviceClass.TEMPERATURE,
    native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    state_class=SensorStateClass.MEASUREMENT,
    value_fn=lambda module, idx: module.sensors[idx].value,
)
TEMP_EXT_DESCRIPTION = HbtnSensorEntityDescription(
    key="temperature",
    device_class=SensorDeviceClass.TEMPERATURE,
    native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    state_class=SensorStateClass.MEASUREMENT,
    entity_registry_enabled_default=False,
    value_fn=lambda module, idx: module.sensors[idx].value,
)
ANALOG_DESCRIPTION = HbtnSensorEntityDescription(
    key="analog",
    translation_key="analog_sensor",
    native_unit_of_measurement=PERCENTAGE,
    state_class=SensorStateClass.MEASUREMENT,
    value_fn=lambda module, idx: module.analogins[idx].value,
    subscribe_fn=lambda module, idx: module.analogins[idx],
)
CURRENT_DESCRIPTION = HbtnSensorEntityDescription(
    key="current",
    device_class=SensorDeviceClass.CURRENT,
    native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
    state_class=SensorStateClass.MEASUREMENT,
    value_fn=lambda module, idx: module.chan_currents[idx].value,
    diag_check=True,
)
VOLTAGE_DESCRIPTION = HbtnSensorEntityDescription(
    key="voltage",
    device_class=SensorDeviceClass.VOLTAGE,
    native_unit_of_measurement=UnitOfElectricPotential.VOLT,
    state_class=SensorStateClass.MEASUREMENT,
    value_fn=lambda module, idx: module.voltages[idx].value,
    diag_check=True,
)
TIMEOUT_DESCRIPTION = HbtnSensorEntityDescription(
    key="timeout",
    translation_key="time_out",
    native_unit_of_measurement="",
    state_class=SensorStateClass.MEASUREMENT,
    value_fn=lambda module, idx: module.chan_timeouts[idx].value,
    diag_check=True,
)
EKEY_ID_DESCRIPTION = HbtnSensorEntityDescription(
    key="ekey_id",
    translation_key="ekey_id",
    translated_name=True,
    value_fn=lambda module, idx: module.sensors[idx].value,
    subscribe_fn=lambda module, idx: module.sensors[idx],
)
EKEY_FINGER_DESCRIPTION = HbtnSensorEntityDescription(
    key="ekey_finger",
    translation_key="ekey_finger",
    translated_name=True,
    value_fn=lambda module, idx: module.sensors[idx].value,
    subscribe_fn=lambda module, idx: module.sensors[idx],
)
EKEY_USER_NAME_DESCRIPTION = HbtnSensorEntityDescription(
    key="ekey_user_name",
    translation_key="ekey_user_name",
    translated_name=True,
    initial_value="None",
    value_fn=_ekey_user_value,
    subscribe_fn=lambda module, idx: module.sensors[idx],
)
EKEY_FINGER_NAME_DESCRIPTION = HbtnSensorEntityDescription(
    key="ekey_finger_name",
    translation_key="ekey_finger_name",
    device_class=SensorDeviceClass.ENUM,
    options=list(_FINGER_KEYS),
    translated_name=True,
    value_fn=_ekey_finger_value,
    subscribe_fn=lambda module, idx: module.sensors[idx],
)
STATUS_DESCRIPTION = HbtnSensorEntityDescription(
    key="module_status",
    translation_key="module_status",
    entity_category=EntityCategory.DIAGNOSTIC,
    entity_registry_enabled_default=False,
    translated_name=True,
    value_fn=lambda module, idx: module.diags[idx].value,
)
POWER_TEMP_DESCRIPTION = HbtnSensorEntityDescription(
    key="power_temp",
    translation_key="power_temp",
    device_class=SensorDeviceClass.TEMPERATURE,
    native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    state_class=SensorStateClass.MEASUREMENT,
    entity_category=EntityCategory.DIAGNOSTIC,
    entity_registry_enabled_default=False,
    translated_name=True,
    value_fn=lambda module, idx: module.diags[idx].value,
)
MEMORY_DESCRIPTION = HbtnSensorEntityDescription(
    key="memory_free",
    translation_key="memory_free",
    native_unit_of_measurement=PERCENTAGE,
    state_class=SensorStateClass.MEASUREMENT,
    icon="mdi:memory",
    translated_name=True,
    value_fn=lambda module, idx: module.sensors[idx].value,
    subscribe_fn=lambda module, idx: module.sensors[idx],
)
DISK_DESCRIPTION = HbtnSensorEntityDescription(
    key="disk_free",
    translation_key="disk_free",
    native_unit_of_measurement=PERCENTAGE,
    state_class=SensorStateClass.MEASUREMENT,
    icon="mdi:harddisk",
    translated_name=True,
    value_fn=lambda module, idx: module.sensors[idx].value,
    subscribe_fn=lambda module, idx: module.sensors[idx],
)
CPU_LOAD_DESCRIPTION = HbtnSensorEntityDescription(
    key="cpu_load",
    translation_key="cpu_load",
    native_unit_of_measurement=PERCENTAGE,
    state_class=SensorStateClass.MEASUREMENT,
    icon="mdi:timer-alert-outline",
    entity_category=EntityCategory.DIAGNOSTIC,
    entity_registry_enabled_default=False,
    translated_name=True,
    value_fn=lambda module, idx: module.diags[idx].value,
    subscribe_fn=lambda module, idx: module.diags[idx],
)
CPU_FREQUENCY_DESCRIPTION = HbtnSensorEntityDescription(
    key="cpu_frequency",
    translation_key="cpu_frequency",
    device_class=SensorDeviceClass.FREQUENCY,
    native_unit_of_measurement=UnitOfFrequency.MEGAHERTZ,
    state_class=SensorStateClass.MEASUREMENT,
    icon="mdi:clock-fast",
    entity_category=EntityCategory.DIAGNOSTIC,
    entity_registry_enabled_default=False,
    translated_name=True,
    value_fn=lambda module, idx: module.diags[idx].value,
    subscribe_fn=lambda module, idx: module.diags[idx],
)
CPU_TEMPERATURE_DESCRIPTION = HbtnSensorEntityDescription(
    key="cpu_temperature",
    translation_key="cpu_temperature",
    device_class=SensorDeviceClass.TEMPERATURE,
    native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    state_class=SensorStateClass.MEASUREMENT,
    entity_category=EntityCategory.DIAGNOSTIC,
    entity_registry_enabled_default=False,
    translated_name=True,
    value_fn=lambda module, idx: module.diags[idx].value,
    subscribe_fn=lambda module, idx: module.diags[idx],
)
LOGIC_DESCRIPTION = HbtnSensorEntityDescription(
    key="logic_state",
    translation_key="logic_state",
    native_unit_of_measurement="",
    state_class=SensorStateClass.MEASUREMENT,
    translated_name=True,
    value_fn=lambda module, idx: module.logic[idx].value,
    subscribe_fn=lambda module, idx: module.logic[idx],
)
