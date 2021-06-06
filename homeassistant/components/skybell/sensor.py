"""Sensor support for Skybell Doorbells."""
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA, SensorEntity
from homeassistant.const import CONF_ENTITY_NAMESPACE, CONF_MONITORED_CONDITIONS
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv

from . import SkybellDevice
from .const import DATA_COORDINATOR, DATA_DEVICES, DOMAIN, SENSOR_TYPES

PLATFORM_SCHEMA = cv.deprecated(
    vol.All(
        PLATFORM_SCHEMA.extend(
            {
                vol.Optional(CONF_ENTITY_NAMESPACE, default=DOMAIN): cv.string,
                vol.Required(CONF_MONITORED_CONDITIONS, default=[]): vol.All(
                    cv.ensure_list, [vol.In(SENSOR_TYPES)]
                ),
            }
        )
    )
)


async def async_setup_entry(hass: HomeAssistant, entry, async_add_entities):
    """Set up Skybell sensor."""
    skybell_data = hass.data[DOMAIN][entry.entry_id]

    sensors = []
    for sensor in SENSOR_TYPES:
        for device in skybell_data[DATA_DEVICES]:
            sensors.append(
                SkybellSensor(
                    skybell_data[DATA_COORDINATOR],
                    device,
                    sensor,
                    entry.entry_id,
                )
            )

    async_add_entities(sensors)


class SkybellSensor(SkybellDevice, SensorEntity):
    """A sensor implementation for Skybell devices."""

    def __init__(
        self,
        coordinator,
        device,
        sensor_type,
        server_unique_id,
    ):
        """Initialize sensor for Skybell device."""
        super().__init__(coordinator, device, sensor_type, server_unique_id)
        self._name = f"{device.name} {SENSOR_TYPES[sensor_type][0]}"

        self._type = sensor_type
        self._icon = SENSOR_TYPES[self._type][1]
        self._device = device
        self._state = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def unique_id(self):
        """Return the unique id of the sensor."""
        return f"{self._server_unique_id}/{self._type}"

    @property
    def state(self):
        """Return the state of the sensor."""
        if self._type == "chime_level":
            self._state = self._device.outdoor_chime_level
            return self._state
        return self._state

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return self._icon
