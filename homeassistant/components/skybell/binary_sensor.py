"""Binary sensor support for the Skybell HD Doorbell."""
import voluptuous as vol

from homeassistant.components.binary_sensor import PLATFORM_SCHEMA, BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ENTITY_NAMESPACE, CONF_MONITORED_CONDITIONS
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv

from . import SkybellDevice
from .const import BINARY_SENSOR_TYPES, DATA_COORDINATOR, DATA_DEVICES, DOMAIN

PLATFORM_SCHEMA = cv.deprecated(
    vol.All(
        PLATFORM_SCHEMA.extend(
            {
                vol.Optional(CONF_ENTITY_NAMESPACE, default=DOMAIN): cv.string,
                vol.Required(CONF_MONITORED_CONDITIONS, default=[]): vol.All(
                    cv.ensure_list, [vol.In(BINARY_SENSOR_TYPES)]
                ),
            }
        )
    )
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities
):
    """Set up Skybell switch."""
    skybell_data = hass.data[DOMAIN][entry.entry_id]

    sensors = []
    for sensor in BINARY_SENSOR_TYPES:
        for device in skybell_data[DATA_DEVICES]:
            sensors.append(
                SkybellBinarySensor(
                    skybell_data[DATA_COORDINATOR],
                    device,
                    sensor,
                    entry.entry_id,
                )
            )

    async_add_entities(sensors)


class SkybellBinarySensor(SkybellDevice, BinarySensorEntity):
    """A binary sensor implementation for Skybell devices."""

    def __init__(
        self,
        coordinator,
        device,
        sensor,
        server_unique_id,
    ):
        """Initialize sensor for Skybell device."""
        super().__init__(coordinator, device, sensor, server_unique_id)
        self._name = f"{device.name} {BINARY_SENSOR_TYPES[sensor][0]}"

        self._sensor = sensor
        self._device = device
        self._device_class = BINARY_SENSOR_TYPES[self._sensor][1]
        self._event = {}
        self._state = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def unique_id(self):
        """Return the unique id of the sensor."""
        return f"{self._server_unique_id}/{self._sensor}"

    @property
    def is_on(self):
        """Return True if the sensor is on."""
        return self._state

    @property
    def device_class(self):
        """Return the class of the sensor."""
        return self._device_class

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        attrs = super().extra_state_attributes

        attrs["event_date"] = self._event.get("createdAt")

        return attrs
