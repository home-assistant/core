"""Platform for sensor integration."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, cast, override

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

from ._helpers import async_assign_entity_area, hbtn_device_info
from .coordinator import HabitronConfigEntry, HbtnCoordinator

if TYPE_CHECKING:
    from .smart_hub import SmartHub

PARALLEL_UPDATES = 0
TYPE_DIAG = 10  # diagnostic entity, hidden by default


async def async_setup_entry(  # noqa: C901
    hass: HomeAssistant,
    entry: HabitronConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add sensors for passed config_entry in HA."""
    smhub = entry.runtime_data
    hbtn_rt = smhub.router
    hbtn_cord = smhub.coordinator

    new_devices: list[SensorEntity] = []
    for smhub_sensor in smhub.sensors:
        if smhub_sensor.name == "Memory free":
            new_devices.append(
                PercSensor(smhub, smhub_sensor, hbtn_cord, len(new_devices))
            )
        if smhub_sensor.name == "Disk free":
            new_devices.append(
                PercSensor(smhub, smhub_sensor, hbtn_cord, len(new_devices))
            )
    for smhub_diag in smhub.diags:
        if smhub_diag.name == "CPU Frequency":
            new_devices.append(
                FrequencySensor(smhub, smhub_diag, hbtn_cord, len(new_devices))
            )
        if smhub_diag.name == "CPU load":
            new_devices.append(
                PercSensor(smhub, smhub_diag, hbtn_cord, len(new_devices))
            )

        if smhub_diag.name == "CPU Temperature":
            new_devices.append(
                # SmartHub stands in for an HbtnModule here (same lookup shape).
                TemperatureDSensor(
                    cast("Module", smhub),
                    smhub_diag,
                    hbtn_cord,
                    len(new_devices),
                )
            )

    # --- Module Iteration ---
    for hbt_module in hbtn_rt.modules:
        if hbt_module.typ in [b"\x01\x03", b"\x0b\x1f"]:
            for ain in hbt_module.analogins:
                if ain.type == 3:
                    new_devices.append(
                        AnalogSensor(hbt_module, ain, hbtn_cord, len(new_devices))
                    )
        for mod_sensor in hbt_module.sensors:
            if mod_sensor.name[0:11] == "Temperature":
                new_devices.append(
                    TemperatureSensor(
                        hbt_module, mod_sensor, hbtn_cord, len(new_devices)
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
                    EKeySensorId(hbt_module, mod_sensor, hbtn_cord, len(new_devices))
                )
                new_devices.append(
                    EKeyUserNameSensor(
                        hbt_module, mod_sensor.nmbr, hbtn_cord, len(new_devices)
                    )
                )
            elif mod_sensor.name == "Finger":
                new_devices.append(
                    EKeySensorFngr(hbt_module, mod_sensor, hbtn_cord, len(new_devices))
                )
                new_devices.append(
                    EKeyFingerNameSensor(
                        hbt_module, mod_sensor.nmbr, hbtn_cord, len(new_devices)
                    )
                )
        for mod_logic in hbt_module.logic:
            if mod_logic.type > 0:
                new_devices.append(
                    LogicSensorPush(hbt_module, mod_logic, hbtn_cord, len(new_devices))
                )
        for mod_diag in hbt_module.diags:
            if mod_diag.name == "Status":
                new_devices.append(
                    StatusSensor(hbt_module, mod_diag, hbtn_cord, len(new_devices))
                )
            elif mod_diag.name == "PowerTemp":
                new_devices.append(
                    TemperatureDSensor(
                        hbt_module, mod_diag, hbtn_cord, len(new_devices)
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
        async_add_entities(new_devices)

    # --- Area Registry Handling ---
    registry = er.async_get(hass)
    area_reg = ar.async_get(hass)
    # Resolve each bus area to its HA area-registry id (creating the area when
    # needed), matching by name exactly like the module devices in smart_hub.
    # The stored area_id must be an AreaEntry.id, not a slugified name.
    area_ids = {
        area.nmbr: area_reg.async_get_or_create(area.name).id for area in hbtn_rt.areas
    }

    for hbt_module in hbtn_rt.modules:
        if hbt_module.typ in [b"\x01\x03", b"\x0b\x1f"]:
            for ain in hbt_module.analogins:
                if ain.type == 3:  # analog input
                    async_assign_entity_area(
                        registry,
                        domain="sensor",
                        unique_id=f"Mod_{hbt_module.uid}_adin{ain.nmbr}",
                        area_index=ain.area,
                        area_member=hbt_module.area,
                        area_ids=area_ids,
                    )


class HbtnSensor(CoordinatorEntity[HbtnCoordinator], SensorEntity):
    """Base representation of a Habitron sensor."""

    _attr_has_entity_name = True
    _attr_state_class = SensorStateClass.MEASUREMENT

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
        return hbtn_device_info(self._module.uid)

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
    (``module.sensors``, ``module.chan_currents``, ``module.voltages``, …)
    so all variants share a single entity class.

    ``diag_check`` enables the common pattern of falling back to a hidden
    diagnostic entity when the underlying descriptor's ``type`` field is
    flagged as diagnostic.
    """

    value_fn: Callable[[Any, int], Any]
    diag_check: bool = False


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
        # built against the same router with independently numbered streams, so
        # timeout/current/voltage would all collide on ``snsr0``. Append the
        # description key to keep each entity's unique_id distinct.
        self._attr_unique_id = f"{self._attr_unique_id}_{description.key}"
        if description.diag_check and abs(sensor.type) == TYPE_DIAG:
            self._attr_entity_category = EntityCategory.DIAGNOSTIC
            self._attr_entity_registry_enabled_default = False

    @callback
    @override
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator via the description."""
        self._attr_native_value = self.entity_description.value_fn(
            self._module, self._sensor_idx
        )
        self.async_write_ha_state()


HUMIDITY_DESCRIPTION = HbtnSensorEntityDescription(
    key="humidity",
    device_class=SensorDeviceClass.HUMIDITY,
    native_unit_of_measurement=PERCENTAGE,
    value_fn=lambda module, idx: module.sensors[idx].value,
)
ILLUMINANCE_DESCRIPTION = HbtnSensorEntityDescription(
    key="illuminance",
    device_class=SensorDeviceClass.ILLUMINANCE,
    native_unit_of_measurement=LIGHT_LUX,
    value_fn=lambda module, idx: module.sensors[idx].value,
)
WIND_DESCRIPTION = HbtnSensorEntityDescription(
    key="wind",
    translation_key="wind",
    device_class=SensorDeviceClass.WIND_SPEED,
    native_unit_of_measurement=UnitOfSpeed.METERS_PER_SECOND,
    suggested_display_precision=1,
    value_fn=lambda module, idx: module.sensors[idx].value,
)
AIRQUALITY_DESCRIPTION = HbtnSensorEntityDescription(
    key="airquality",
    translation_key="airquality",
    native_unit_of_measurement=PERCENTAGE,
    value_fn=lambda module, idx: module.sensors[idx].value,
)
CURRENT_DESCRIPTION = HbtnSensorEntityDescription(
    key="current",
    device_class=SensorDeviceClass.CURRENT,
    native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
    value_fn=lambda module, idx: module.chan_currents[idx].value,
    diag_check=True,
)
VOLTAGE_DESCRIPTION = HbtnSensorEntityDescription(
    key="voltage",
    device_class=SensorDeviceClass.VOLTAGE,
    native_unit_of_measurement=UnitOfElectricPotential.VOLT,
    value_fn=lambda module, idx: module.voltages[idx].value,
    diag_check=True,
)
TIMEOUT_DESCRIPTION = HbtnSensorEntityDescription(
    key="timeout",
    translation_key="time_out",
    native_unit_of_measurement="",
    value_fn=lambda module, idx: module.chan_timeouts[idx].value,
    diag_check=True,
)


class AnalogSensor(HbtnSensor):
    """Representation of a Sensor."""

    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_translation_key = "analog_sensor"

    def __init__(
        self,
        module: Module,
        sensor: BusMember,
        coord: HbtnCoordinator,
        idx: int,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(module, sensor, coord, idx)
        self._attr_unique_id = f"Mod_{self._module.uid}_adin{sensor.nmbr}"
        self.sensor = sensor

    @override
    async def async_added_to_hass(self) -> None:
        """Run when this Entity has been added to HA."""
        # Push subscription: keep HA state in sync whenever the bus member changes.
        await super().async_added_to_hass()
        self.sensor.add_listener(self._handle_coordinator_update)

    @override
    async def async_will_remove_from_hass(self) -> None:
        """Entity being removed from hass."""
        # The opposite of async_added_to_hass. Remove any registered call backs here.
        self.sensor.remove_listener(self._handle_coordinator_update)

    @callback
    @override
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._attr_native_value = self._module.analogins[self._sensor_idx].value
        self.async_write_ha_state()


class TemperatureSensor(HbtnSensor):
    """Representation of a Sensor."""

    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS

    def __init__(
        self,
        module: Module,
        sensor: BusMember,
        coord: HbtnCoordinator,
        idx: int,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(module, sensor, coord, idx)
        if sensor.name == "Temperature ext.":
            self._attr_entity_registry_enabled_default = (
                False  # Entity will initially be disabled
            )


class EKeySensorId(HbtnSensor):
    """Representation of an ekey identifier sensor."""

    _attr_translation_key = "ekey_id"

    def __init__(
        self,
        module: Module,
        sensor: BusMember,
        coord: HbtnCoordinator,
        idx: int,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(module, sensor, coord, idx)
        self.sensor = sensor
        self._attr_unique_id = f"Mod_{self._module.uid}_ekey_ident"
        self._attr_name = "Identifier Value"

    @override
    async def async_added_to_hass(self) -> None:
        """Run when this Entity has been added to HA."""
        # Push subscription: keep HA state in sync whenever the bus member changes.
        await super().async_added_to_hass()
        self.sensor.add_listener(self._handle_coordinator_update)

    @override
    async def async_will_remove_from_hass(self) -> None:
        """Entity being removed from hass."""
        # The opposite of async_added_to_hass. Remove any registered call backs here.
        self.sensor.remove_listener(self._handle_coordinator_update)


class EKeySensorFngr(HbtnSensor):
    """Representation of an ekey finger sensor."""

    _attr_translation_key = "ekey_finger"

    def __init__(
        self,
        module: Module,
        sensor: BusMember,
        coord: HbtnCoordinator,
        idx: int,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(module, sensor, coord, idx)
        self.sensor = sensor
        self._attr_unique_id = f"Mod_{self._module.uid}_ekey_fngr"
        self._attr_name = "Finger Value"

    @override
    async def async_added_to_hass(self) -> None:
        """Run when this Entity has been added to HA."""
        # Push subscription: keep HA state in sync whenever the bus member changes.
        await super().async_added_to_hass()
        self.sensor.add_listener(self._handle_coordinator_update)

    @override
    async def async_will_remove_from_hass(self) -> None:
        """Entity being removed from hass."""
        # The opposite of async_added_to_hass. Remove any registered call backs here.
        self.sensor.remove_listener(self._handle_coordinator_update)


class HbtnDiagSensor(CoordinatorEntity[HbtnCoordinator], SensorEntity):
    """Base representation of a Habitron sensor."""

    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self,
        module: Module,
        diag: BusMember,
        coord: HbtnCoordinator,
        idx: int,
    ) -> None:
        """Initialize a Habitron sensor, pass coordinator to CoordinatorEntity."""
        super().__init__(coord, context=idx)
        self.idx = idx
        self._module = module
        self._diag_idx = diag.nmbr
        self._value = 0
        self._attr_entity_category = EntityCategory.DIAGNOSTIC
        self._attr_entity_registry_enabled_default = (
            False  # Entity will initially be disabled
        )

    # To link this entity to its device, this property must return an
    # identifiers value matching that used in the module
    @property
    @override
    def device_info(self) -> DeviceInfo | None:
        """Return information to link this entity with the correct device."""
        return hbtn_device_info(self._module.uid)

    @callback
    @override
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._attr_native_value = self._module.diags[self._diag_idx].value
        self.async_write_ha_state()


class TemperatureDSensor(HbtnDiagSensor):
    """Representation of a Sensor."""

    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_has_entity_name = True
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS

    def __init__(
        self,
        module: Module,
        diag: BusMember,
        coord: HbtnCoordinator,
        idx: int,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(module, diag, coord, idx)
        self._attr_unique_id = f"Mod_{self._module.uid}_{diag.name}"
        self._attr_name = diag.name


class StatusSensor(HbtnDiagSensor):
    """Representation of a Sensor."""

    _attr_has_entity_name = True

    def __init__(
        self,
        module: Module,
        diag: BusMember,
        coord: HbtnCoordinator,
        idx: int,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(module, diag, coord, idx)
        self._attr_unique_id = f"Mod_{self._module.uid}_module_status"
        self._attr_name = diag.name

    @callback
    @override
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._attr_native_value = self._module.diags[self._diag_idx].value
        # Set the icon before writing state so it reflects the current value.
        if self._attr_native_value:
            self._attr_icon = "mdi:lan-disconnect"
        else:
            self._attr_icon = "mdi:lan-check"
        self.async_write_ha_state()


class LogicSensor(HbtnSensor):
    """Representation of a logic state sensor."""

    _attr_native_unit_of_measurement = ""
    _attr_translation_key = "logic_state"

    def __init__(
        self,
        module: Module,
        logic: Logic,
        coord: HbtnCoordinator,
        idx: int,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(module, logic, coord, idx)
        self.idx = logic.idx
        self.logic = logic
        self._attr_unique_id = f"Mod_{self._module.uid}_logic{logic.nmbr}"
        self._attr_name = f"Cnt{logic.nmbr + 1}: {logic.name}"

    @callback
    @override
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._attr_native_value = self._module.logic[self.idx].value
        self.async_write_ha_state()


class LogicSensorPush(LogicSensor):
    """Representation of a logic state sensor for push update."""

    @override
    async def async_added_to_hass(self) -> None:
        """Run when this Entity has been added to HA."""
        # Push subscription: keep HA state in sync whenever the bus member changes.
        await super().async_added_to_hass()
        self.logic.add_listener(self._handle_coordinator_update)

    @override
    async def async_will_remove_from_hass(self) -> None:
        """Entity being removed from hass."""
        # The opposite of async_added_to_hass. Remove any registered call backs here.
        self.logic.remove_listener(self._handle_coordinator_update)


class PercSensor(HbtnSensor):
    """Representation of a percentage sensor."""

    _attr_native_unit_of_measurement = PERCENTAGE

    def __init__(
        self,
        module: SmartHub,
        perctg: BusMember,
        coord: HbtnCoordinator,
        idx: int,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(cast("Module", module), perctg, coord, idx)
        self.type = perctg.type
        self._attr_unique_id = f"Mod_{self._module.uid}_perc{perctg.nmbr}"
        if self._attr_name[:6].lower() == "memory":  # type: ignore[index]
            self._attr_icon = "mdi:memory"
        elif self._attr_name[:4].lower() == "disk":  # type: ignore[index]
            self._attr_icon = "mdi:harddisk"
        elif self._attr_name.lower() == "cpu load":  # type: ignore[union-attr]
            self._attr_icon = "mdi:timer-alert-outline"
        else:
            self._attr_icon = "mdi:percent-circle-outline"
        if abs(perctg.type) == TYPE_DIAG:
            self._attr_entity_category = EntityCategory.DIAGNOSTIC
            self._attr_unique_id = f"Mod_{self._module.uid}_dperc{perctg.nmbr}"
            self._attr_entity_registry_enabled_default = (
                False  # Entity will initially be disabled
            )

    @callback
    @override
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if abs(self.type) == TYPE_DIAG:
            self._attr_native_value = self._module.diags[self._sensor_idx].value
        else:
            self._attr_native_value = self._module.sensors[self._sensor_idx].value
        self.async_write_ha_state()


class FrequencySensor(HbtnSensor):
    """Representation of a frequency sensor."""

    _attr_device_class = SensorDeviceClass.FREQUENCY
    _attr_native_unit_of_measurement = UnitOfFrequency.HERTZ

    def __init__(
        self,
        module: SmartHub,
        freq: BusMember,
        coord: HbtnCoordinator,
        idx: int,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(cast("Module", module), freq, coord, idx)
        self.type = freq.type
        if self._attr_name.lower() == "cpu frequency":  # type: ignore[union-attr]
            self._attr_icon = "mdi:clock-fast"
        else:
            self._attr_icon = "mdi:sine-wave"
        if abs(self.type) == TYPE_DIAG:
            self._attr_entity_category = EntityCategory.DIAGNOSTIC
            self._attr_entity_registry_enabled_default = (
                False  # Entity will initially be disabled
            )

    @callback
    @override
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if abs(self.type) == TYPE_DIAG:
            self._attr_native_value = self._module.diags[self._sensor_idx].value
        else:
            self._attr_native_value = self._module.sensors[self._sensor_idx].value
        self.async_write_ha_state()


class EKeyUserNameSensor(CoordinatorEntity[HbtnCoordinator], SensorEntity):
    """Resolve a Fanekey ``Identifier`` value to the matching user's name."""

    _attr_has_entity_name = True
    _attr_translation_key = "ekey_user_name"

    def __init__(
        self,
        module: Module,
        nmbr: int,
        coord: HbtnCoordinator,
        idx: int,
    ) -> None:
        """Initialize the user-name sensor."""
        super().__init__(coord, context=idx)
        self.idx = idx
        self._module = module
        self._nmbr = nmbr
        self._attr_unique_id = f"Mod_{self._module.uid}_ekey_ident_name"
        self._attr_device_info = hbtn_device_info(self._module.uid)
        self._attr_native_value = "None"

    @override
    async def async_added_to_hass(self) -> None:
        """Subscribe to the underlying sensor's push updates."""
        await super().async_added_to_hass()
        self._module.sensors[self._nmbr].add_listener(self._handle_coordinator_update)

    @override
    async def async_will_remove_from_hass(self) -> None:
        """Unsubscribe from the underlying sensor's push updates."""
        self._module.sensors[self._nmbr].remove_listener(
            self._handle_coordinator_update
        )

    @callback
    @override
    def _handle_coordinator_update(self) -> None:
        """Translate the raw identifier value into a user name string."""
        id_val = int(self._module.sensors[self._nmbr].value or 0)
        if id_val == 0:
            self._attr_native_value = "None"
        elif id_val == 255:
            self._attr_native_value = "Error"
        elif (id_val - 1) in range(len(self._module.ids)):
            self._attr_native_value = self._module.ids[id_val - 1].name
        elif (abs(id_val) - 1) in range(len(self._module.ids)):
            self._attr_native_value = (
                self._module.ids[abs(id_val) - 1].name + "-disabled"
            )
        else:
            self._attr_native_value = "Unknown"
        self.async_write_ha_state()


class EKeyFingerNameSensor(CoordinatorEntity[HbtnCoordinator], SensorEntity):
    """Resolve a Fanekey ``Finger`` value to the matching finger name."""

    _attr_has_entity_name = True
    _attr_translation_key = "ekey_finger_name"
    _attr_device_class = SensorDeviceClass.ENUM

    # Stable, language-independent enum keys ordered by the hub's raw finger
    # value (1..10). Localized labels live in strings.json under
    # ``entity.sensor.ekey_finger_name.state`` — the state itself must not carry
    # display text.
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
    _attr_options = list(_FINGER_KEYS)

    def __init__(
        self,
        module: Module,
        nmbr: int,
        coord: HbtnCoordinator,
        idx: int,
    ) -> None:
        """Initialize the finger-name sensor."""
        super().__init__(coord, context=idx)
        self.idx = idx
        self._module = module
        self._nmbr = nmbr
        self._attr_unique_id = f"Mod_{self._module.uid}_ekey_fngr_ident"
        self._attr_device_info = hbtn_device_info(self._module.uid)
        self._attr_native_value = None

    @override
    async def async_added_to_hass(self) -> None:
        """Subscribe to the underlying sensor's push updates."""
        await super().async_added_to_hass()
        self._module.sensors[self._nmbr].add_listener(self._handle_coordinator_update)

    @override
    async def async_will_remove_from_hass(self) -> None:
        """Unsubscribe from the underlying sensor's push updates."""
        self._module.sensors[self._nmbr].remove_listener(
            self._handle_coordinator_update
        )

    @callback
    @override
    def _handle_coordinator_update(self) -> None:
        """Translate the raw finger value into a finger-name string."""
        id_val = int(self._module.sensors[self._nmbr].value or 0)
        if id_val in range(1, 11):
            self._attr_native_value = self._FINGER_KEYS[id_val - 1]
        else:
            # 0 (idle), 255 (error) or out of range → no current finger.
            self._attr_native_value = None
        self.async_write_ha_state()
