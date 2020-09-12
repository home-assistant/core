"""Support for Xiaomi aqara binary sensors."""
import logging

from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_OPENING,
    BinarySensorEntity,
)
from homeassistant.core import callback
from homeassistant.helpers.event import async_call_later

from . import XiaomiDevice
from .const import DOMAIN, GATEWAYS_KEY

_LOGGER = logging.getLogger(__name__)

NO_CLOSE = "no_close"
ATTR_OPEN_SINCE = "Open since"

MOTION = "motion"
NO_MOTION = "no_motion"
ATTR_LAST_ACTION = "last_action"
ATTR_NO_MOTION_SINCE = "No motion since"

DENSITY = "density"
ATTR_DENSITY = "Density"


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Perform the setup for Xiaomi devices."""
    entities = []
    gateway = hass.data[DOMAIN][GATEWAYS_KEY][config_entry.entry_id]
    for entity in gateway.devices["binary_sensor"]:
        model = entity["model"]
        if model in ["motion", "sensor_motion", "sensor_motion.aq2"]:
            entities.append(XiaomiMotionSensor(entity, hass, gateway, config_entry))
        elif model in ["magnet", "sensor_magnet", "sensor_magnet.aq2"]:
            entities.append(XiaomiDoorSensor(entity, gateway, config_entry))
        elif model == "sensor_wleak.aq1":
            entities.append(XiaomiWaterLeakSensor(entity, gateway, config_entry))
        elif model in ["smoke", "sensor_smoke"]:
            entities.append(XiaomiSmokeSensor(entity, gateway, config_entry))
        elif model in ["natgas", "sensor_natgas"]:
            entities.append(XiaomiNatgasSensor(entity, gateway, config_entry))
        elif model in [
            "switch",
            "sensor_switch",
            "sensor_switch.aq2",
            "sensor_switch.aq3",
            "remote.b1acn01",
        ]:
            if "proto" not in entity or int(entity["proto"][0:1]) == 1:
                data_key = "status"
            else:
                data_key = "button_0"
            entities.append(
                XiaomiButton(entity, "Switch", data_key, hass, gateway, config_entry)
            )
        elif model in [
            "86sw1",
            "sensor_86sw1",
            "sensor_86sw1.aq1",
            "remote.b186acn01",
            "remote.b186acn02",
        ]:
            if "proto" not in entity or int(entity["proto"][0:1]) == 1:
                data_key = "channel_0"
            else:
                data_key = "button_0"
            entities.append(
                XiaomiButton(
                    entity, "Wall Switch", data_key, hass, gateway, config_entry
                )
            )
        elif model in [
            "86sw2",
            "sensor_86sw2",
            "sensor_86sw2.aq1",
            "remote.b286acn01",
            "remote.b286acn02",
        ]:
            if "proto" not in entity or int(entity["proto"][0:1]) == 1:
                data_key_left = "channel_0"
                data_key_right = "channel_1"
            else:
                data_key_left = "button_0"
                data_key_right = "button_1"
            entities.append(
                XiaomiButton(
                    entity,
                    "Wall Switch (Left)",
                    data_key_left,
                    hass,
                    gateway,
                    config_entry,
                )
            )
            entities.append(
                XiaomiButton(
                    entity,
                    "Wall Switch (Right)",
                    data_key_right,
                    hass,
                    gateway,
                    config_entry,
                )
            )
            entities.append(
                XiaomiButton(
                    entity,
                    "Wall Switch (Both)",
                    "dual_channel",
                    hass,
                    gateway,
                    config_entry,
                )
            )
        elif model in ["cube", "sensor_cube", "sensor_cube.aqgl01"]:
            entities.append(XiaomiCube(entity, hass, gateway, config_entry))
        elif model in ["vibration", "vibration.aq1"]:
            entities.append(
                XiaomiVibration(entity, "Vibration", "status", gateway, config_entry)
            )
        else:
            _LOGGER.warning("Unmapped Device Model %s", model)

    async_add_entities(entities)


class XiaomiBinarySensor(XiaomiDevice, BinarySensorEntity):
    """Representation of a base XiaomiBinarySensor."""

    def __init__(self, device, name, xiaomi_hub, data_key, device_class, config_entry):
        """Initialize the XiaomiSmokeSensor."""
        self._data_key = data_key
        self._device_class = device_class
        self._should_poll = False
        self._density = 0
        super().__init__(device, name, xiaomi_hub, config_entry)

    @property
    def should_poll(self):
        """Return True if entity has to be polled for state."""
        return self._should_poll

    @property
    def is_on(self):
        """Return true if sensor is on."""
        return self._state

    @property
    def device_class(self):
        """Return the class of binary sensor."""
        return self._device_class

    def update(self):
        """Update the sensor state."""
        _LOGGER.debug("Updating xiaomi sensor (%s) by polling", self._sid)
        self._get_from_hub(self._sid)


class XiaomiNatgasSensor(XiaomiBinarySensor):
    """Representation of a XiaomiNatgasSensor."""

    def __init__(self, device, xiaomi_hub, config_entry):
        """Initialize the XiaomiSmokeSensor."""
        self._density = None
        super().__init__(
            device, "Natgas Sensor", xiaomi_hub, "alarm", "gas", config_entry
        )

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        attrs = {ATTR_DENSITY: self._density}
        attrs.update(super().device_state_attributes)
        return attrs

    def parse_data(self, data, raw_data):
        """Parse data sent by gateway."""
        if DENSITY in data:
            self._density = int(data.get(DENSITY))

        value = data.get(self._data_key)
        if value is None:
            return False

        if value in ("1", "2"):
            if self._state:
                return False
            self._state = True
            return True
        if value == "0":
            if self._state:
                self._state = False
                return True
            return False


class XiaomiMotionSensor(XiaomiBinarySensor):
    """Representation of a XiaomiMotionSensor."""

    def __init__(self, device, hass, xiaomi_hub, config_entry):
        """Initialize the XiaomiMotionSensor."""
        self._hass = hass
        self._no_motion_since = 0
        self._unsub_set_no_motion = None
        if "proto" not in device or int(device["proto"][0:1]) == 1:
            data_key = "status"
        else:
            data_key = "motion_status"
        super().__init__(
            device, "Motion Sensor", xiaomi_hub, data_key, "motion", config_entry
        )

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        attrs = {ATTR_NO_MOTION_SINCE: self._no_motion_since}
        attrs.update(super().device_state_attributes)
        return attrs

    @callback
    def _async_set_no_motion(self, now):
        """Set state to False."""
        self._unsub_set_no_motion = None
        self._state = False
        self.async_write_ha_state()

    def parse_data(self, data, raw_data):
        """Parse data sent by gateway.

        Polling (proto v1, firmware version 1.4.1_159.0143)

        >> { "cmd":"read","sid":"158..."}
        << {'model': 'motion', 'sid': '158...', 'short_id': 26331,
            'cmd': 'read_ack', 'data': '{"voltage":3005}'}

        Multicast messages (proto v1, firmware version 1.4.1_159.0143)

        << {'model': 'motion', 'sid': '158...', 'short_id': 26331,
            'cmd': 'report', 'data': '{"status":"motion"}'}
        << {'model': 'motion', 'sid': '158...', 'short_id': 26331,
            'cmd': 'report', 'data': '{"no_motion":"120"}'}
        << {'model': 'motion', 'sid': '158...', 'short_id': 26331,
            'cmd': 'report', 'data': '{"no_motion":"180"}'}
        << {'model': 'motion', 'sid': '158...', 'short_id': 26331,
           'cmd': 'report', 'data': '{"no_motion":"300"}'}
        << {'model': 'motion', 'sid': '158...', 'short_id': 26331,
            'cmd': 'heartbeat', 'data': '{"voltage":3005}'}

        """
        if raw_data["cmd"] == "heartbeat":
            _LOGGER.debug(
                "Skipping heartbeat of the motion sensor. "
                "It can introduce an incorrect state because of a firmware "
                "bug (https://github.com/home-assistant/home-assistant/pull/"
                "11631#issuecomment-357507744)"
            )
            return

        if NO_MOTION in data:
            self._no_motion_since = data[NO_MOTION]
            self._state = False
            return True

        value = data.get(self._data_key)
        if value is None:
            return False

        if value == MOTION:
            if self._data_key == "motion_status":
                if self._unsub_set_no_motion:
                    self._unsub_set_no_motion()
                self._unsub_set_no_motion = async_call_later(
                    self._hass, 120, self._async_set_no_motion
                )

            if self.entity_id is not None:
                self._hass.bus.fire(
                    "xiaomi_aqara.motion", {"entity_id": self.entity_id}
                )

            self._no_motion_since = 0
            if self._state:
                return False
            self._state = True
            return True


class XiaomiDoorSensor(XiaomiBinarySensor):
    """Representation of a XiaomiDoorSensor."""

    def __init__(self, device, xiaomi_hub, config_entry):
        """Initialize the XiaomiDoorSensor."""
        self._open_since = 0
        if "proto" not in device or int(device["proto"][0:1]) == 1:
            data_key = "status"
        else:
            data_key = "window_status"
        super().__init__(
            device,
            "Door Window Sensor",
            xiaomi_hub,
            data_key,
            DEVICE_CLASS_OPENING,
            config_entry,
        )

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        attrs = {ATTR_OPEN_SINCE: self._open_since}
        attrs.update(super().device_state_attributes)
        return attrs

    def parse_data(self, data, raw_data):
        """Parse data sent by gateway."""
        self._should_poll = False
        if NO_CLOSE in data:  # handle push from the hub
            self._open_since = data[NO_CLOSE]
            return True

        value = data.get(self._data_key)
        if value is None:
            return False

        if value == "open":
            self._should_poll = True
            if self._state:
                return False
            self._state = True
            return True
        if value == "close":
            self._open_since = 0
            if self._state:
                self._state = False
                return True
            return False


class XiaomiWaterLeakSensor(XiaomiBinarySensor):
    """Representation of a XiaomiWaterLeakSensor."""

    def __init__(self, device, xiaomi_hub, config_entry):
        """Initialize the XiaomiWaterLeakSensor."""
        if "proto" not in device or int(device["proto"][0:1]) == 1:
            data_key = "status"
        else:
            data_key = "wleak_status"
        super().__init__(
            device,
            "Water Leak Sensor",
            xiaomi_hub,
            data_key,
            "moisture",
            config_entry,
        )

    def parse_data(self, data, raw_data):
        """Parse data sent by gateway."""
        self._should_poll = False

        value = data.get(self._data_key)
        if value is None:
            return False

        if value == "leak":
            self._should_poll = True
            if self._state:
                return False
            self._state = True
            return True
        if value == "no_leak":
            if self._state:
                self._state = False
                return True
            return False


class XiaomiSmokeSensor(XiaomiBinarySensor):
    """Representation of a XiaomiSmokeSensor."""

    def __init__(self, device, xiaomi_hub, config_entry):
        """Initialize the XiaomiSmokeSensor."""
        self._density = 0
        super().__init__(
            device, "Smoke Sensor", xiaomi_hub, "alarm", "smoke", config_entry
        )

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        attrs = {ATTR_DENSITY: self._density}
        attrs.update(super().device_state_attributes)
        return attrs

    def parse_data(self, data, raw_data):
        """Parse data sent by gateway."""
        if DENSITY in data:
            self._density = int(data.get(DENSITY))
        value = data.get(self._data_key)
        if value is None:
            return False

        if value in ("1", "2"):
            if self._state:
                return False
            self._state = True
            return True
        if value == "0":
            if self._state:
                self._state = False
                return True
            return False


class XiaomiVibration(XiaomiBinarySensor):
    """Representation of a Xiaomi Vibration Sensor."""

    def __init__(self, device, name, data_key, xiaomi_hub, config_entry):
        """Initialize the XiaomiVibration."""
        self._last_action = None
        super().__init__(device, name, xiaomi_hub, data_key, None, config_entry)

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        attrs = {ATTR_LAST_ACTION: self._last_action}
        attrs.update(super().device_state_attributes)
        return attrs

    def parse_data(self, data, raw_data):
        """Parse data sent by gateway."""
        value = data.get(self._data_key)
        if value is None:
            return False

        if value not in ("vibrate", "tilt", "free_fall", "actively"):
            _LOGGER.warning("Unsupported movement_type detected: %s", value)
            return False

        self.hass.bus.fire(
            "xiaomi_aqara.movement",
            {"entity_id": self.entity_id, "movement_type": value},
        )
        self._last_action = value

        return True


class XiaomiButton(XiaomiBinarySensor):
    """Representation of a Xiaomi Button."""

    def __init__(self, device, name, data_key, hass, xiaomi_hub, config_entry):
        """Initialize the XiaomiButton."""
        self._hass = hass
        self._last_action = None
        super().__init__(device, name, xiaomi_hub, data_key, None, config_entry)

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        attrs = {ATTR_LAST_ACTION: self._last_action}
        attrs.update(super().device_state_attributes)
        return attrs

    def parse_data(self, data, raw_data):
        """Parse data sent by gateway."""
        value = data.get(self._data_key)
        if value is None:
            return False

        if value == "long_click_press":
            self._state = True
            click_type = "long_click_press"
        elif value == "long_click_release":
            self._state = False
            click_type = "hold"
        elif value == "click":
            click_type = "single"
        elif value == "double_click":
            click_type = "double"
        elif value == "both_click":
            click_type = "both"
        elif value == "double_both_click":
            click_type = "double_both"
        elif value == "shake":
            click_type = "shake"
        elif value == "long_click":
            click_type = "long"
        elif value == "long_both_click":
            click_type = "long_both"
        else:
            _LOGGER.warning("Unsupported click_type detected: %s", value)
            return False

        self._hass.bus.fire(
            "xiaomi_aqara.click",
            {"entity_id": self.entity_id, "click_type": click_type},
        )
        self._last_action = click_type

        return True


class XiaomiCube(XiaomiBinarySensor):
    """Representation of a Xiaomi Cube."""

    def __init__(self, device, hass, xiaomi_hub, config_entry):
        """Initialize the Xiaomi Cube."""
        self._hass = hass
        self._last_action = None
        self._state = False
        if "proto" not in device or int(device["proto"][0:1]) == 1:
            data_key = "status"
        else:
            data_key = "cube_status"
        super().__init__(device, "Cube", xiaomi_hub, data_key, None, config_entry)

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        attrs = {ATTR_LAST_ACTION: self._last_action}
        attrs.update(super().device_state_attributes)
        return attrs

    def parse_data(self, data, raw_data):
        """Parse data sent by gateway."""
        if self._data_key in data:
            self._hass.bus.fire(
                "xiaomi_aqara.cube_action",
                {"entity_id": self.entity_id, "action_type": data[self._data_key]},
            )
            self._last_action = data[self._data_key]

        if "rotate" in data:
            action_value = float(
                data["rotate"]
                if isinstance(data["rotate"], int)
                else data["rotate"].replace(",", ".")
            )
            self._hass.bus.fire(
                "xiaomi_aqara.cube_action",
                {
                    "entity_id": self.entity_id,
                    "action_type": "rotate",
                    "action_value": action_value,
                },
            )
            self._last_action = "rotate"

        if "rotate_degree" in data:
            action_value = float(
                data["rotate_degree"]
                if isinstance(data["rotate_degree"], int)
                else data["rotate_degree"].replace(",", ".")
            )
            self._hass.bus.fire(
                "xiaomi_aqara.cube_action",
                {
                    "entity_id": self.entity_id,
                    "action_type": "rotate",
                    "action_value": action_value,
                },
            )
            self._last_action = "rotate"

        return True
