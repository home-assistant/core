"""Support for August sensors."""
import logging

from yalexs.activity import ActivityType

from homeassistant.components.sensor import DEVICE_CLASS_BATTERY, SensorEntity
from homeassistant.const import ATTR_ENTITY_PICTURE, PERCENTAGE, STATE_UNAVAILABLE
from homeassistant.core import callback
from homeassistant.helpers.entity_registry import async_get_registry
from homeassistant.helpers.restore_state import RestoreEntity

from .const import (
    ATTR_OPERATION_AUTORELOCK,
    ATTR_OPERATION_KEYPAD,
    ATTR_OPERATION_METHOD,
    ATTR_OPERATION_REMOTE,
    DATA_AUGUST,
    DOMAIN,
    OPERATION_METHOD_AUTORELOCK,
    OPERATION_METHOD_KEYPAD,
    OPERATION_METHOD_MOBILE_DEVICE,
    OPERATION_METHOD_REMOTE,
)
from .entity import AugustEntityMixin

_LOGGER = logging.getLogger(__name__)


def _retrieve_device_battery_state(detail):
    """Get the latest state of the sensor."""
    return detail.battery_level


def _retrieve_linked_keypad_battery_state(detail):
    """Get the latest state of the sensor."""
    return detail.battery_percentage


SENSOR_TYPES_BATTERY = {
    "device_battery": {"state_provider": _retrieve_device_battery_state},
    "linked_keypad_battery": {"state_provider": _retrieve_linked_keypad_battery_state},
}


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the August sensors."""
    data = hass.data[DOMAIN][config_entry.entry_id][DATA_AUGUST]
    devices = []
    migrate_unique_id_devices = []
    operation_sensors = []
    batteries = {
        "device_battery": [],
        "linked_keypad_battery": [],
    }
    for device in data.doorbells:
        batteries["device_battery"].append(device)
    for device in data.locks:
        batteries["device_battery"].append(device)
        batteries["linked_keypad_battery"].append(device)
        operation_sensors.append(device)

    for device in batteries["device_battery"]:
        state_provider = SENSOR_TYPES_BATTERY["device_battery"]["state_provider"]
        detail = data.get_device_detail(device.device_id)
        if detail is None or state_provider(detail) is None:
            _LOGGER.debug(
                "Not adding battery sensor for %s because it is not present",
                device.device_name,
            )
            continue
        _LOGGER.debug(
            "Adding battery sensor for %s",
            device.device_name,
        )
        devices.append(AugustBatterySensor(data, "device_battery", device, device))

    for device in batteries["linked_keypad_battery"]:
        detail = data.get_device_detail(device.device_id)

        if detail.keypad is None:
            _LOGGER.debug(
                "Not adding keypad battery sensor for %s because it is not present",
                device.device_name,
            )
            continue
        _LOGGER.debug(
            "Adding keypad battery sensor for %s",
            device.device_name,
        )
        keypad_battery_sensor = AugustBatterySensor(
            data, "linked_keypad_battery", detail.keypad, device
        )
        devices.append(keypad_battery_sensor)
        migrate_unique_id_devices.append(keypad_battery_sensor)

    for device in operation_sensors:
        devices.append(AugustOperatorSensor(data, device))

    await _async_migrate_old_unique_ids(hass, migrate_unique_id_devices)

    async_add_entities(devices, True)


async def _async_migrate_old_unique_ids(hass, devices):
    """Keypads now have their own serial number."""
    registry = await async_get_registry(hass)
    for device in devices:
        old_entity_id = registry.async_get_entity_id(
            "sensor", DOMAIN, device.old_unique_id
        )
        if old_entity_id is not None:
            _LOGGER.debug(
                "Migrating unique_id from [%s] to [%s]",
                device.old_unique_id,
                device.unique_id,
            )
            registry.async_update_entity(old_entity_id, new_unique_id=device.unique_id)


class AugustOperatorSensor(AugustEntityMixin, RestoreEntity, SensorEntity):
    """Representation of an August lock operation sensor."""

    def __init__(self, data, device):
        """Initialize the sensor."""
        super().__init__(data, device)
        self._data = data
        self._device = device
        self._state = None
        self._operated_remote = None
        self._operated_keypad = None
        self._operated_autorelock = None
        self._operated_time = None
        self._available = False
        self._entity_picture = None
        self._update_from_data()

    @property
    def available(self):
        """Return the availability of this sensor."""
        return self._available

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"{self._device.device_name} Operator"

    @callback
    def _update_from_data(self):
        """Get the latest state of the sensor and update activity."""
        lock_activity = self._data.activity_stream.get_latest_device_activity(
            self._device_id, {ActivityType.LOCK_OPERATION}
        )

        self._available = True
        if lock_activity is not None:
            self._state = lock_activity.operated_by
            self._operated_remote = lock_activity.operated_remote
            self._operated_keypad = lock_activity.operated_keypad
            self._operated_autorelock = lock_activity.operated_autorelock
            self._entity_picture = lock_activity.operator_thumbnail_url

    @property
    def extra_state_attributes(self):
        """Return the device specific state attributes."""
        attributes = {}

        if self._operated_remote is not None:
            attributes[ATTR_OPERATION_REMOTE] = self._operated_remote
        if self._operated_keypad is not None:
            attributes[ATTR_OPERATION_KEYPAD] = self._operated_keypad
        if self._operated_autorelock is not None:
            attributes[ATTR_OPERATION_AUTORELOCK] = self._operated_autorelock

        if self._operated_remote:
            attributes[ATTR_OPERATION_METHOD] = OPERATION_METHOD_REMOTE
        elif self._operated_keypad:
            attributes[ATTR_OPERATION_METHOD] = OPERATION_METHOD_KEYPAD
        elif self._operated_autorelock:
            attributes[ATTR_OPERATION_METHOD] = OPERATION_METHOD_AUTORELOCK
        else:
            attributes[ATTR_OPERATION_METHOD] = OPERATION_METHOD_MOBILE_DEVICE

        return attributes

    async def async_added_to_hass(self):
        """Restore ATTR_CHANGED_BY on startup since it is likely no longer in the activity log."""
        await super().async_added_to_hass()

        last_state = await self.async_get_last_state()
        if not last_state or last_state.state == STATE_UNAVAILABLE:
            return

        self._state = last_state.state
        if ATTR_ENTITY_PICTURE in last_state.attributes:
            self._entity_picture = last_state.attributes[ATTR_ENTITY_PICTURE]
        if ATTR_OPERATION_REMOTE in last_state.attributes:
            self._operated_remote = last_state.attributes[ATTR_OPERATION_REMOTE]
        if ATTR_OPERATION_KEYPAD in last_state.attributes:
            self._operated_keypad = last_state.attributes[ATTR_OPERATION_KEYPAD]
        if ATTR_OPERATION_AUTORELOCK in last_state.attributes:
            self._operated_autorelock = last_state.attributes[ATTR_OPERATION_AUTORELOCK]

    @property
    def entity_picture(self):
        """Return the entity picture to use in the frontend, if any."""
        return self._entity_picture

    @property
    def unique_id(self) -> str:
        """Get the unique id of the device sensor."""
        return f"{self._device_id}_lock_operator"


class AugustBatterySensor(AugustEntityMixin, SensorEntity):
    """Representation of an August sensor."""

    def __init__(self, data, sensor_type, device, old_device):
        """Initialize the sensor."""
        super().__init__(data, device)
        self._data = data
        self._sensor_type = sensor_type
        self._device = device
        self._old_device = old_device
        self._state = None
        self._available = False
        self._update_from_data()

    @property
    def available(self):
        """Return the availability of this sensor."""
        return self._available

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return PERCENTAGE

    @property
    def device_class(self):
        """Return the class of this device, from component DEVICE_CLASSES."""
        return DEVICE_CLASS_BATTERY

    @property
    def name(self):
        """Return the name of the sensor."""
        device_name = self._device.device_name
        return f"{device_name} Battery"

    @callback
    def _update_from_data(self):
        """Get the latest state of the sensor."""
        state_provider = SENSOR_TYPES_BATTERY[self._sensor_type]["state_provider"]
        self._state = state_provider(self._detail)
        self._available = self._state is not None

    @property
    def unique_id(self) -> str:
        """Get the unique id of the device sensor."""
        return f"{self._device_id}_{self._sensor_type}"

    @property
    def old_unique_id(self) -> str:
        """Get the old unique id of the device sensor."""
        return f"{self._old_device.device_id}_{self._sensor_type}"
