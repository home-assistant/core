"""Support for the Torque OBD application."""
from __future__ import annotations

import re

import voluptuous as vol

from homeassistant.components.http import HomeAssistantView
from homeassistant.components.sensor import PLATFORM_SCHEMA, SensorEntity
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_EMAIL, DEGREE
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResultType
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import (
    API_PATH,
    DOMAIN,
    ISSUE_PLACEHOLDER,
    SENSOR_EMAIL_FIELD,
    SENSOR_NAME_KEY,
    SENSOR_UNIT_KEY,
    SENSOR_VALUE_KEY,
)

NAME_KEY = re.compile(SENSOR_NAME_KEY)
UNIT_KEY = re.compile(SENSOR_UNIT_KEY)
VALUE_KEY = re.compile(SENSOR_VALUE_KEY)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_EMAIL): cv.string,
    }
)


def convert_pid(value):
    """Convert pid from hex string to integer."""
    return int(value, 16)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensor from a config entry created in the integrations UI."""
    unique_id = config_entry.unique_id
    email = config_entry.data.get(CONF_EMAIL)
    sensors: dict[int, TorqueSensor] = {}

    hass.http.register_view(
        TorqueReceiveDataView(email, sensors, async_add_entities, unique_id)
    )


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Torque platform."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data=config,
    )

    if (
        result["type"] == FlowResultType.CREATE_ENTRY
        or result["reason"] == "already_configured"
    ):
        async_create_issue(
            hass,
            HOMEASSISTANT_DOMAIN,
            f"deprecated_yaml_{DOMAIN}",
            breaks_in_ha_version="2024.7.0",
            is_fixable=False,
            issue_domain=DOMAIN,
            severity=IssueSeverity.WARNING,
            translation_key="deprecated_yaml",
            translation_placeholders={
                "domain": DOMAIN,
                "integration_title": "Torque",
            },
        )
    else:
        async_create_issue(
            hass,
            DOMAIN,
            f"deprecated_yaml_import_issue_{result['reason']}",
            breaks_in_ha_version="2024.7.0",
            is_fixable=False,
            issue_domain=DOMAIN,
            severity=IssueSeverity.WARNING,
            translation_key=f"deprecated_yaml_import_issue_{result['reason']}",
            translation_placeholders=ISSUE_PLACEHOLDER,
        )


class TorqueReceiveDataView(HomeAssistantView):
    """Handle data from Torque requests."""

    url = API_PATH
    name = "api:torque"

    def __init__(self, email, sensors, add_entities, unique_id):
        """Initialize a Torque view."""
        self.email = email
        self.sensors = sensors
        self.add_entities = add_entities
        self.unique_id = unique_id

    @callback
    def get(self, request):
        """Handle Torque data request."""
        hass = request.app["hass"]
        data = request.query

        if self.email is not None and self.email != data[SENSOR_EMAIL_FIELD]:
            return

        names = {}
        units = {}
        for key in data:
            is_name = NAME_KEY.match(key)
            is_unit = UNIT_KEY.match(key)
            is_value = VALUE_KEY.match(key)

            if is_name:
                pid = convert_pid(is_name.group(1))
                names[pid] = data[key]
            elif is_unit:
                pid = convert_pid(is_unit.group(1))

                temp_unit = data[key]
                if "\\xC2\\xB0" in temp_unit:
                    temp_unit = temp_unit.replace("\\xC2\\xB0", DEGREE)

                units[pid] = temp_unit
            elif is_value:
                pid = convert_pid(is_value.group(1))
                if pid in self.sensors:
                    self.sensors[pid].async_on_update(data[key])

        for pid, name in names.items():
            if pid not in self.sensors:
                self.sensors[pid] = TorqueSensor(name, units.get(pid), self.unique_id)
                hass.async_add_job(self.add_entities, [self.sensors[pid]])

        return "OK!"


class TorqueSensor(SensorEntity):
    """Representation of a Torque sensor."""

    def __init__(self, name, unit, unique_id):
        """Initialize the sensor."""
        self._name = name
        self._unit = unit
        self._state = None
        self._attr_unique_id = f"{unique_id}_{name}"

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def native_unit_of_measurement(self):
        """Return the unit of measurement."""
        return self._unit

    @property
    def native_value(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def icon(self):
        """Return the default icon of the sensor."""
        return "mdi:car"

    @callback
    def async_on_update(self, value):
        """Receive an update."""
        self._state = value
        self.async_write_ha_state()
