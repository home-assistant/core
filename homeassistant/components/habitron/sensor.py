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
    DOMAIN as SENSOR_DOMAIN,
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
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers import area_registry as ar, entity_registry as er
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
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
        """Return the HA area for a bus area, creating it only when needed."""
        name = bus_area_names.get(area_no)
        return area_reg.async_get_or_create(name).id if name else None

    # Set an analog input's own area only on first registration, never on reload.
    ent_reg = er.async_get(hass)
    known_unique_ids = {
        registered.unique_id
        for registered in er.async_entries_for_config_entry(ent_reg, entry.entry_id)
    } | {
        unique_id
        for domain, platform, unique_id in ent_reg.deleted_entities
        if domain == SENSOR_DOMAIN and platform == DOMAIN
    }
    pending_areas: dict[str, str] = {}

    new_entities: list[SensorEntity] = []

    def add_described(
        owner: HbtnOwner,
        member: BusMember,
        descriptions: tuple[HbtnSensorEntityDescription, ...],
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
        for ain in hbt_module.analogins:
            if ain.type != 3:
                continue
            # Area 0 means the module's own area.
            analog_uid = f"{hbt_module.uid}_{ANALOG_DESCRIPTION.key}_{ain.nmbr}"
            if (
                ain.area not in (0, hbt_module.area)
                and analog_uid not in known_unique_ids
                and (area_id := bus_area_id(ain.area)) is not None
            ):
                pending_areas[analog_uid] = area_id
            add_described(hbt_module, ain, (ANALOG_DESCRIPTION,))
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

    if pending_areas:
        # On registry creation, since a disabled entity is never added.
        @callback
        def _async_stamp_area(
            event: Event[er.EventEntityRegistryUpdatedData],
        ) -> None:
            if event.data["action"] != "create":
                return
            registered = ent_reg.async_get(event.data["entity_id"])
            if (
                registered is not None
                and registered.config_entry_id == entry.entry_id
                and (area_id := pending_areas.pop(registered.unique_id, None))
            ):
                ent_reg.async_update_entity(registered.entity_id, area_id=area_id)

        entry.async_on_unload(
            hass.bus.async_listen(er.EVENT_ENTITY_REGISTRY_UPDATED, _async_stamp_area)
        )

    if new_entities:
        async_add_entities(new_entities)


@dataclass(frozen=True, kw_only=True)
class HbtnSensorEntityDescription(SensorEntityDescription):
    """Habitron sensor entity description."""

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
    ) -> None:
        """Initialize the described sensor."""
        super().__init__(module, sensor, coord, idx)
        self.entity_description = description
        self._attr_unique_id = f"{module.uid}_{description.key}"
        if description.numbered:
            self._attr_unique_id = f"{self._attr_unique_id}_{sensor.nmbr}"
        if description.translated_name:
            del self._attr_name
        if description.diag_check and sensor.is_diagnostic:
            self._attr_entity_category = EntityCategory.DIAGNOSTIC
            self._attr_entity_registry_enabled_default = False

    @override
    async def async_added_to_hass(self) -> None:
        """Run when this Entity has been added to HA."""
        await super().async_added_to_hass()
        if (subscribe_fn := self.entity_description.subscribe_fn) is not None:
            member = subscribe_fn(self._module, self._sensor_idx)
            member.add_listener(self._handle_coordinator_update)
            # async_on_remove also runs when adding the entity fails.
            self.async_on_remove(
                lambda: member.remove_listener(self._handle_coordinator_update)
            )
        # The first refresh ran before the platform was set up.
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
    """Sensor for a host reading of the hub itself."""

    @property
    @override
    def available(self) -> bool:
        """Return if the hub answered the last host poll."""
        return super().available and self.coordinator.host_readings_ok


class LogicSensor(HbtnDescribedSensor):
    """Logic/counter sensor of a module."""

    def __init__(
        self,
        module: Module,
        logic: Logic,
        coord: HbtnCoordinator,
        idx: int,
    ) -> None:
        """Initialize the logic sensor."""
        super().__init__(module, logic, coord, idx, LOGIC_DESCRIPTION)
        # The value index is the logic's list position, not its number.
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
)
EKEY_FINGER_DESCRIPTION = HbtnSensorEntityDescription(
    key="ekey_finger",
    translation_key="ekey_finger",
    translated_name=True,
    value_fn=lambda module, idx: module.sensors[idx].value,
)
EKEY_USER_NAME_DESCRIPTION = HbtnSensorEntityDescription(
    key="ekey_user_name",
    translation_key="ekey_user_name",
    translated_name=True,
    value_fn=lambda module, idx: decode_user(
        int(module.sensors[idx].value or 0), module.ids
    ),
)
EKEY_FINGER_NAME_DESCRIPTION = HbtnSensorEntityDescription(
    key="ekey_finger_name",
    translation_key="ekey_finger_name",
    device_class=SensorDeviceClass.ENUM,
    options=list(FINGER_KEYS),
    translated_name=True,
    value_fn=lambda module, idx: decode_finger(int(module.sensors[idx].value or 0)),
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
    value_fn=lambda module, idx: module.logic[idx].value,
)


# Entity descriptions by bus member name; unlisted members get no entity.
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
