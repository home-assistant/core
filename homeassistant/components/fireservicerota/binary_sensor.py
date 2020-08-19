"""Binary Sensor platform for FireServiceRota integration."""
import logging

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ATTRIBUTION, STATE_OFF, STATE_ON
from homeassistant.helpers.typing import HomeAssistantType

from .const import ATTRIBUTION, BINARY_SENSOR_ENTITY_LIST, DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistantType, entry: ConfigEntry, async_add_entities
) -> None:
    """Set up FireServiceRota binary sensor based on a config entry."""
    data = hass.data[DOMAIN][entry.entry_id]
    unique_id = entry.unique_id

    entities = []
    for (
        sensor_type,
        (name, unit, icon, device_class, enabled_by_default),
    ) in BINARY_SENSOR_ENTITY_LIST.items():

        _LOGGER.debug(
            "Registering entity: %s, %s, %s, %s, %s, %s",
            sensor_type,
            name,
            unit,
            icon,
            device_class,
            enabled_by_default,
        )
        entities.append(
            ResponseBinarySensor(
                data,
                unique_id,
                sensor_type,
                name,
                unit,
                icon,
                device_class,
                enabled_by_default,
            )
        )

    async_add_entities(entities, True)


class ResponseBinarySensor(BinarySensorEntity):
    """Representation of an FireServiceRota sensor."""

    def __init__(
        self,
        data,
        unique_id,
        sensor_type,
        name,
        unit,
        icon,
        device_class,
        enabled_default: bool = True,
    ):
        """Initialize."""
        self._data = data
        self._unique_id = unique_id
        self._type = sensor_type
        self._name = name
        self._unit = unit
        self._icon = icon
        self._device_class = device_class
        self._enabled_default = enabled_default
        self._available = True
        self._state = None
        self._state_attributes = {}

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def icon(self):
        """Return the icon to use in the frontend."""
        return self._icon

    @property
    def state(self):
        """Return the state of the binary sensor."""
        return self._state

    @property
    def unique_id(self) -> str:
        """Return the unique ID for this binary sensor."""
        return f"{self._unique_id}_{self._type}"

    @property
    def device_state_attributes(self):
        """Return available attributes for binary sensor."""
        attr = {}
        attr = self._state_attributes
        attr[ATTR_ATTRIBUTION] = ATTRIBUTION
        return attr

    @property
    def entity_registry_enabled_default(self) -> bool:
        """Return if the entity should be enabled when first added to the entity registry."""
        return self._enabled_default

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._available

    @property
    def device_class(self):
        """Return the device class of the binary sensor."""
        return self._device_class

    @property
    def is_on(self):
        """Return the status of the binary sensor."""
        return self._state

    @property
    def should_poll(self) -> bool:
        """Enable Polling for this binary sensor."""
        return True

    async def async_on_demand_update(self):
        """Update state."""
        self.async_schedule_update_ha_state(True)

    async def async_update(self):
        """Update using FireServiceRota data."""
        if not self.enabled:
            return

        await self._data.async_update()
        _LOGGER.debug(self._data.availability_data)
        try:
            if self._data.availability_data:
                state = self._data.availability_data["available"]
                if state:
                    self._state = STATE_ON
                else:
                    self._state = STATE_OFF
                self._state_attributes = self._data.availability_data
            else:
                self._state = STATE_OFF
        except (KeyError, TypeError) as err:
            _LOGGER.debug("Error while updating %s device state: %s", self._name, err)

        _LOGGER.debug("Entity '%s' state set to: %s", self._name, self._state)
