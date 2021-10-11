"""Provides a number entity for Home Connect."""
import logging

from homeconnect.api import HomeConnectError

from homeassistant.components.number import NumberEntity
from homeassistant.const import CONF_ENTITIES

from .const import ATTR_SETTING, ATTR_VALUE, DOMAIN
from .entity import HomeConnectEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Home Connect number entity."""

    def get_entities():
        """Get a list of entities."""
        entities = []
        hc_api = hass.data[DOMAIN][config_entry.entry_id]
        for device_dict in hc_api.devices:
            entity_dicts = device_dict.get(CONF_ENTITIES, {}).get("number", [])
            entity_list = []
            for d in entity_dicts:
                if ATTR_SETTING in d:
                    entity_list += [HomeConnectSettingNumberEntity(**d)]
            entities += entity_list
        return entities

    async_add_entities(await hass.async_add_executor_job(get_entities), True)


class HomeConnectSettingNumberEntity(HomeConnectEntity, NumberEntity):
    """Setting number entity class for Home Connect."""

    def __init__(self, device, setting, desc, icon):
        """Initialize the entity."""
        super().__init__(device, desc)
        self._value = None
        self._setting = setting
        self._icon = icon

        self._min_value = None
        self._max_value = None

        self._unit_of_measurement = None

        data = self.device.appliance.get(f"/settings/{self._setting}")
        constraints = data.get("constraints")
        if "min" in constraints:
            self._min_value = constraints.get("min")
        if "max" in constraints:
            self._max_value = constraints.get("max")

        if "unit" in data:
            self._unit_of_measurement = data.get("unit")

    @property
    def icon(self):
        """Return the icon."""
        return self._icon

    @property
    def min_value(self):
        """Return the min value."""
        if self._min_value is None:
            return 0
        return int(self._min_value)

    @property
    def max_value(self):
        """Return the max value."""
        if self._max_value is None:
            return 100
        return int(self._max_value)

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return self._unit_of_measurement

    @property
    def value(self):
        """Return the number value."""
        return int(self._value)

    @property
    def available(self):
        """Return true if the entity is available."""
        return True

    async def async_set_value(self, value: float) -> None:
        """Set number."""
        _LOGGER.debug("Tried to set number %s to %s", self.name, value)
        try:
            await self.hass.async_add_executor_job(
                self.device.appliance.set_setting, self._setting, value
            )
        except HomeConnectError as err:
            _LOGGER.error("Error while trying to set setting: %s", err)
        self.async_entity_update()

    async def async_update(self):
        """Update the number's status."""
        state = self.device.appliance.status.get(self._setting, {})
        self._value = state.get(ATTR_VALUE)
        _LOGGER.debug("Updated, new value: %s", self._value)
