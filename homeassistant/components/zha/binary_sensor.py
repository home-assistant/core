"""Binary sensors on Zigbee Home Automation networks."""
from __future__ import annotations

import functools

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_ON, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .core import discovery
from .core.const import (
    CHANNEL_ACCELEROMETER,
    CHANNEL_BINARY_INPUT,
    CHANNEL_OCCUPANCY,
    CHANNEL_ON_OFF,
    CHANNEL_ZONE,
    DATA_ZHA,
    SIGNAL_ADD_ENTITIES,
    SIGNAL_ATTR_UPDATED,
)
from .core.registries import ZHA_ENTITIES
from .entity import ZhaEntity

# Zigbee Cluster Library Zone Type to Home Assistant device class
CLASS_MAPPING = {
    0x000D: BinarySensorDeviceClass.MOTION,
    0x0015: BinarySensorDeviceClass.OPENING,
    0x0028: BinarySensorDeviceClass.SMOKE,
    0x002A: BinarySensorDeviceClass.MOISTURE,
    0x002B: BinarySensorDeviceClass.GAS,
    0x002D: BinarySensorDeviceClass.VIBRATION,
}

STRICT_MATCH = functools.partial(ZHA_ENTITIES.strict_match, Platform.BINARY_SENSOR)
MULTI_MATCH = functools.partial(ZHA_ENTITIES.multipass_match, Platform.BINARY_SENSOR)


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

    def __init__(self, unique_id, zha_device, channels, **kwargs):
        """Initialize the ZHA binary sensor."""
        super().__init__(unique_id, zha_device, channels, **kwargs)
        self._channel = channels[0]

    async def async_added_to_hass(self) -> None:
        """Run when about to be added to hass."""
        await super().async_added_to_hass()
        self.async_accept_signal(
            self._channel, SIGNAL_ATTR_UPDATED, self.async_set_state
        )

    @callback
    def async_restore_last_state(self, last_state):
        """Restore previous state."""
        super().async_restore_last_state(last_state)
        self._state = last_state.state == STATE_ON

    @property
    def is_on(self) -> bool:
        """Return True if the switch is on based on the state machine."""
        if self._state is None:
            return False
        return self._state

    @callback
    def async_set_state(self, attr_id, attr_name, value):
        """Set the state."""
        if self.SENSOR_ATTR is None or self.SENSOR_ATTR != attr_name:
            return
        self._state = bool(value)
        self.async_write_ha_state()

    async def async_update(self) -> None:
        """Attempt to retrieve on off state from the binary sensor."""
        await super().async_update()
        attribute = getattr(self._channel, "value_attribute", "on_off")
        attr_value = await self._channel.get_attribute_value(attribute)
        if attr_value is not None:
            self._state = attr_value


@MULTI_MATCH(channel_names=CHANNEL_ACCELEROMETER)
class Accelerometer(BinarySensor):
    """ZHA BinarySensor."""

    SENSOR_ATTR = "acceleration"
    _attr_device_class: BinarySensorDeviceClass = BinarySensorDeviceClass.MOVING


@MULTI_MATCH(channel_names=CHANNEL_OCCUPANCY)
class Occupancy(BinarySensor):
    """ZHA BinarySensor."""

    SENSOR_ATTR = "occupancy"
    _attr_device_class: BinarySensorDeviceClass = BinarySensorDeviceClass.OCCUPANCY


@STRICT_MATCH(channel_names=CHANNEL_ON_OFF)
class Opening(BinarySensor):
    """ZHA BinarySensor."""

    SENSOR_ATTR = "on_off"
    _attr_device_class: BinarySensorDeviceClass = BinarySensorDeviceClass.OPENING


@MULTI_MATCH(channel_names=CHANNEL_BINARY_INPUT)
class BinaryInput(BinarySensor):
    """ZHA BinarySensor."""

    SENSOR_ATTR = "present_value"


@STRICT_MATCH(
    channel_names=CHANNEL_ON_OFF,
    manufacturers="IKEA of Sweden",
    models=lambda model: isinstance(model, str)
    and model is not None
    and model.find("motion") != -1,
)
@STRICT_MATCH(
    channel_names=CHANNEL_ON_OFF,
    manufacturers="Philips",
    models={"SML001", "SML002"},
)
class Motion(BinarySensor):
    """ZHA BinarySensor."""

    SENSOR_ATTR = "on_off"
    _attr_device_class: BinarySensorDeviceClass = BinarySensorDeviceClass.MOTION


@MULTI_MATCH(channel_names=CHANNEL_ZONE)
class IASZone(BinarySensor):
    """ZHA IAS BinarySensor."""

    SENSOR_ATTR = "zone_status"

    @property
    def device_class(self) -> BinarySensorDeviceClass | None:
        """Return device class from component DEVICE_CLASSES."""
        return CLASS_MAPPING.get(self._channel.cluster.get("zone_type"))

    async def async_update(self) -> None:
        """Attempt to retrieve on off state from the binary sensor."""
        await super().async_update()
        value = await self._channel.get_attribute_value("zone_status")
        if value is not None:
            self._state = value & 3


@MULTI_MATCH(
    channel_names="tuya_manufacturer",
    manufacturers={
        "_TZE200_htnnfasr",
    },
)
class FrostLock(BinarySensor, id_suffix="frost_lock"):
    """ZHA BinarySensor."""

    SENSOR_ATTR = "frost_lock"
    _attr_device_class: BinarySensorDeviceClass = BinarySensorDeviceClass.LOCK


@MULTI_MATCH(channel_names="ikea_airpurifier")
class ReplaceFilter(BinarySensor, id_suffix="replace_filter"):
    """ZHA BinarySensor."""

    SENSOR_ATTR = "replace_filter"
    _attr_device_class: BinarySensorDeviceClass = BinarySensorDeviceClass.PROBLEM


@MULTI_MATCH(channel_names="opple_cluster", models={"aqara.feeder.acn001"})
class AqaraPetFeederErrorDetected(BinarySensor, id_suffix="error_detected"):
    """ZHA aqara pet feeder error detected binary sensor."""

    SENSOR_ATTR = "error_detected"
    _attr_device_class: BinarySensorDeviceClass = BinarySensorDeviceClass.PROBLEM
    _attr_name: str = "Error detected"
