"""Support for control of ElkM1 sensors."""

from __future__ import annotations

from typing import Any

from elkm1_lib.const import SettingFormat, ZoneType
from elkm1_lib.counters import Counter
from elkm1_lib.elements import Element
from elkm1_lib.keypads import Keypad
from elkm1_lib.panel import Panel
from elkm1_lib.settings import Setting
from elkm1_lib.util import pretty_const
from elkm1_lib.zones import Zone
import voluptuous as vol

from homeassistant.components.sensor import SensorEntity
from homeassistant.const import EntityCategory, UnitOfElectricPotential
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_platform
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import VolDictType

from . import ElkM1ConfigEntry
from .const import ATTR_VALUE, ELK_USER_CODE_SERVICE_SCHEMA
from .entity import ElkAttachedEntity, ElkEntity, create_elk_entities

SERVICE_SENSOR_COUNTER_REFRESH = "sensor_counter_refresh"
SERVICE_SENSOR_COUNTER_SET = "sensor_counter_set"
SERVICE_SENSOR_ZONE_BYPASS = "sensor_zone_bypass"
SERVICE_SENSOR_ZONE_TRIGGER = "sensor_zone_trigger"
UNDEFINED_TEMPERATURE = -40

ELK_SET_COUNTER_SERVICE_SCHEMA: VolDictType = {
    vol.Required(ATTR_VALUE): vol.All(vol.Coerce(int), vol.Range(0, 65535))
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ElkM1ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Create the Elk-M1 sensor platform."""
    elk_data = config_entry.runtime_data
    elk = elk_data.elk
    entities: list[ElkEntity] = []
    create_elk_entities(elk_data, elk.counters, "counter", ElkCounter, entities)
    create_elk_entities(elk_data, elk.keypads, "keypad", ElkKeypad, entities)
    create_elk_entities(elk_data, [elk.panel], "panel", ElkPanel, entities)
    create_elk_entities(elk_data, elk.settings, "setting", ElkSetting, entities)
    create_elk_entities(elk_data, elk.zones, "zone", ElkZone, entities)
    async_add_entities(entities)

    platform = entity_platform.async_get_current_platform()

    platform.async_register_entity_service(
        SERVICE_SENSOR_COUNTER_REFRESH,
        None,
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
        None,
        "async_zone_trigger",
    )


def temperature_to_state(temperature: int, undefined_temperature: int) -> str | None:
    """Convert temperature to a state."""
    return f"{temperature}" if temperature > undefined_temperature else None


class ElkSensor(ElkAttachedEntity, SensorEntity):
    """Base representation of Elk-M1 sensor."""

    _attr_native_value: str | None = None

    async def async_counter_refresh(self) -> None:
        """Refresh the value of a counter from the panel."""
        if not isinstance(self, ElkCounter):
            raise HomeAssistantError("supported only on ElkM1 Counter sensors")
        self._element.get()

    async def async_counter_set(self, value: int | None = None) -> None:
        """Set the value of a counter on the panel."""
        if not isinstance(self, ElkCounter):
            raise HomeAssistantError("supported only on ElkM1 Counter sensors")
        if value is not None:
            self._element.set(value)

    async def async_zone_bypass(self, code: int | None = None) -> None:
        """Bypass zone."""
        if not isinstance(self, ElkZone):
            raise HomeAssistantError("supported only on ElkM1 Zone sensors")
        if code is not None:
            self._element.bypass(code)

    async def async_zone_trigger(self) -> None:
        """Trigger zone."""
        if not isinstance(self, ElkZone):
            raise HomeAssistantError("supported only on ElkM1 Zone sensors")
        self._element.trigger()


class ElkCounter(ElkSensor):
    """Representation of an Elk-M1 Counter."""

    _attr_icon = "mdi:numeric"
    _element: Counter

    def _element_changed(self, _: Element, changeset: Any) -> None:
        self._attr_native_value = self._element.value


class ElkKeypad(ElkSensor):
    """Representation of an Elk-M1 Keypad."""

    _attr_icon = "mdi:thermometer-lines"
    _element: Keypad

    @property
    def temperature_unit(self) -> str:
        """Return the temperature unit."""
        return self._temperature_unit

    @property
    def native_unit_of_measurement(self) -> str:
        """Return the unit of measurement."""
        return self._temperature_unit

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Attributes of the sensor."""
        attrs: dict[str, Any] = self.initial_attrs()
        attrs["area"] = self._element.area + 1
        attrs["temperature"] = self._attr_native_value
        attrs["last_user_time"] = self._element.last_user_time.isoformat()
        attrs["last_user"] = self._element.last_user + 1
        attrs["code"] = self._element.code
        attrs["last_user_name"] = self._elk.users.username(self._element.last_user)
        attrs["last_keypress"] = self._element.last_keypress
        return attrs

    def _element_changed(self, _: Element, changeset: Any) -> None:
        self._attr_native_value = temperature_to_state(
            self._element.temperature, UNDEFINED_TEMPERATURE
        )


class ElkPanel(ElkSensor):
    """Representation of an Elk-M1 Panel."""

    _attr_translation_key = "panel"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _element: Panel

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Attributes of the sensor."""
        attrs = self.initial_attrs()
        attrs["system_trouble_status"] = self._element.system_trouble_status
        return attrs

    def _element_changed(self, _: Element, changeset: Any) -> None:
        if self._elk.is_connected():
            self._attr_native_value = (
                "Paused" if self._element.remote_programming_status else "Connected"
            )
        else:
            self._attr_native_value = "Disconnected"


class ElkSetting(ElkSensor):
    """Representation of an Elk-M1 Setting."""

    _attr_translation_key = "setting"
    _element: Setting

    def _element_changed(self, _: Element, changeset: Any) -> None:
        self._attr_native_value = self._element.value

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Attributes of the sensor."""
        attrs: dict[str, Any] = self.initial_attrs()
        attrs["value_format"] = SettingFormat(self._element.value_format).name.lower()
        return attrs


class ElkZone(ElkSensor):
    """Representation of an Elk-M1 Zone."""

    _element: Zone

    @property
    def icon(self) -> str:
        """Icon to use in the frontend."""
        zone_icons = {
            ZoneType.FIRE_ALARM: "fire",
            ZoneType.FIRE_VERIFIED: "fire",
            ZoneType.FIRE_SUPERVISORY: "fire",
            ZoneType.KEYFOB: "key",
            ZoneType.NON_ALARM: "alarm-off",
            ZoneType.MEDICAL_ALARM: "medical-bag",
            ZoneType.POLICE_ALARM: "alarm-light",
            ZoneType.POLICE_NO_INDICATION: "alarm-light",
            ZoneType.KEY_MOMENTARY_ARM_DISARM: "power",
            ZoneType.KEY_MOMENTARY_ARM_AWAY: "power",
            ZoneType.KEY_MOMENTARY_ARM_STAY: "power",
            ZoneType.KEY_MOMENTARY_DISARM: "power",
            ZoneType.KEY_ON_OFF: "toggle-switch",
            ZoneType.MUTE_AUDIBLES: "volume-mute",
            ZoneType.POWER_SUPERVISORY: "power-plug",
            ZoneType.TEMPERATURE: "thermometer-lines",
            ZoneType.ANALOG_ZONE: "speedometer",
            ZoneType.PHONE_KEY: "phone-classic",
            ZoneType.INTERCOM_KEY: "deskphone",
        }
        return f"mdi:{zone_icons.get(self._element.definition, 'alarm-bell')}"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Attributes of the sensor."""
        attrs: dict[str, Any] = self.initial_attrs()
        attrs["physical_status"] = self._element.physical_status.name.lower()
        attrs["logical_status"] = self._element.logical_status.name.lower()
        attrs["definition"] = self._element.definition.name.lower()
        attrs["area"] = self._element.area + 1
        attrs["triggered_alarm"] = self._element.triggered_alarm
        return attrs

    @property
    def temperature_unit(self) -> str | None:
        """Return the temperature unit."""
        if self._element.definition == ZoneType.TEMPERATURE:
            return self._temperature_unit
        return None

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return the unit of measurement."""
        if self._element.definition == ZoneType.TEMPERATURE:
            return self._temperature_unit
        if self._element.definition == ZoneType.ANALOG_ZONE:
            return UnitOfElectricPotential.VOLT
        return None

    def _element_changed(self, _: Element, changeset: Any) -> None:
        if self._element.definition == ZoneType.TEMPERATURE:
            self._attr_native_value = temperature_to_state(
                self._element.temperature, UNDEFINED_TEMPERATURE
            )
        elif self._element.definition == ZoneType.ANALOG_ZONE:
            self._attr_native_value = f"{self._element.voltage}"
        else:
            self._attr_native_value = pretty_const(self._element.logical_status.name)
