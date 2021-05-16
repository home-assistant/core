"""Provides a sensor to track various status aspects of a UPS."""
import logging

from homeassistant.components.sensor import SensorEntity
from homeassistant.const import ATTR_STATE, CONF_RESOURCES, STATE_UNKNOWN
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    COORDINATOR,
    DOMAIN,
    KEY_STATUS,
    KEY_STATUS_DISPLAY,
    PYNUT_DATA,
    PYNUT_FIRMWARE,
    PYNUT_MANUFACTURER,
    PYNUT_MODEL,
    PYNUT_NAME,
    PYNUT_UNIQUE_ID,
    SENSOR_DEVICE_CLASS,
    SENSOR_ICON,
    SENSOR_NAME,
    SENSOR_TYPES,
    SENSOR_UNIT,
    STATE_TYPES,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the NUT sensors."""

    pynut_data = hass.data[DOMAIN][config_entry.entry_id]
    unique_id = pynut_data[PYNUT_UNIQUE_ID]
    manufacturer = pynut_data[PYNUT_MANUFACTURER]
    model = pynut_data[PYNUT_MODEL]
    firmware = pynut_data[PYNUT_FIRMWARE]
    name = pynut_data[PYNUT_NAME]
    coordinator = pynut_data[COORDINATOR]
    data = pynut_data[PYNUT_DATA]
    status = data.status

    entities = []

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
                    coordinator,
                    data,
                    name.title(),
                    sensor_type,
                    unique_id,
                    manufacturer,
                    model,
                    firmware,
                )
            )
        else:
            _LOGGER.info(
                "Sensor type: %s does not appear in the NUT status "
                "output, cannot add",
                sensor_type,
            )

    async_add_entities(entities, True)


class NUTSensor(CoordinatorEntity, SensorEntity):
    """Representation of a sensor entity for NUT status values."""

    def __init__(
        self,
        coordinator,
        data,
        name,
        sensor_type,
        unique_id,
        manufacturer,
        model,
        firmware,
    ):
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._type = sensor_type
        self._manufacturer = manufacturer
        self._firmware = firmware
        self._model = model
        self._device_name = name
        self._name = f"{name} {SENSOR_TYPES[sensor_type][SENSOR_NAME]}"
        self._unit = SENSOR_TYPES[sensor_type][SENSOR_UNIT]
        self._data = data
        self._unique_id = unique_id

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
        if SENSOR_TYPES[self._type][SENSOR_DEVICE_CLASS]:
            # The UI will assign an icon
            # if it has a class
            return None
        return SENSOR_TYPES[self._type][SENSOR_ICON]

    @property
    def device_class(self):
        """Device class of the sensor."""
        return SENSOR_TYPES[self._type][SENSOR_DEVICE_CLASS]

    @property
    def state(self):
        """Return entity state from ups."""
        if not self._data.status:
            return None
        if self._type == KEY_STATUS_DISPLAY:
            return _format_display_state(self._data.status)
        return self._data.status.get(self._type)

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return self._unit

    @property
    def extra_state_attributes(self):
        """Return the sensor attributes."""
        return {ATTR_STATE: _format_display_state(self._data.status)}


def _format_display_state(status):
    """Return UPS display state."""
    if status is None:
        return STATE_TYPES["OFF"]
    try:
        return " ".join(STATE_TYPES[state] for state in status[KEY_STATUS].split())
    except KeyError:
        return STATE_UNKNOWN
