"""Support for tariff selection."""

import logging

import voluptuous as vol

from homeassistant.components.select import SelectEntity
from homeassistant.helpers import config_validation as cv, entity_platform
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.restore_state import RestoreEntity

from .const import (
    ATTR_TARIFF,
    ATTR_TARIFFS,
    CONF_METER,
    CONF_TARIFFS,
    SERVICE_RESET,
    SERVICE_SELECT_NEXT_TARIFF,
    SERVICE_SELECT_TARIFF,
    SIGNAL_RESET_METER,
    TARIFF_ICON,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(hass, conf, async_add_entities, discovery_info=None):
    """Set up the utility meter select."""
    if discovery_info is None:
        _LOGGER.error("This platform is only available through discovery")
        return

    async_add_entities(
        [TariffSelect(discovery_info[CONF_METER], discovery_info[CONF_TARIFFS])]
    )

    platform = entity_platform.async_get_current_platform()

    platform.async_register_entity_service(SERVICE_RESET, {}, "async_reset_meters")

    platform.async_register_entity_service(
        SERVICE_SELECT_TARIFF,
        {vol.Required(ATTR_TARIFF): cv.string},
        "async_select_option",
    )

    platform.async_register_entity_service(
        SERVICE_SELECT_NEXT_TARIFF, {}, "async_next_tariff"
    )


class TariffSelect(SelectEntity, RestoreEntity):
    """Representation of a Tariff selector."""

    def __init__(self, name, tariffs):
        """Initialize a tariff selector."""
        self._attr_name = name
        self._current_tariff = None
        self._tariffs = tariffs
        self._attr_icon = TARIFF_ICON
        self._attr_should_poll = False

    @property
    def options(self):
        """Return the available tariffs."""
        return self._tariffs

    @property
    def current_option(self):
        """Return current tariff."""
        return self._current_tariff

    async def async_added_to_hass(self):
        """Run when entity about to be added."""
        await super().async_added_to_hass()
        if self._current_tariff is not None:
            return

        state = await self.async_get_last_state()
        if not state or state.state not in self._tariffs:
            self._current_tariff = self._tariffs[0]
        else:
            self._current_tariff = state.state

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        return {ATTR_TARIFFS: self._tariffs}

    async def async_reset_meters(self):
        """Reset all sensors of this meter."""
        _LOGGER.debug("reset meter %s", self.entity_id)
        async_dispatcher_send(self.hass, SIGNAL_RESET_METER, self.entity_id)

    async def async_select_option(self, tariff: str) -> None:
        """Select new option."""
        if tariff not in self._tariffs:
            _LOGGER.warning(
                "Invalid tariff: %s (possible tariffs: %s)",
                tariff,
                ", ".join(self._tariffs),
            )
            return
        self._current_tariff = tariff
        self.async_write_ha_state()

    async def async_next_tariff(self):
        """Offset current index."""
        current_index = self._tariffs.index(self._current_tariff)
        new_index = (current_index + 1) % len(self._tariffs)
        self._current_tariff = self._tariffs[new_index]
        self.async_write_ha_state()
