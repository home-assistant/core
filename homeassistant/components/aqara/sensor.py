"""Support for Aqara sensors."""
from __future__ import annotations

import copy
from dataclasses import dataclass

from aqara_iot import AqaraDeviceManager, AqaraPoint

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONCENTRATION_MILLIGRAMS_PER_CUBIC_METER,
    ELECTRIC_POTENTIAL_VOLT,
    LIGHT_LUX,
    PERCENTAGE,
    PRESSURE_KPA,
    TEMP_CELSIUS,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from . import HomeAssistantAqaraData
from .base import (
    AqaraEntity,
    DeviceValueRange,
    EnumTypeData,
    IntegerTypeData,
    find_aqara_device_points_and_register,
)
from .const import (
    AQARA_DISCOVERY_NEW,
    AQARA_HA_SIGNAL_UPDATE_POINT_VALUE,
    DOMAIN,
    EMPTY_UNIT,
    UnitOfMeasurement,
)
from .device_trigger import AQARA_EVENTS_MAP as aqara_events_map
from .util import string_dot_to_underline


@dataclass
class AqaraSensorEntityDescription(SensorEntityDescription):
    """Describes Aqara sensor entity."""

    scale: float | None = None
    precision: int | None = None
    data_type: str | None = None
    enum_value_map: dict[str, str] | None = None
    # native_unit_of_measurement: str | None = EMPTY_UNIT

    def set_key(self, key) -> AqaraSensorEntityDescription:
        """Set key of sensor Description."""
        entity_description = copy.copy(self)
        entity_description.key = key
        return entity_description

    def set_name(self, name) -> AqaraSensorEntityDescription:
        """Set name of sensor Description."""
        self.name = name
        return self

    def set_value_map(self, value_map) -> AqaraSensorEntityDescription:
        """Set name of sensor Description."""
        self.enum_value_map = value_map
        return self


# Commonly used battery sensors, that are re-used in the sensors down below.
BATTERY_SENSORS: tuple[AqaraSensorEntityDescription, ...] = (
    AqaraSensorEntityDescription(
        key="8.0.9001",
        name="Battery State",
        icon="mdi:battery",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    AqaraSensorEntityDescription(
        key="8.0.2008",
        name="voltage",
        native_unit_of_measurement=ELECTRIC_POTENTIAL_VOLT,
        device_class=SensorDeviceClass.BATTERY,
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        scale=0.001,
        precision=2,
    ),
)

temp_desc = AqaraSensorEntityDescription(
    key="0.1.85",
    name="Current Temperature",
    device_class=SensorDeviceClass.TEMPERATURE,
    state_class=SensorStateClass.MEASUREMENT,
    native_unit_of_measurement=TEMP_CELSIUS,
    scale=0.01,
    precision=1,
)
humidity_desc = AqaraSensorEntityDescription(
    key="0.2.85",
    name="Current humidity",
    device_class=SensorDeviceClass.TEMPERATURE,
    state_class=SensorStateClass.MEASUREMENT,
    native_unit_of_measurement=PERCENTAGE,
    scale=0.01,
    precision=1,
)
co2_desc = AqaraSensorEntityDescription(
    key="0.6.85",
    name="CO2",
    device_class=SensorDeviceClass.CO2,
    state_class=SensorStateClass.MEASUREMENT,
    native_unit_of_measurement=CONCENTRATION_MILLIGRAMS_PER_CUBIC_METER,
    scale=0.01,
)

pm25_out_desc = AqaraSensorEntityDescription(
    key="0.19.85",
    name="PM2.5",
    device_class=SensorDeviceClass.PM25,
    state_class=SensorStateClass.MEASUREMENT,
    native_unit_of_measurement=CONCENTRATION_MILLIGRAMS_PER_CUBIC_METER,
)


pm25_desc = AqaraSensorEntityDescription(
    key="0.20.85",
    name="PM2.5",
    device_class=SensorDeviceClass.PM25,
    state_class=SensorStateClass.MEASUREMENT,
    native_unit_of_measurement=CONCENTRATION_MILLIGRAMS_PER_CUBIC_METER,
)
pm25_evaluate_desc = AqaraSensorEntityDescription(
    key="0.20.85",
    name="PM2.5",
    device_class=SensorDeviceClass.PM25,
    state_class=SensorStateClass.MEASUREMENT,
    native_unit_of_measurement=CONCENTRATION_MILLIGRAMS_PER_CUBIC_METER,
)

air_pressure_desc = AqaraSensorEntityDescription(
    key="0.3.85",
    name="pressure",
    device_class=SensorDeviceClass.PRESSURE,
    state_class=SensorStateClass.MEASUREMENT,
    native_unit_of_measurement=PRESSURE_KPA,
    scale=0.001,
    precision=2,
)

illuminance_desc = AqaraSensorEntityDescription(
    key="0.3.85",
    name="illuminance",
    device_class=SensorDeviceClass.ILLUMINANCE,
    state_class=SensorStateClass.MEASUREMENT,
    native_unit_of_measurement=LIGHT_LUX,
    scale=1,
    precision=0,
)

tvoc_desc = AqaraSensorEntityDescription(
    key="0.3.85",
    name="TVOC",
    device_class=SensorDeviceClass.GAS,
    state_class=SensorStateClass.MEASUREMENT,
    native_unit_of_measurement=CONCENTRATION_MILLIGRAMS_PER_CUBIC_METER,
    scale=1,
    precision=0,
)

# vibration
vibration_desc = AqaraSensorEntityDescription(
    key="0.3.85",
    name="vibration",
)

common_desp = AqaraSensorEntityDescription(
    key="0.3.85",
    name="common",
)

cube_status_desp = AqaraSensorEntityDescription(
    key="13.1.85",
    name="cube status",
)

cube_rotate_degree_desp = AqaraSensorEntityDescription(
    key="0.3.85",
    name="Rotating degree",
    device_class=SensorDeviceClass.AQI,
    state_class=SensorStateClass.MEASUREMENT,
    native_unit_of_measurement=EMPTY_UNIT,
    scale=1,
    precision=0,
)
cube_rotate_side = AqaraSensorEntityDescription(
    key="13.101.85",
    name="action surface",
    device_class=SensorDeviceClass.AQI,
    state_class=SensorStateClass.MEASUREMENT,
    native_unit_of_measurement=EMPTY_UNIT,
    scale=1,
    precision=0,
)
cube_rotate_side_status = AqaraSensorEntityDescription(
    key="13.103.85",
    name="Top surface",
    device_class=SensorDeviceClass.AQI,
    state_class=SensorStateClass.MEASUREMENT,
    native_unit_of_measurement=EMPTY_UNIT,
    scale=1,
    precision=0,
)
common_cube = (
    cube_status_desp,
    cube_rotate_degree_desp,
    *BATTERY_SENSORS,
)


switch_ch1_status_desc = AqaraSensorEntityDescription(
    key="13.1.85",
    name="button 1",
    icon="mdi:light-switch",
)

switch_ch2_status_desc = AqaraSensorEntityDescription(
    key="13.2.85",
    name="button 2",
    icon="mdi:light-switch",
)

switch_ch3_status_desc = AqaraSensorEntityDescription(
    key="13.3.85",
    name="button 3",
    icon="mdi:light-switch",
)

dual_switch_status_desc = AqaraSensorEntityDescription(
    key="13.3.85",
    name="button",
    icon="mdi:light-switch",
    native_unit_of_measurement=EMPTY_UNIT,
)


SENSORS: dict[str, tuple[AqaraSensorEntityDescription, ...]] = {
    "lumi.sensor_ht.jcn001": (
        temp_desc,
        humidity_desc,
        air_pressure_desc,
        *BATTERY_SENSORS,
    ),
    "lumi.sen_ill.eicn01": (
        illuminance_desc,
        *BATTERY_SENSORS,
    ),
    "aqara.adetector.drcn01": (
        temp_desc.set_key("0.1.85").set_name("temperature"),
        humidity_desc.set_key("0.2.85").set_name("humidity"),
        co2_desc.set_key("0.6.85").set_name("co2"),
        co2_desc.set_key("0.19.85").set_name("co2"),
        pm25_desc.set_key("0.19.85").set_name("pm25"),
        pm25_desc.set_key("0.20.85").set_name("pm25"),
        pm25_evaluate_desc.set_key("13.12.85").set_name("pm25"),
        pm25_desc.set_key("13.8.85").set_name("pm25"),
        *BATTERY_SENSORS,
    ),
    "lumi.airmonitor.acn01": (
        temp_desc.set_key("0.1.85").set_name("temperature"),
        humidity_desc.set_key("0.2.85").set_name("humidity"),
        tvoc_desc.set_key("0.3.85").set_name("tvoc"),
        common_desp.set_key("13.1.85").set_name("TVOC level"),
        *BATTERY_SENSORS,
    ),
    "miot.airmonitor.b1": (
        pm25_desc.set_key("13.1.85").set_name("PM2.5 Density"),
        humidity_desc.set_key("13.3.85").set_name("Environment Relative Humidity"),
        temp_desc.set_key("13.4.85").set_name("Environment Temperature"),
        co2_desc.set_key("13.5.85").set_name("Environment CO2 Density"),
        tvoc_desc.set_key("13.6.85").set_name("Environment TVOC Density"),
        *BATTERY_SENSORS,
    ),
    "miot.airmonitor.v1": (
        pm25_desc.set_key("13.1.85").set_name("PM2.5 Density"),
        *BATTERY_SENSORS,
    ),
    "lumi.airm.fhac01": (
        temp_desc.set_key("0.1.85").set_name("temperature"),
        humidity_desc.set_key("0.2.85").set_name("humidity"),
        co2_desc.set_key("0.6.85").set_name("CO2"),
        pm25_desc.set_key("0.19.85").set_name("PM2.5"),
        common_desp.set_key("13.11.85").set_name("CO2"),
        common_desp.set_key("13.12.85").set_name("PM2.5"),
        *BATTERY_SENSORS,
    ),
    "lumi.sensor_gas.acn001": (
        temp_desc.set_key("0.1.85").set_name("temperature"),
        tvoc_desc.set_key("0.5.85").set_name("tvoc"),
        *BATTERY_SENSORS,
    ),
    "lumi.sensor_gas.jcn001": (
        temp_desc.set_key("0.1.85").set_name("temperature"),
        tvoc_desc.set_key("0.5.85").set_name("tvoc"),
        *BATTERY_SENSORS,
    ),
    "lumi.sen_gas.hrcn01": (
        temp_desc.set_key("0.1.85").set_name("temperature"),
        tvoc_desc.set_key("0.5.85").set_name("tvoc"),
        common_desp.set_key("14.1.85").set_name("status"),
        *BATTERY_SENSORS,
    ),
    "lumi.sensor_gas.acn02": (
        temp_desc.set_key("0.1.85").set_name("temperature"),
        tvoc_desc.set_key("0.5.85").set_name("tvoc"),
        common_desp.set_key("14.1.85").set_name("status"),
        *BATTERY_SENSORS,
    ),
    "lumi.sensor_natgas.v1": (
        tvoc_desc.set_key("0.1.85").set_name("tvoc"),
        common_desp.set_key("14.1.85").set_name("status"),
        *BATTERY_SENSORS,
    ),
    "lumi.sensor_smoke.acn05": (
        tvoc_desc.set_key("0.5.85").set_name("tvoc"),
        *BATTERY_SENSORS,
    ),
    "lumi.sensor_smoke.jcn01": (
        tvoc_desc.set_key("0.5.85").set_name("tvoc"),
        *BATTERY_SENSORS,
    ),
    "lumi.sensor_smoke.acn03": (
        tvoc_desc.set_key("0.5.85").set_name("tvoc"),
        *BATTERY_SENSORS,
    ),
    "lumi.sensor_smoke.acn02": (
        common_desp.set_key("0.1.85").set_name("density"),
        common_desp.set_key("14.1.111").set_name("alarm status"),
        *BATTERY_SENSORS,
    ),
    "lumi.sensor_smoke.v1": (
        common_desp.set_key("0.1.85").set_name("density"),
        common_desp.set_key("14.1.111").set_name("alarm status"),
        *BATTERY_SENSORS,
    ),
    "aqara.sensor_smoke.eicn01": (
        common_desp.set_key("13.1.85").set_name("alarm status"),
        *BATTERY_SENSORS,
    ),
    # cube###################
    "lumi.remote.cagl02": (  # wareless switch
        cube_status_desp,
        cube_rotate_degree_desp.set_key("0.21.85"),
        cube_rotate_side,
        cube_rotate_side_status,
        *BATTERY_SENSORS,
    ),
    # ########################################################
    "aqara.tow_w.acn001": (
        temp_desc.set_key("0.1.85").set_name("current temperature"),
    ),
    # ####################lock################################
    "lumi.vibration.aq1": (
        common_desp.set_key("13.1.85").set_name("vibration"),
        *BATTERY_SENSORS,
    ),
    "lumi.vibration.agl01": (
        common_desp.set_key("13.7.85").set_name("vibration"),
        *BATTERY_SENSORS,
    ),
    # wireless switch######################
    "lumi.remote.acn009": (  # # wareless switch
        switch_ch1_status_desc,
        switch_ch2_status_desc,
        dual_switch_status_desc,
        *BATTERY_SENSORS,
    ),
    "lumi.remote.acn008": (  # wareless switch
        switch_ch1_status_desc,
        *BATTERY_SENSORS,
    ),
    "lumi.remote.jcn002": (  # wareless switch
        switch_ch1_status_desc,
        *BATTERY_SENSORS,
    ),
    "lumi.remote.acn007": (  # wareless switch
        switch_ch1_status_desc,
        *BATTERY_SENSORS,
    ),
    "lumi.remote.acn003": (  # wareless switch
        switch_ch1_status_desc,
        *BATTERY_SENSORS,
    ),
    "lumi.remote.acn004": (  # wareless switch
        switch_ch1_status_desc,
        switch_ch2_status_desc,
        dual_switch_status_desc,
        *BATTERY_SENSORS,
    ),
    "lumi.remote.acn002": (  # wareless switch
        switch_ch1_status_desc,
        switch_ch2_status_desc,
        dual_switch_status_desc,
        *BATTERY_SENSORS,
    ),
    "lumi.remote.acn001": (  # wareless switch
        switch_ch1_status_desc,
        *BATTERY_SENSORS,
    ),
    "lumi.remote.rkba01": (  # wareless switch
        switch_ch1_status_desc,
        cube_rotate_side.set_key("0.21.85").set_name("current rotate angle"),
        cube_rotate_side.set_key("0.22.85").set_name("sum rotate angle"),
        cube_rotate_side.set_key("0.23.85").set_name("current rotate angle percent"),
        cube_rotate_side.set_key("0.24.85").set_name("sum rotate angle percent"),
        cube_rotate_side.set_key("0.25.85").set_name("rotate_cumulate_time"),
        cube_rotate_side.set_key("0.26.85").set_name("press_current_rotate_angle"),
        cube_rotate_side.set_key("0.27.85").set_name("press_sum_rotate_angle"),
        cube_rotate_side.set_key("0.28.85").set_name("press_cur_rotate_angle_per"),
        cube_rotate_side.set_key("0.29.85").set_name("press_sum_rotate_angle_percent"),
        cube_rotate_side.set_key("0.20.85").set_name("spress_rotate_cumulate_time"),
        *BATTERY_SENSORS,
    ),
    "lumi.switch.n6eic2": (  # wareless switch
        switch_ch1_status_desc,
        switch_ch2_status_desc,
        switch_ch3_status_desc,
        switch_ch1_status_desc.set_key("13.4.85").set_name("button 4"),
        switch_ch2_status_desc.set_key("13.6.85").set_name(
            "button 5"
        ),  # key is 13.6.85 not 13.5.85
        switch_ch3_status_desc.set_key("13.7.85").set_name(
            "button 6"
        ),  # key is 13.7.85
        *BATTERY_SENSORS,
    ),
    "lumi.switch.n4eic2": (  # wareless switch
        switch_ch1_status_desc,
        switch_ch2_status_desc,
        switch_ch3_status_desc,
        switch_ch1_status_desc.set_key("13.4.85").set_name("button 4"),
        *BATTERY_SENSORS,
    ),
    "lumi.switch.n3eic2": (  # wareless switch
        switch_ch1_status_desc,
        switch_ch2_status_desc,
        switch_ch3_status_desc,
        *BATTERY_SENSORS,
    ),
    "lumi.switch.n2eic2": (  # wareless switch
        switch_ch1_status_desc,
        switch_ch2_status_desc,
        *BATTERY_SENSORS,
    ),
    "lumi.switch.n1eic2": (  # wareless switch
        switch_ch1_status_desc,
        *BATTERY_SENSORS,
    ),
    "lumi.remote.b1akr1": (  # wareless switch
        switch_ch1_status_desc,
        switch_ch2_status_desc,
        *BATTERY_SENSORS,
    ),
    "lumi.remote.b286acn03": (  # wareless switch
        switch_ch1_status_desc,
        switch_ch2_status_desc,
        *BATTERY_SENSORS,
    ),
    "lumi.remote.b686opcn01": (  # wareless switch
        switch_ch1_status_desc,
        switch_ch2_status_desc,
        switch_ch3_status_desc,
        switch_ch1_status_desc.set_key("13.4.85").set_name("button 4"),
        switch_ch2_status_desc.set_key("13.6.85").set_name("button 5"),
        switch_ch3_status_desc.set_key("13.7.85").set_name(
            "button 6"
        ),  # key is 13.7.85
        *BATTERY_SENSORS,
    ),
    "lumi.remote.b486opcn01": (  # wareless switch
        switch_ch1_status_desc,
        switch_ch2_status_desc,
        switch_ch3_status_desc,
        switch_ch1_status_desc.set_key("13.4.85").set_name("button 4"),
        *BATTERY_SENSORS,
    ),
    "lumi.remote.b286opcn01": (  # wareless switch
        switch_ch1_status_desc,
        switch_ch2_status_desc,
        *BATTERY_SENSORS,
    ),
    "lumi.remote.b186acn03": (  # wareless switch
        switch_ch1_status_desc,
        *BATTERY_SENSORS,
    ),
    "lumi.remote.b1acn02": (  # wareless switch
        switch_ch1_status_desc,
        *BATTERY_SENSORS,
    ),
    "lumi.sensor_switch.aq3": (  # wareless switch
        switch_ch1_status_desc,
        *BATTERY_SENSORS,
    ),
    "lumi.sensor_switch.v1": (  # wareless switch
        switch_ch1_status_desc,
        *BATTERY_SENSORS,
    ),
    "lumi.sensor_switch.es3": (  # wareless switch
        switch_ch1_status_desc,
        *BATTERY_SENSORS,
    ),
    "lumi.sensor_switch.es2": (  # wareless switch
        switch_ch1_status_desc,
        *BATTERY_SENSORS,
    ),
    "lumi.sensor_switch.v2": (  # wareless switch
        switch_ch1_status_desc,
        *BATTERY_SENSORS,
    ),
    "lumi.sensor_switch.aq2": (  # wareless switch
        switch_ch1_status_desc,
        *BATTERY_SENSORS,
    ),
    "lumi.sensor_86sw2.v1": (  # wareless switch
        switch_ch1_status_desc,
        switch_ch2_status_desc,
        *BATTERY_SENSORS,
    ),
    "lumi.sensor_86sw2.es1": (  # wareless switch
        switch_ch1_status_desc,
        switch_ch2_status_desc,
        *BATTERY_SENSORS,
    ),
    "lumi.remote.b1acn01": (  # wareless switch
        switch_ch1_status_desc,
        *BATTERY_SENSORS,
    ),
    "lumi.sensor_86sw1.es1": (
        switch_ch1_status_desc,
        *BATTERY_SENSORS,
    ),
    "lumi.remote.b186acn01": (
        switch_ch1_status_desc,
        *BATTERY_SENSORS,
    ),
    "lumi.sensor_86sw1.aq1": (
        switch_ch1_status_desc,
        *BATTERY_SENSORS,
    ),
    "lumi.sensor_86sw2.aq1": (
        switch_ch1_status_desc,
        switch_ch2_status_desc,
        *BATTERY_SENSORS,
    ),
    "lumi.remote.b286acn01": (  # wareless switch
        switch_ch1_status_desc,
        switch_ch2_status_desc,
        *BATTERY_SENSORS,
    ),
    "lumi.sensor_86sw1.v1": (  # wareless switch）
        switch_ch1_status_desc,
        *BATTERY_SENSORS,
    ),
    "lumi.remote.b28ac1": (  # wareless switch
        switch_ch1_status_desc,
        switch_ch2_status_desc,
        *BATTERY_SENSORS,
    ),
    "lumi.remote.b18ac1": (  # wareless switch
        switch_ch1_status_desc,
        *BATTERY_SENSORS,
    ),
}

common_temp_sensor = SENSORS["lumi.sensor_ht.jcn001"]


SENSORS["lumi.sensor_ht.agl02"] = common_temp_sensor
SENSORS["lumi.weather.es1"] = common_temp_sensor
SENSORS["lumi.weather.v1"] = common_temp_sensor
SENSORS["lumi.sensor_ht.v1"] = common_temp_sensor
SENSORS["lumi.sensor_ht.es1"] = common_temp_sensor


common_illumination_sensor = SENSORS["lumi.sen_ill.eicn01"]
SENSORS["lumi.sen_ill.akr01"] = common_illumination_sensor
SENSORS["lumi.sen_ill.mgl01"] = common_illumination_sensor
SENSORS["lumi.sen_ill.agl01"] = common_illumination_sensor

SENSORS["lumi.remote.jcn001"] = common_cube

SENSORS["lumi.remote.eicn01"] = common_cube


SENSORS["lumi.remote.cagl01"] = common_cube

SENSORS["lumi.sensor_cube.aqgl01"] = common_cube

SENSORS["lumi.sensor_cube.es1"] = common_cube

SENSORS["lumi.sensor_cube.v1"] = common_cube


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Aqara sensor dynamically through Aqara discovery."""
    hass_data: HomeAssistantAqaraData = hass.data[DOMAIN][entry.entry_id]

    @callback
    def async_discover_device(device_ids: list[str]) -> None:
        """Discover and add a discovered Aqara sensor."""
        entities: list[AqaraSensorEntity] = []

        def append_entity(aqara_point, description):

            entity: AqaraSensorEntity = AqaraSensorEntity(
                aqara_point, hass_data.device_manager, description
            )
            entities.append(entity)

            async_dispatcher_connect(
                hass,
                f"{AQARA_HA_SIGNAL_UPDATE_POINT_VALUE}_{string_dot_to_underline(aqara_point.id)}",
                entity.async_update_attr,
            )

        find_aqara_device_points_and_register(
            hass, entry.entry_id, hass_data, device_ids, SENSORS, append_entity
        )
        async_add_entities(entities)

    async_discover_device([*hass_data.device_manager.device_map])

    entry.async_on_unload(
        async_dispatcher_connect(hass, AQARA_DISCOVERY_NEW, async_discover_device)
    )


class AqaraSensorEntity(AqaraEntity, SensorEntity):
    """Aqara Sensor Entity."""

    entity_description: AqaraSensorEntityDescription

    _value_range: DeviceValueRange | None = None
    _type_data: IntegerTypeData | EnumTypeData | None = None
    _uom: UnitOfMeasurement | None = None

    def __init__(
        self,
        point: AqaraPoint,
        device_manager: AqaraDeviceManager,
        description: AqaraSensorEntityDescription,
    ) -> None:
        """Init Aqara sensor."""
        super().__init__(point, device_manager)
        self.entity_description = description

    async def async_update_attr(self, point: AqaraPoint) -> None:
        """Async_update_attr."""
        model = self.device_info.get("model")
        model_info = aqara_events_map.get(str(model))
        if model_info is None:
            return

        resources = model_info.get(point.resource_id)
        if resources is None:
            return

        event_type = resources.get(point.value)

        if self.registry_entry is not None:
            device_id = self.registry_entry.device_id
        else:
            device_id = ""

        if event_type is not None:
            message = {
                "device_id": device_id,
                "type": event_type,
            }
            self.hass.bus.async_fire("aqara_event", message)

    @property
    def native_value(self) -> StateType:
        """Return the value reported by the sensor."""
        point_value = self.point.get_value()
        if point_value is None or point_value == "":
            return None
        value: float = 0
        try:
            if self.entity_description.scale is not None:
                value = float(point_value) * self.entity_description.scale
            else:
                value = float(point_value)
            if self.entity_description.precision is not None:
                if self.entity_description.precision == 0:
                    return round(value)

                return round(value, self.entity_description.precision)
        except ValueError:
            pass
        return value
