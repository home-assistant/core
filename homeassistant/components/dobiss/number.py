"""Support for dobiss climate control."""
import logging

from dobissapi import DobissTempSensor

from homeassistant.components.number import NumberEntity
from homeassistant.helpers.restore_state import RestoreEntity

from .const import CONF_IGNORE_ZIGBEE_DEVICES, DOMAIN, KEY_API

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up dobisssensor."""

    _LOGGER.debug(f"Setting up number component of {DOMAIN}")
    dobiss = hass.data[DOMAIN][config_entry.entry_id][KEY_API].api

    # only add number objects for temperature sensors when there is at least a schedule entry
    if len(dobiss.calendars) == 0:
        return

    entities = []
    d_entities = dobiss.get_devices_by_type(DobissTempSensor)
    for d in d_entities:
        if (
            config_entry.options.get(CONF_IGNORE_ZIGBEE_DEVICES) is not None
            and config_entry.options.get(CONF_IGNORE_ZIGBEE_DEVICES)
            and (d.address in (210, 211))
        ):
            continue
        entities.append(HADobissNumber(d))
    if entities:
        async_add_entities(entities)


class HADobissNumber(NumberEntity, RestoreEntity):
    """Dobiss number device."""

    should_poll = False

    native_min_value = -30

    native_max_value = 60 * 24

    native_step = 15

    def __init__(self, dobisssensor: DobissTempSensor):
        """Init dobiss Number device."""
        super().__init__()
        self._dobisssensor = dobisssensor

    @property
    def device_info(self):
        """Information about this entity/device."""
        return {
            "identifiers": {(DOMAIN, f"climatecontrol_{self._dobisssensor.object_id}")},
        }

    @property
    def available(self) -> bool:
        """Return True."""
        return True

    async def async_added_to_hass(self):
        """Run when this Entity has been added to HA."""
        self._dobisssensor.register_callback(self.async_write_ha_state)
        last_state = await self.async_get_last_state()
        if last_state:
            await self.async_set_native_value(float(last_state.state))

    async def async_will_remove_from_hass(self):
        """Entity being removed from hass."""
        self._dobisssensor.remove_callback(self.async_write_ha_state)

    @property
    def name(self):
        """Return the display name of this sensor."""
        return f"{self._dobisssensor.name} Default Time"

    @property
    def unique_id(self):
        """Return a unique ID."""
        return f"default_time_{self._dobisssensor.object_id}"

    @property
    def native_value(self) -> float:
        """Return the entity value to represent the entity state."""
        return float(self._dobisssensor.default_time)

    async def async_set_native_value(self, value: float):
        """Set new value."""
        await self._dobisssensor.set_default_time(round(value))
