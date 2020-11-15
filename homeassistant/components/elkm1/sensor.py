"""Support for control of ElkM1 sensors."""
from elkm1_lib.const import (
    SettingFormat,
    ZoneLogicalStatus,
    ZonePhysicalStatus,
    ZoneType,
)
from elkm1_lib.util import pretty_const, username
import voluptuous as vol

from homeassistant.const import VOLT
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_platform

from . import ElkAttachedEntity, create_elk_entities
from .const import ATTR_VALUE, DOMAIN, ELK_USER_CODE_SERVICE_SCHEMA

SERVICE_SENSOR_COUNTER_REFRESH = "sensor_counter_refresh"
SERVICE_SENSOR_COUNTER_SET = "sensor_counter_set"
SERVICE_SENSOR_ZONE_BYPASS = "sensor_zone_bypass"
SERVICE_SENSOR_ZONE_TRIGGER = "sensor_zone_trigger"
UNDEFINED_TEMPATURE = -40

ELK_SET_COUNTER_SERVICE_SCHEMA = {
    vol.Required(ATTR_VALUE): vol.All(vol.Coerce(int), vol.Range(0, 65535))
}


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Create the Elk-M1 sensor platform."""
    elk_data = hass.data[DOMAIN][config_entry.entry_id]
    entities = []
    elk = elk_data["elk"]
    create_elk_entities(elk_data, elk.counters, "counter", ElkCounter, entities)
    create_elk_entities(elk_data, elk.keypads, "keypad", ElkKeypad, entities)
    create_elk_entities(elk_data, [elk.panel], "panel", ElkPanel, entities)
    create_elk_entities(elk_data, elk.settings, "setting", ElkSetting, entities)
    create_elk_entities(elk_data, elk.zones, "zone", ElkZone, entities)
    async_add_entities(entities, True)

    platform = entity_platform.current_platform.get()

    platform.async_register_entity_service(
        SERVICE_SENSOR_COUNTER_REFRESH,
        {},
        "async_counter_refresh",
    )
    platform.async_register_entity_service(
        SERVICE_SENSOR_COUNTER_SET,
        ELK_SET_COUNTER_SERVICE_SCHEMA,
        "async_counter_set",
    )
    platform.async_register_entity_service(
        SERVICE_SENSOR_ZONE_BYPASS,
        ELK_USER_CODE_SERVICE_SCHEMA,
        "async_zone_bypass",
    )
    platform.async_register_entity_service(
        SERVICE_SENSOR_ZONE_TRIGGER,
        {},
        "async_zone_trigger",
    )


def temperature_to_state(temperature, undefined_temperature):
    """Convert temperature to a state."""
    return temperature if temperature > undefined_temperature else None


class ElkSensor(ElkAttachedEntity):
    """Base representation of Elk-M1 sensor."""

    def __init__(self, element, elk, elk_data):
        """Initialize the base of all Elk sensors."""
        super().__init__(element, elk, elk_data)
        self._state = None

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    async def async_counter_refresh(self):
        """Refresh the value of a counter from the panel."""
        if not isinstance(self, ElkCounter):
            raise HomeAssistantError("supported only on ElkM1 Counter sensors")
        self._element.get()

    async def async_counter_set(self, value=None):
        """Set the value of a counter on the panel."""
        if not isinstance(self, ElkCounter):
            raise HomeAssistantError("supported only on ElkM1 Counter sensors")
        self._element.set(value)

    async def async_zone_bypass(self, code=None):
        """Bypass zone."""
        if not isinstance(self, ElkZone):
            raise HomeAssistantError("supported only on ElkM1 Zone sensors")
        self._element.bypass(code)

    async def async_zone_trigger(self):
        """Trigger zone."""
        if not isinstance(self, ElkZone):
            raise HomeAssistantError("supported only on ElkM1 Zone sensors")
        self._element.trigger()


class ElkCounter(ElkSensor):
    """Representation of an Elk-M1 Counter."""

    @property
    def icon(self):
        """Icon to use in the frontend."""
        return "mdi:numeric"

    def _element_changed(self, element, changeset):
        self._state = self._element.value


class ElkKeypad(ElkSensor):
    """Representation of an Elk-M1 Keypad."""

    @property
    def temperature_unit(self):
        """Return the temperature unit."""
        return self._temperature_unit

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return self._temperature_unit

    @property
    def icon(self):
        """Icon to use in the frontend."""
        return "mdi:thermometer-lines"

    @property
    def device_state_attributes(self):
        """Attributes of the sensor."""
        attrs = self.initial_attrs()
        attrs["area"] = self._element.area + 1
        attrs["temperature"] = self._state
        attrs["last_user_time"] = self._element.last_user_time.isoformat()
        attrs["last_user"] = self._element.last_user + 1
        attrs["code"] = self._element.code
        attrs["last_user_name"] = username(self._elk, self._element.last_user)
        attrs["last_keypress"] = self._element.last_keypress
        return attrs

    def _element_changed(self, element, changeset):
        self._state = temperature_to_state(
            self._element.temperature, UNDEFINED_TEMPATURE
        )


class ElkPanel(ElkSensor):
    """Representation of an Elk-M1 Panel."""

    @property
    def icon(self):
        """Icon to use in the frontend."""
        return "mdi:home"

    @property
    def device_state_attributes(self):
        """Attributes of the sensor."""
        attrs = self.initial_attrs()
        attrs["system_trouble_status"] = self._element.system_trouble_status
        return attrs

    def _element_changed(self, element, changeset):
        if self._elk.is_connected():
            self._state = (
                "Paused" if self._element.remote_programming_status else "Connected"
            )
        else:
            self._state = "Disconnected"


class ElkSetting(ElkSensor):
    """Representation of an Elk-M1 Setting."""

    @property
    def icon(self):
        """Icon to use in the frontend."""
        return "mdi:numeric"

    def _element_changed(self, element, changeset):
        self._state = self._element.value

    @property
    def device_state_attributes(self):
        """Attributes of the sensor."""
        attrs = self.initial_attrs()
        attrs["value_format"] = SettingFormat(self._element.value_format).name.lower()
        return attrs


class ElkZone(ElkSensor):
    """Representation of an Elk-M1 Zone."""

    @property
    def icon(self):
        """Icon to use in the frontend."""
        zone_icons = {
            ZoneType.FIRE_ALARM.value: "fire",
            ZoneType.FIRE_VERIFIED.value: "fire",
            ZoneType.FIRE_SUPERVISORY.value: "fire",
            ZoneType.KEYFOB.value: "key",
            ZoneType.NON_ALARM.value: "alarm-off",
            ZoneType.MEDICAL_ALARM.value: "medical-bag",
            ZoneType.POLICE_ALARM.value: "alarm-light",
            ZoneType.POLICE_NO_INDICATION.value: "alarm-light",
            ZoneType.KEY_MOMENTARY_ARM_DISARM.value: "power",
            ZoneType.KEY_MOMENTARY_ARM_AWAY.value: "power",
            ZoneType.KEY_MOMENTARY_ARM_STAY.value: "power",
            ZoneType.KEY_MOMENTARY_DISARM.value: "power",
            ZoneType.KEY_ON_OFF.value: "toggle-switch",
            ZoneType.MUTE_AUDIBLES.value: "volume-mute",
            ZoneType.POWER_SUPERVISORY.value: "power-plug",
            ZoneType.TEMPERATURE.value: "thermometer-lines",
            ZoneType.ANALOG_ZONE.value: "speedometer",
            ZoneType.PHONE_KEY.value: "phone-classic",
            ZoneType.INTERCOM_KEY.value: "deskphone",
        }
        return f"mdi:{zone_icons.get(self._element.definition, 'alarm-bell')}"

    @property
    def device_state_attributes(self):
        """Attributes of the sensor."""
        attrs = self.initial_attrs()
        attrs["physical_status"] = ZonePhysicalStatus(
            self._element.physical_status
        ).name.lower()
        attrs["logical_status"] = ZoneLogicalStatus(
            self._element.logical_status
        ).name.lower()
        attrs["definition"] = ZoneType(self._element.definition).name.lower()
        attrs["area"] = self._element.area + 1
        attrs["triggered_alarm"] = self._element.triggered_alarm
        return attrs

    @property
    def temperature_unit(self):
        """Return the temperature unit."""
        if self._element.definition == ZoneType.TEMPERATURE.value:
            return self._temperature_unit
        return None

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        if self._element.definition == ZoneType.TEMPERATURE.value:
            return self._temperature_unit
        if self._element.definition == ZoneType.ANALOG_ZONE.value:
            return VOLT
        return None

    def _element_changed(self, element, changeset):
        if self._element.definition == ZoneType.TEMPERATURE.value:
            self._state = temperature_to_state(
                self._element.temperature, UNDEFINED_TEMPATURE
            )
        elif self._element.definition == ZoneType.ANALOG_ZONE.value:
            self._state = self._element.voltage
        else:
            self._state = pretty_const(
                ZoneLogicalStatus(self._element.logical_status).name
            )
