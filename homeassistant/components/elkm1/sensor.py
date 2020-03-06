"""Support for control of ElkM1 sensors."""
from elkm1_lib.const import (
    SettingFormat,
    ZoneLogicalStatus,
    ZonePhysicalStatus,
    ZoneType,
)
from elkm1_lib.util import pretty_const, username

from . import DOMAIN as ELK_DOMAIN, ElkEntity, create_elk_entities


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Create the Elk-M1 sensor platform."""
    if discovery_info is None:
        return

    elk_datas = hass.data[ELK_DOMAIN]
    entities = []
    for elk_data in elk_datas.values():
        elk = elk_data["elk"]
        entities = create_elk_entities(
            elk_data, elk.counters, "counter", ElkCounter, entities
        )
        entities = create_elk_entities(
            elk_data, elk.keypads, "keypad", ElkKeypad, entities
        )
        entities = create_elk_entities(
            elk_data, [elk.panel], "panel", ElkPanel, entities
        )
        entities = create_elk_entities(
            elk_data, elk.settings, "setting", ElkSetting, entities
        )
        entities = create_elk_entities(elk_data, elk.zones, "zone", ElkZone, entities)
    async_add_entities(entities, True)


def temperature_to_state(temperature, undefined_temperature):
    """Convert temperature to a state."""
    return temperature if temperature > undefined_temperature else None


class ElkSensor(ElkEntity):
    """Base representation of Elk-M1 sensor."""

    def __init__(self, element, elk, elk_data):
        """Initialize the base of all Elk sensors."""
        super().__init__(element, elk, elk_data)
        self._state = None

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state


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
        attrs["temperature"] = self._element.temperature
        attrs["last_user_time"] = self._element.last_user_time.isoformat()
        attrs["last_user"] = self._element.last_user + 1
        attrs["code"] = self._element.code
        attrs["last_user_name"] = username(self._elk, self._element.last_user)
        attrs["last_keypress"] = self._element.last_keypress
        return attrs

    def _element_changed(self, element, changeset):
        self._state = temperature_to_state(self._element.temperature, -40)

    async def async_added_to_hass(self):
        """Register callback for ElkM1 changes and update entity state."""
        await super().async_added_to_hass()
        elk_datas = self.hass.data[ELK_DOMAIN]
        for elk_data in elk_datas.values():
            elk_data["keypads"][self._element.index] = self.entity_id


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
        attrs["bypassed"] = self._element.bypassed
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
            return "V"
        return None

    def _element_changed(self, element, changeset):
        if self._element.definition == ZoneType.TEMPERATURE.value:
            self._state = temperature_to_state(self._element.temperature, -60)
        elif self._element.definition == ZoneType.ANALOG_ZONE.value:
            self._state = self._element.voltage
        else:
            self._state = pretty_const(
                ZoneLogicalStatus(self._element.logical_status).name
            )
