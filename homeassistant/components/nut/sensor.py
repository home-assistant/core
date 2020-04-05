"""Provides a sensor to track various status aspects of a UPS."""
from datetime import timedelta
import logging

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import (
    ATTR_STATE,
    CONF_ALIAS,
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_RESOURCES,
    CONF_USERNAME,
    STATE_UNKNOWN,
)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity

from .const import (
    DEFAULT_HOST,
    DEFAULT_NAME,
    DEFAULT_PORT,
    DOMAIN,
    KEY_STATUS,
    KEY_STATUS_DISPLAY,
    PYNUT_DATA,
    PYNUT_FIRMWARE,
    PYNUT_MANUFACTURER,
    PYNUT_MODEL,
    PYNUT_STATUS,
    PYNUT_UNIQUE_ID,
    SENSOR_TYPES,
    STATE_TYPES,
)

_LOGGER = logging.getLogger(__name__)


SCAN_INTERVAL = timedelta(seconds=60)


PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_HOST, default=DEFAULT_HOST): cv.string,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
        vol.Optional(CONF_ALIAS): cv.string,
        vol.Optional(CONF_USERNAME): cv.string,
        vol.Optional(CONF_PASSWORD): cv.string,
        vol.Required(CONF_RESOURCES): vol.All(cv.ensure_list, [vol.In(SENSOR_TYPES)]),
    }
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Import the platform into a config entry."""

    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_IMPORT}, data=config
        )
    )


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the NUT sensors."""

    config = config_entry.data
    pynut_data = hass.data[DOMAIN][config_entry.entry_id]
    data = pynut_data[PYNUT_DATA]
    status = pynut_data[PYNUT_STATUS]
    unique_id = pynut_data[PYNUT_UNIQUE_ID]
    manufacturer = pynut_data[PYNUT_MANUFACTURER]
    model = pynut_data[PYNUT_MODEL]
    firmware = pynut_data[PYNUT_FIRMWARE]

    entities = []

    name = config[CONF_NAME]
    if CONF_RESOURCES in config_entry.options:
        resources = config_entry.options[CONF_RESOURCES]
    else:
        resources = config_entry.data[CONF_RESOURCES]

    for resource in resources:
        sensor_type = resource.lower()

        # Display status is a special case that falls back to the status value
        # of the UPS instead.
        if sensor_type in status or (
            sensor_type == KEY_STATUS_DISPLAY and KEY_STATUS in status
        ):
            entities.append(
                NUTSensor(
                    name, data, sensor_type, unique_id, manufacturer, model, firmware
                )
            )
        else:
            _LOGGER.warning(
                "Sensor type: %s does not appear in the NUT status "
                "output, cannot add",
                sensor_type,
            )

    async_add_entities(entities, True)


class NUTSensor(Entity):
    """Representation of a sensor entity for NUT status values."""

    def __init__(
        self, name, data, sensor_type, unique_id, manufacturer, model, firmware
    ):
        """Initialize the sensor."""
        self._data = data
        self._type = sensor_type
        self._manufacturer = manufacturer
        self._firmware = firmware
        self._model = model
        self._device_name = name
        self._name = f"{name} {SENSOR_TYPES[sensor_type][0]}"
        self._unit = SENSOR_TYPES[sensor_type][1]
        self._state = None
        self._unique_id = unique_id
        self._display_state = None
        self._available = False

    @property
    def device_info(self):
        """Device info for the ups."""
        if not self._unique_id:
            return None
        device_info = {
            "identifiers": {(DOMAIN, self._unique_id)},
            "name": self._device_name,
        }
        if self._model:
            device_info["model"] = self._model
        if self._manufacturer:
            device_info["manufacturer"] = self._manufacturer
        if self._firmware:
            device_info["sw_version"] = self._firmware
        return device_info

    @property
    def unique_id(self):
        """Sensor Unique id."""
        if not self._unique_id:
            return None
        return f"{self._unique_id}_{self._type}"

    @property
    def name(self):
        """Return the name of the UPS sensor."""
        return self._name

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return SENSOR_TYPES[self._type][2]

    @property
    def state(self):
        """Return entity state from ups."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return self._unit

    @property
    def available(self):
        """Return if the device is polling successfully."""
        return self._available

    @property
    def device_state_attributes(self):
        """Return the sensor attributes."""
        return {ATTR_STATE: self._display_state}

    def update(self):
        """Get the latest status and use it to update our sensor state."""
        status = self._data.status

        if status is None:
            self._available = False
            return

        self._available = True
        self._display_state = _format_display_state(status)
        # In case of the display status sensor, keep a human-readable form
        # as the sensor state.
        if self._type == KEY_STATUS_DISPLAY:
            self._state = self._display_state
        elif self._type not in status:
            self._state = None
        else:
            self._state = status[self._type]


def _format_display_state(status):
    """Return UPS display state."""
    if status is None:
        return STATE_TYPES["OFF"]
    try:
        return " ".join(STATE_TYPES[state] for state in status[KEY_STATUS].split())
    except KeyError:
        return STATE_UNKNOWN
