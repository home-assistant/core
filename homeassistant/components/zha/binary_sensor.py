"""Binary sensors on Zigbee Home Automation networks."""
from __future__ import annotations

import functools
from typing import Any

import zigpy.types as t
from zigpy.zcl.clusters.general import OnOff
from zigpy.zcl.clusters.security import IasZone

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_ON, EntityCategory, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .core import discovery
from .core.const import (
    CLUSTER_HANDLER_ACCELEROMETER,
    CLUSTER_HANDLER_BINARY_INPUT,
    CLUSTER_HANDLER_HUE_OCCUPANCY,
    CLUSTER_HANDLER_OCCUPANCY,
    CLUSTER_HANDLER_ON_OFF,
    CLUSTER_HANDLER_ZONE,
    DATA_ZHA,
    SIGNAL_ADD_ENTITIES,
    SIGNAL_ATTR_UPDATED,
)
from .core.registries import ZHA_ENTITIES
from .entity import ZhaEntity

# Zigbee Cluster Library Zone Type to Home Assistant device class
IAS_ZONE_CLASS_MAPPING = {
    IasZone.ZoneType.Motion_Sensor: BinarySensorDeviceClass.MOTION,
    IasZone.ZoneType.Contact_Switch: BinarySensorDeviceClass.OPENING,
    IasZone.ZoneType.Fire_Sensor: BinarySensorDeviceClass.SMOKE,
    IasZone.ZoneType.Water_Sensor: BinarySensorDeviceClass.MOISTURE,
    IasZone.ZoneType.Carbon_Monoxide_Sensor: BinarySensorDeviceClass.GAS,
    IasZone.ZoneType.Vibration_Movement_Sensor: BinarySensorDeviceClass.VIBRATION,
}

IAS_ZONE_NAME_MAPPING = {
    IasZone.ZoneType.Motion_Sensor: "Motion",
    IasZone.ZoneType.Contact_Switch: "Opening",
    IasZone.ZoneType.Fire_Sensor: "Smoke",
    IasZone.ZoneType.Water_Sensor: "Moisture",
    IasZone.ZoneType.Carbon_Monoxide_Sensor: "Gas",
    IasZone.ZoneType.Vibration_Movement_Sensor: "Vibration",
}

STRICT_MATCH = functools.partial(ZHA_ENTITIES.strict_match, Platform.BINARY_SENSOR)
MULTI_MATCH = functools.partial(ZHA_ENTITIES.multipass_match, Platform.BINARY_SENSOR)
CONFIG_DIAGNOSTIC_MATCH = functools.partial(
    ZHA_ENTITIES.config_diagnostic_match, Platform.BINARY_SENSOR
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Zigbee Home Automation binary sensor from config entry."""
    entities_to_create = hass.data[DATA_ZHA][Platform.BINARY_SENSOR]

    unsub = async_dispatcher_connect(
        hass,
        SIGNAL_ADD_ENTITIES,
        functools.partial(
            discovery.async_add_entities, async_add_entities, entities_to_create
        ),
    )
    config_entry.async_on_unload(unsub)


class BinarySensor(ZhaEntity, BinarySensorEntity):
    """ZHA BinarySensor."""

    SENSOR_ATTR: str | None = None

    def __init__(self, unique_id, zha_device, cluster_handlers, **kwargs):
        """Initialize the ZHA binary sensor."""
        super().__init__(unique_id, zha_device, cluster_handlers, **kwargs)
        self._cluster_handler = cluster_handlers[0]

    async def async_added_to_hass(self) -> None:
        """Run when about to be added to hass."""
        await super().async_added_to_hass()
        self.async_accept_signal(
            self._cluster_handler, SIGNAL_ATTR_UPDATED, self.async_set_state
        )

    @property
    def is_on(self) -> bool:
        """Return True if the switch is on based on the state machine."""
        raw_state = self._cluster_handler.cluster.get(self.SENSOR_ATTR)
        if raw_state is None:
            return False
        return self.parse(raw_state)

    @callback
    def async_set_state(self, attr_id, attr_name, value):
        """Set the state."""
        self.async_write_ha_state()

    @staticmethod
    def parse(value: bool | int) -> bool:
        """Parse the raw attribute into a bool state."""
        return bool(value)


@MULTI_MATCH(cluster_handler_names=CLUSTER_HANDLER_ACCELEROMETER)
class Accelerometer(BinarySensor):
    """ZHA BinarySensor."""

    SENSOR_ATTR = "acceleration"
    _attr_name: str = "Accelerometer"
    _attr_device_class: BinarySensorDeviceClass = BinarySensorDeviceClass.MOVING


@MULTI_MATCH(cluster_handler_names=CLUSTER_HANDLER_OCCUPANCY)
class Occupancy(BinarySensor):
    """ZHA BinarySensor."""

    SENSOR_ATTR = "occupancy"
    _attr_name: str = "Occupancy"
    _attr_device_class: BinarySensorDeviceClass = BinarySensorDeviceClass.OCCUPANCY


@MULTI_MATCH(cluster_handler_names=CLUSTER_HANDLER_HUE_OCCUPANCY)
class HueOccupancy(Occupancy):
    """ZHA Hue occupancy."""


@STRICT_MATCH(cluster_handler_names=CLUSTER_HANDLER_ON_OFF)
class Opening(BinarySensor):
    """ZHA OnOff BinarySensor."""

    SENSOR_ATTR = "on_off"
    _attr_name: str = "Opening"
    _attr_device_class: BinarySensorDeviceClass = BinarySensorDeviceClass.OPENING

    # Client/out cluster attributes aren't stored in the zigpy database, but are properly stored in the runtime cache.
    # We need to manually restore the last state from the sensor state to the runtime cache for now.
    @callback
    def async_restore_last_state(self, last_state):
        """Restore previous state to zigpy cache."""
        self._cluster_handler.cluster.update_attribute(
            OnOff.attributes_by_name[self.SENSOR_ATTR].id,
            t.Bool.true if last_state.state == STATE_ON else t.Bool.false,
        )


@MULTI_MATCH(cluster_handler_names=CLUSTER_HANDLER_BINARY_INPUT)
class BinaryInput(BinarySensor):
    """ZHA BinarySensor."""

    SENSOR_ATTR = "present_value"
    _attr_name: str = "Binary input"


@STRICT_MATCH(
    cluster_handler_names=CLUSTER_HANDLER_ON_OFF,
    manufacturers="IKEA of Sweden",
    models=lambda model: isinstance(model, str)
    and model is not None
    and model.find("motion") != -1,
)
@STRICT_MATCH(
    cluster_handler_names=CLUSTER_HANDLER_ON_OFF,
    manufacturers="Philips",
    models={"SML001", "SML002"},
)
class Motion(Opening):
    """ZHA OnOff BinarySensor with motion device class."""

    _attr_name: str = "Motion"
    _attr_device_class: BinarySensorDeviceClass = BinarySensorDeviceClass.MOTION


@MULTI_MATCH(cluster_handler_names=CLUSTER_HANDLER_ZONE)
class IASZone(BinarySensor):
    """ZHA IAS BinarySensor."""

    SENSOR_ATTR = "zone_status"

    @property
    def name(self) -> str | None:
        """Return the name of the sensor."""
        zone_type = self._cluster_handler.cluster.get("zone_type")
        return IAS_ZONE_NAME_MAPPING.get(zone_type, "iaszone")

    @property
    def device_class(self) -> BinarySensorDeviceClass | None:
        """Return device class from component DEVICE_CLASSES."""
        zone_type = self._cluster_handler.cluster.get("zone_type")
        return IAS_ZONE_CLASS_MAPPING.get(zone_type)

    @staticmethod
    def parse(value: bool | int) -> bool:
        """Parse the raw attribute into a bool state."""
        return BinarySensor.parse(value & 3)  # use only bit 0 and 1 for alarm state

    # temporary code to migrate old IasZone sensors to update attribute cache state once
    # remove in 2024.4.0
    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return state attributes."""
        return {"migrated_to_cache": True}  # writing new state means we're migrated

    # temporary migration code
    @callback
    def async_restore_last_state(self, last_state):
        """Restore previous state."""
        # trigger migration if extra state attribute is not present
        if "migrated_to_cache" not in last_state.attributes:
            self.migrate_to_zigpy_cache(last_state)

    # temporary migration code
    @callback
    def migrate_to_zigpy_cache(self, last_state):
        """Save old IasZone sensor state to attribute cache."""
        # previous HA versions did not update the attribute cache for IasZone sensors, so do it once here
        # a HA state write is triggered shortly afterwards and writes the "migrated_to_cache" extra state attribute
        if last_state.state == STATE_ON:
            migrated_state = IasZone.ZoneStatus.Alarm_1
        else:
            migrated_state = IasZone.ZoneStatus(0)

        self._cluster_handler.cluster.update_attribute(
            IasZone.attributes_by_name[self.SENSOR_ATTR].id, migrated_state
        )


@STRICT_MATCH(cluster_handler_names=CLUSTER_HANDLER_ZONE, models={"WL4200", "WL4200S"})
class SinopeLeakStatus(BinarySensor):
    """Sinope water leak sensor."""

    SENSOR_ATTR = "leak_status"
    _attr_name = "Moisture"
    _attr_device_class = BinarySensorDeviceClass.MOISTURE


@MULTI_MATCH(
    cluster_handler_names="tuya_manufacturer",
    manufacturers={
        "_TZE200_htnnfasr",
    },
)
class FrostLock(BinarySensor, id_suffix="frost_lock"):
    """ZHA BinarySensor."""

    SENSOR_ATTR = "frost_lock"
    _attr_device_class: BinarySensorDeviceClass = BinarySensorDeviceClass.LOCK
    _attr_name: str = "Frost lock"


@MULTI_MATCH(cluster_handler_names="ikea_airpurifier")
class ReplaceFilter(BinarySensor, id_suffix="replace_filter"):
    """ZHA BinarySensor."""

    SENSOR_ATTR = "replace_filter"
    _attr_device_class: BinarySensorDeviceClass = BinarySensorDeviceClass.PROBLEM
    _attr_entity_category: EntityCategory = EntityCategory.DIAGNOSTIC
    _attr_name: str = "Replace filter"


@MULTI_MATCH(cluster_handler_names="opple_cluster", models={"aqara.feeder.acn001"})
class AqaraPetFeederErrorDetected(BinarySensor, id_suffix="error_detected"):
    """ZHA aqara pet feeder error detected binary sensor."""

    SENSOR_ATTR = "error_detected"
    _attr_device_class: BinarySensorDeviceClass = BinarySensorDeviceClass.PROBLEM
    _attr_name: str = "Error detected"


@MULTI_MATCH(
    cluster_handler_names="opple_cluster",
    models={"lumi.plug.mmeu01", "lumi.plug.maeu01"},
)
class XiaomiPlugConsumerConnected(BinarySensor, id_suffix="consumer_connected"):
    """ZHA Xiaomi plug consumer connected binary sensor."""

    SENSOR_ATTR = "consumer_connected"
    _attr_name: str = "Consumer connected"
    _attr_device_class: BinarySensorDeviceClass = BinarySensorDeviceClass.PLUG


@MULTI_MATCH(cluster_handler_names="opple_cluster", models={"lumi.airrtc.agl001"})
class AqaraThermostatWindowOpen(BinarySensor, id_suffix="window_open"):
    """ZHA Aqara thermostat window open binary sensor."""

    SENSOR_ATTR = "window_open"
    _attr_device_class: BinarySensorDeviceClass = BinarySensorDeviceClass.WINDOW
    _attr_name: str = "Window open"


@MULTI_MATCH(cluster_handler_names="opple_cluster", models={"lumi.airrtc.agl001"})
class AqaraThermostatValveAlarm(BinarySensor, id_suffix="valve_alarm"):
    """ZHA Aqara thermostat valve alarm binary sensor."""

    SENSOR_ATTR = "valve_alarm"
    _attr_device_class: BinarySensorDeviceClass = BinarySensorDeviceClass.PROBLEM
    _attr_name: str = "Valve alarm"


@CONFIG_DIAGNOSTIC_MATCH(
    cluster_handler_names="opple_cluster", models={"lumi.airrtc.agl001"}
)
class AqaraThermostatCalibrated(BinarySensor, id_suffix="calibrated"):
    """ZHA Aqara thermostat calibrated binary sensor."""

    SENSOR_ATTR = "calibrated"
    _attr_entity_category: EntityCategory = EntityCategory.DIAGNOSTIC
    _attr_name: str = "Calibrated"


@CONFIG_DIAGNOSTIC_MATCH(
    cluster_handler_names="opple_cluster", models={"lumi.airrtc.agl001"}
)
class AqaraThermostatExternalSensor(BinarySensor, id_suffix="sensor"):
    """ZHA Aqara thermostat external sensor binary sensor."""

    SENSOR_ATTR = "sensor"
    _attr_entity_category: EntityCategory = EntityCategory.DIAGNOSTIC
    _attr_name: str = "External sensor"


@MULTI_MATCH(cluster_handler_names="opple_cluster", models={"lumi.sensor_smoke.acn03"})
class AqaraLinkageAlarmState(BinarySensor, id_suffix="linkage_alarm_state"):
    """ZHA Aqara linkage alarm state binary sensor."""

    SENSOR_ATTR = "linkage_alarm_state"
    _attr_name: str = "Linkage alarm state"
    _attr_device_class: BinarySensorDeviceClass = BinarySensorDeviceClass.SMOKE
