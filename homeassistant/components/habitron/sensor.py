"""Platform for sensor integration."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, override

from habitron_client import (
    FINGER_KEYS,
    BusMember,
    Logic,
    Module,
    decode_finger,
    decode_user,
)

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
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import HabitronConfigEntry, HbtnCoordinator
from .entity import HabitronEntity, HbtnOwner

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HabitronConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add sensors for passed config_entry in HA."""
    hbtn_cord = entry.runtime_data
    smhub = hbtn_cord.hub
    hbtn_rt = hbtn_cord.router

    area_reg = ar.async_get(hass)
    bus_area_names = {area.nmbr: area.name for area in hbtn_rt.areas}

    def bus_area_id(area_no: int) -> str | None:
        """Return the HA area for a bus area, creating it only when needed.

        Creating them all up front would run on every reload and resurrect an
        area the user has since renamed or deleted -- ``async_get_or_create``
        matches by name, so a renamed area is not found and is recreated under
        its old bus name.
        """
        name = bus_area_names.get(area_no)
        return area_reg.async_get_or_create(name).id if name else None

    # Snapshot the entities already registered for this entry. The deviating
    # analog-input area is stamped only at first creation, never on a reload:
    # a user may later move the entity or clear its area to inherit the device
    # area, and clearing it reads as ``area_id is None`` -- indistinguishable
    # from a fresh entity -- so the "already registered" check is what protects
    # that choice.
    known_unique_ids = {
        registered.unique_id
        for registered in er.async_entries_for_config_entry(
            er.async_get(hass), entry.entry_id
        )
    }

    new_entities: list[SensorEntity] = []

    def add_described(
        owner: HbtnOwner,
        member: BusMember,
        descriptions: tuple[HbtnSensorEntityDescription, ...],
        initial_area_id: str | None = None,
        *,
        entity_class: type[HbtnDescribedSensor] = HbtnDescribedSensor,
    ) -> None:
        """Create one entity per description for this bus member."""
        for description in descriptions:
            new_entities.append(
                entity_class(
                    owner,
                    member,
                    hbtn_cord,
                    len(new_entities),
                    description,
                    initial_area_id=initial_area_id,
                )
            )

    for smhub_sensor in smhub.sensors:
        add_described(
            smhub,
            smhub_sensor,
            HUB_SENSORS.get(smhub_sensor.name, ()),
            entity_class=HbtnHostSensor,
        )
    for smhub_diag in smhub.diags:
        add_described(
            smhub,
            smhub_diag,
            HUB_DIAGS.get(smhub_diag.name, ()),
            entity_class=HbtnHostSensor,
        )

    for hbt_module in hbtn_rt.modules:
        # The library only populates ``analogins`` for modules that have analog
        # inputs, so iterate it directly instead of hard-coding module types --
        # ``type == 3`` marks a real (enabled) analog input.
        for ain in hbt_module.analogins:
            if ain.type != 3:
                continue
            # ain.area == 0 means "the module's own area"; only a value that
            # differs is a real deviation, and only stamp it on first creation
            # (unique_id not yet registered) so a later user area choice
            # survives reloads.
            analog_uid = f"{hbt_module.uid}_{ANALOG_DESCRIPTION.key}_{ain.nmbr}"
            deviating_area = (
                bus_area_id(ain.area)
                if ain.area not in (0, hbt_module.area)
                and analog_uid not in known_unique_ids
                else None
            )
            add_described(
                hbt_module, ain, (ANALOG_DESCRIPTION,), initial_area_id=deviating_area
            )
        for mod_sensor in hbt_module.sensors:
            add_described(
                hbt_module, mod_sensor, MODULE_SENSORS.get(mod_sensor.name, ())
            )
        for mod_logic in hbt_module.logic:
            if mod_logic.type > 0:
                new_entities.append(
                    LogicSensor(hbt_module, mod_logic, hbtn_cord, len(new_entities))
                )
        for mod_diag in hbt_module.diags:
            add_described(hbt_module, mod_diag, MODULE_DIAGS.get(mod_diag.name, ()))

    for router_members, router_description in (
        (hbtn_rt.chan_timeouts, TIMEOUT_DESCRIPTION),
        (hbtn_rt.chan_currents, CURRENT_DESCRIPTION),
        (hbtn_rt.voltages, VOLTAGE_DESCRIPTION),
    ):
        for router_member in router_members:
            add_described(hbtn_rt, router_member, (router_description,))

    if new_entities:
        async_add_entities(new_entities)


@dataclass(frozen=True, kw_only=True)
class HbtnSensorEntityDescription(SensorEntityDescription):
    """Habitron-specific sensor description.

    The per-owner accessors let one entity class serve every member list, so
    only the three flags need saying:

    ``diag_check`` falls back to a hidden diagnostic entity when the member's
    own ``type`` says it is one -- the router's current, voltage and timeout
    streams only reveal that at runtime.

    ``translated_name`` drops the bus name, so the display name comes from the
    ``translation_key`` instead.

    ``numbered`` appends the member number to the unique_id, for a device that
    carries several members of the same kind (the router channels, a module's
    analogue inputs) where the key alone would not tell them apart.
    """

    value_fn: Callable[[Any, int], Any]
    subscribe_fn: Callable[[Any, int], BusMember] | None = None
    diag_check: bool = False
    translated_name: bool = False
    numbered: bool = False


class HbtnDescribedSensor(HabitronEntity, SensorEntity):
    """Generic Habitron sensor driven by a ``HbtnSensorEntityDescription``."""

    entity_description: HbtnSensorEntityDescription

    def __init__(
        self,
        module: HbtnOwner,
        sensor: BusMember,
        coord: HbtnCoordinator,
        idx: int,
        description: HbtnSensorEntityDescription,
        initial_area_id: str | None = None,
    ) -> None:
        """Initialize the described sensor."""
        super().__init__(module, sensor, coord, idx)
        self.entity_description = description
        # An area that deviates from the module's own, applied once the entity
        # is registered (see ``async_added_to_hass``). HA has no per-entity
        # ``suggested_area``, so it has to go through the entity registry.
        self._initial_area_id = initial_area_id
        # Members sharing a description -- router channels, analogue inputs --
        # would collide on uid and key alone, hence the member number.
        self._attr_unique_id = f"{module.uid}_{description.key}"
        if description.numbered:
            self._attr_unique_id = f"{self._attr_unique_id}_{sensor.nmbr}"
        if description.translated_name:
            # Let the translation_key (not the bus name) drive the display name.
            del self._attr_name
        if description.diag_check and sensor.is_diagnostic:
            self._attr_entity_category = EntityCategory.DIAGNOSTIC
            self._attr_entity_registry_enabled_default = False

    @override
    async def async_added_to_hass(self) -> None:
        """Run when this Entity has been added to HA."""
        await super().async_added_to_hass()
        # Apply the deviating area now the entity is registered.
        # ``_initial_area_id`` is only set for a first-time creation (the setup
        # snapshot gate), so this never overrides a later user choice.
        # ``async_add_entities`` registers asynchronously, so this cannot run at
        # platform-setup time.
        if self._initial_area_id is not None and (entry := self.registry_entry):
            er.async_get(self.hass).async_update_entity(
                entry.entity_id, area_id=self._initial_area_id
            )
        if (subscribe_fn := self.entity_description.subscribe_fn) is not None:
            member = subscribe_fn(self._module, self._sensor_idx)
            member.add_listener(self._handle_coordinator_update)
            # Unsubscribed through ``async_on_remove`` rather than
            # ``async_will_remove_from_hass``: the latter is skipped when adding
            # the entity fails after this hook has run -- ``entity_platform``
            # then calls ``add_to_platform_abort``, which runs only the
            # on-remove callbacks -- and the library would keep a listener for
            # an entity Home Assistant has discarded.
            self.async_on_remove(
                lambda: member.remove_listener(self._handle_coordinator_update)
            )
        # CoordinatorEntity.async_added_to_hass does not pick up a value, and
        # the coordinator's first refresh completed before this platform was set
        # up, so without this the entity would start out "unknown" until the
        # next coordinator tick. Taking the value is all there is to do:
        # ``add_to_platform_finish`` writes the state right after this hook
        # returns, and a write attempted from in here would be dropped anyway --
        # ``_async_write_ha_state`` returns early while ``_platform_state`` is
        # still ADDING.
        self._refresh_native_value()

    @callback
    def _refresh_native_value(self) -> None:
        """Read this sensor's value out of the model."""
        self._attr_native_value = self.entity_description.value_fn(
            self._module, self._sensor_idx
        )

    @callback
    @override
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator via the description."""
        self._refresh_native_value()
        self.async_write_ha_state()


class HbtnHostSensor(HbtnDescribedSensor):
    """A reading of the hub itself rather than of the bus.

    Host readings are polled apart from the bus status and their errors are
    swallowed, so that a hub-diagnostics hiccup cannot mark every bus entity
    unavailable. That trade only holds while the readings say when they stopped
    being live: ``SmartHub.host_valid`` means "a poll has ever succeeded" and
    never goes back to false, so CPU, memory and disk would otherwise keep
    reporting their last value indefinitely, indistinguishable from a fresh one.
    """

    @property
    @override
    def available(self) -> bool:
        """Whether the hub answered the most recent host poll."""
        return super().available and self.coordinator.host_readings_ok


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
        self._attr_unique_id = f"{self._module.uid}_logic_{logic.nmbr}"
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
WIND_PEAK_DESCRIPTION = HbtnSensorEntityDescription(
    key="wind_peak",
    translation_key="wind_peak",
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
    key="temperature_external",
    device_class=SensorDeviceClass.TEMPERATURE,
    native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    state_class=SensorStateClass.MEASUREMENT,
    entity_registry_enabled_default=False,
    value_fn=lambda module, idx: module.sensors[idx].value,
)
# No ``subscribe_fn``: analogue values live in the compact status mirror (the
# Smart In reads all six from it, the Smart Controller its two), and nothing
# else ever writes them -- push events do not carry them at all. A change
# therefore always moves the status CRC and reaches the entity through the
# coordinator; subscribing as well would only write the state a second time.
ANALOG_DESCRIPTION = HbtnSensorEntityDescription(
    key="analog_in",
    translation_key="analog_sensor",
    native_unit_of_measurement=PERCENTAGE,
    state_class=SensorStateClass.MEASUREMENT,
    value_fn=lambda module, idx: module.analogins[idx].value,
    numbered=True,
)
CURRENT_DESCRIPTION = HbtnSensorEntityDescription(
    key="current",
    device_class=SensorDeviceClass.CURRENT,
    native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
    state_class=SensorStateClass.MEASUREMENT,
    value_fn=lambda module, idx: module.chan_currents[idx].value,
    subscribe_fn=lambda module, idx: module.chan_currents[idx],
    diag_check=True,
    numbered=True,
)
VOLTAGE_DESCRIPTION = HbtnSensorEntityDescription(
    key="voltage",
    device_class=SensorDeviceClass.VOLTAGE,
    native_unit_of_measurement=UnitOfElectricPotential.VOLT,
    state_class=SensorStateClass.MEASUREMENT,
    value_fn=lambda module, idx: module.voltages[idx].value,
    subscribe_fn=lambda module, idx: module.voltages[idx],
    diag_check=True,
    numbered=True,
)
TIMEOUT_DESCRIPTION = HbtnSensorEntityDescription(
    key="timeout",
    translation_key="time_out",
    state_class=SensorStateClass.MEASUREMENT,
    value_fn=lambda module, idx: module.chan_timeouts[idx].value,
    subscribe_fn=lambda module, idx: module.chan_timeouts[idx],
    diag_check=True,
    numbered=True,
)
EKEY_ID_DESCRIPTION = HbtnSensorEntityDescription(
    key="ekey_identifier",
    translation_key="ekey_id",
    translated_name=True,
    value_fn=lambda module, idx: module.sensors[idx].value,
    # No ``subscribe_fn``: the poll parser (``_status_ekey``) writes this member
    # and the same read moves the module CRC, so the coordinator already updates
    # the entity -- subscribing would write the state twice. The FINGER bus event
    # writes it too, but nothing receives events yet; the subscription belongs
    # with the push receiver in a later PR.
)
# The finger sensors bind to ``module.sensors[idx]`` -- the canonical member for
# the finger number, which both the 10-second poll parser (``_status_ekey``) and
# the FINGER bus event write (habitron_client >= 2.0.9). ``module.fingers[0]``
# instead carries the combined user+finger reading as one atomic event, meant for
# the access-control event platform in a later PR, not this per-number sensor.
EKEY_FINGER_DESCRIPTION = HbtnSensorEntityDescription(
    key="ekey_finger",
    translation_key="ekey_finger",
    translated_name=True,
    value_fn=lambda module, idx: module.sensors[idx].value,
    # No ``subscribe_fn``: the poll parser (``_status_ekey``) writes this member
    # and the same read moves the module CRC, so the coordinator already updates
    # the entity -- subscribing would write the state twice. The FINGER bus event
    # writes it too, but nothing receives events yet; the subscription belongs
    # with the push receiver in a later PR.
)
EKEY_USER_NAME_DESCRIPTION = HbtnSensorEntityDescription(
    key="ekey_user_name",
    translation_key="ekey_user_name",
    translated_name=True,
    value_fn=lambda module, idx: decode_user(
        int(module.sensors[idx].value or 0), module.ids
    ),
    # No ``subscribe_fn``: the poll parser (``_status_ekey``) writes this member
    # and the same read moves the module CRC, so the coordinator already updates
    # the entity -- subscribing would write the state twice. The FINGER bus event
    # writes it too, but nothing receives events yet; the subscription belongs
    # with the push receiver in a later PR.
)
EKEY_FINGER_NAME_DESCRIPTION = HbtnSensorEntityDescription(
    key="ekey_finger_name",
    translation_key="ekey_finger_name",
    device_class=SensorDeviceClass.ENUM,
    options=list(FINGER_KEYS),
    translated_name=True,
    value_fn=lambda module, idx: decode_finger(int(module.sensors[idx].value or 0)),
    # No ``subscribe_fn``: the poll parser (``_status_ekey``) writes this member
    # and the same read moves the module CRC, so the coordinator already updates
    # the entity -- subscribing would write the state twice. The FINGER bus event
    # writes it too, but nothing receives events yet; the subscription belongs
    # with the push receiver in a later PR.
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
    key="power_temperature",
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
    key="memory_usage",
    translation_key="memory_usage",
    native_unit_of_measurement=PERCENTAGE,
    state_class=SensorStateClass.MEASUREMENT,
    # Host health of the machine the hub runs on, like the CPU readings below
    # -- not a building-automation measurement anyone automates on.
    entity_category=EntityCategory.DIAGNOSTIC,
    entity_registry_enabled_default=False,
    translated_name=True,
    value_fn=lambda hub, idx: hub.sensors[idx].value if hub.host_valid else None,
    subscribe_fn=lambda module, idx: module.sensors[idx],
)
DISK_DESCRIPTION = HbtnSensorEntityDescription(
    key="disk_usage",
    translation_key="disk_usage",
    native_unit_of_measurement=PERCENTAGE,
    state_class=SensorStateClass.MEASUREMENT,
    entity_category=EntityCategory.DIAGNOSTIC,
    entity_registry_enabled_default=False,
    translated_name=True,
    value_fn=lambda hub, idx: hub.sensors[idx].value if hub.host_valid else None,
    subscribe_fn=lambda module, idx: module.sensors[idx],
)
CPU_LOAD_DESCRIPTION = HbtnSensorEntityDescription(
    key="cpu_load",
    translation_key="cpu_load",
    native_unit_of_measurement=PERCENTAGE,
    state_class=SensorStateClass.MEASUREMENT,
    entity_category=EntityCategory.DIAGNOSTIC,
    entity_registry_enabled_default=False,
    translated_name=True,
    value_fn=lambda hub, idx: hub.diags[idx].value if hub.host_valid else None,
    subscribe_fn=lambda module, idx: module.diags[idx],
)
CPU_FREQUENCY_DESCRIPTION = HbtnSensorEntityDescription(
    key="cpu_frequency",
    translation_key="cpu_frequency",
    device_class=SensorDeviceClass.FREQUENCY,
    native_unit_of_measurement=UnitOfFrequency.MEGAHERTZ,
    state_class=SensorStateClass.MEASUREMENT,
    entity_category=EntityCategory.DIAGNOSTIC,
    entity_registry_enabled_default=False,
    translated_name=True,
    value_fn=lambda hub, idx: hub.diags[idx].value if hub.host_valid else None,
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
    value_fn=lambda hub, idx: hub.diags[idx].value if hub.host_valid else None,
    subscribe_fn=lambda module, idx: module.diags[idx],
)
LOGIC_DESCRIPTION = HbtnSensorEntityDescription(
    key="logic",
    translation_key="logic_state",
    state_class=SensorStateClass.MEASUREMENT,
    translated_name=True,
    # No ``subscribe_fn``: counter values come from the compact status mirror,
    # which the module CRC covers, so a change already moves the coordinator's
    # data and updates the entity. Subscribing would write the state twice.
    value_fn=lambda module, idx: module.logic[idx].value,
)


# Which entity descriptions a bus member's name maps to. Keyed by the name the
# library gives the member; the ekey members produce two entities each -- the
# raw value and the resolved name. A member whose name is not listed simply
# gets no entity.
HUB_SENSORS: dict[str, tuple[HbtnSensorEntityDescription, ...]] = {
    "Memory usage": (MEMORY_DESCRIPTION,),
    "Disk usage": (DISK_DESCRIPTION,),
}

HUB_DIAGS: dict[str, tuple[HbtnSensorEntityDescription, ...]] = {
    "CPU Frequency": (CPU_FREQUENCY_DESCRIPTION,),
    "CPU load": (CPU_LOAD_DESCRIPTION,),
    "CPU Temperature": (CPU_TEMPERATURE_DESCRIPTION,),
}

MODULE_SENSORS: dict[str, tuple[HbtnSensorEntityDescription, ...]] = {
    # The external probe is disabled by default; the two descriptions differ
    # only in entity_registry_enabled_default.
    "Temperature": (TEMP_DESCRIPTION,),
    "Temperature ext.": (TEMP_EXT_DESCRIPTION,),
    "Humidity": (HUMIDITY_DESCRIPTION,),
    "Illuminance": (ILLUMINANCE_DESCRIPTION,),
    "Wind": (WIND_DESCRIPTION,),
    "Windpeak": (WIND_PEAK_DESCRIPTION,),
    "Airquality": (AIRQUALITY_DESCRIPTION,),
    "Identifier": (EKEY_ID_DESCRIPTION, EKEY_USER_NAME_DESCRIPTION),
    "Finger": (EKEY_FINGER_DESCRIPTION, EKEY_FINGER_NAME_DESCRIPTION),
}

MODULE_DIAGS: dict[str, tuple[HbtnSensorEntityDescription, ...]] = {
    "Status": (STATUS_DESCRIPTION,),
    "PowerTemp": (POWER_TEMP_DESCRIPTION,),
}
