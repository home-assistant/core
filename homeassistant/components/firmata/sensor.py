"""Support for Firmata sensor input."""

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME, CONF_PIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import Entity

from .const import CONF_DIFFERENTIAL, CONF_PIN_MODE, DOMAIN
from .entity import FirmataPinEntity
from .pin import FirmataAnalogInput, FirmataPinUsedException

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, config_entry: ConfigEntry, async_add_entities
) -> None:
    """Set up the Firmata sensors."""
    new_entities = []

    board = hass.data[DOMAIN][config_entry.entry_id]
    for sensor in board.sensors:
        pin = sensor[CONF_PIN]
        pin_mode = sensor[CONF_PIN_MODE]
        differential = sensor[CONF_DIFFERENTIAL]
        api = FirmataAnalogInput(board, pin, pin_mode, differential)
        try:
            api.setup()
        except FirmataPinUsedException:
            _LOGGER.error(
                "Could not setup sensor on pin %s since pin already in use",
                sensor[CONF_PIN],
            )
            continue
        name = sensor[CONF_NAME]
        sensor_entity = FirmataSensor(api, config_entry, name, pin)
        new_entities.append(sensor_entity)

    if new_entities:
        async_add_entities(new_entities)


class FirmataSensor(FirmataPinEntity, Entity):
    """Representation of a sensor on a Firmata board."""

    async def async_added_to_hass(self) -> None:
        """Set up a sensor."""
        await self._api.start_pin(self.async_write_ha_state)

    async def async_will_remove_from_hass(self) -> None:
        """Stop reporting a sensor."""
        await self._api.stop_pin()

    @property
    def state(self) -> int:
        """Return sensor state."""
        return self._api.state
