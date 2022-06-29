"""Support for tariff selection."""
from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.components.select import SelectEntity
from homeassistant.components.select.const import (
    ATTR_OPTION,
    ATTR_OPTIONS,
    DOMAIN as SELECT_DOMAIN,
    SERVICE_SELECT_OPTION,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_FRIENDLY_NAME,
    CONF_UNIQUE_ID,
    STATE_UNAVAILABLE,
)
from homeassistant.core import Event, HomeAssistant, callback, split_entity_id
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import (
    ATTR_TARIFF,
    ATTR_TARIFFS,
    CONF_METER,
    CONF_TARIFFS,
    DATA_LEGACY_COMPONENT,
    DATA_UTILITY,
    SERVICE_SELECT_NEXT_TARIFF,
    SERVICE_SELECT_TARIFF,
    TARIFF_ICON,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Initialize Utility Meter config entry."""
    name = config_entry.title
    tariffs = config_entry.options[CONF_TARIFFS]

    legacy_add_entities = None
    unique_id = config_entry.entry_id
    tariff_select = TariffSelect(name, tariffs, legacy_add_entities, unique_id)
    async_add_entities([tariff_select])


async def async_setup_platform(
    hass: HomeAssistant,
    conf: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the utility meter select."""
    if discovery_info is None:
        _LOGGER.error(
            "This platform is not available to configure "
            "from 'select:' in configuration.yaml"
        )
        return

    legacy_component = hass.data[DATA_LEGACY_COMPONENT]
    meter: str = discovery_info[CONF_METER]
    conf_meter_unique_id: str | None = hass.data[DATA_UTILITY][meter].get(
        CONF_UNIQUE_ID
    )

    async_add_entities(
        [
            TariffSelect(
                discovery_info[CONF_METER],
                discovery_info[CONF_TARIFFS],
                legacy_component.async_add_entities,
                conf_meter_unique_id,
            )
        ]
    )

    legacy_component.async_register_entity_service(
        SERVICE_SELECT_TARIFF,
        {vol.Required(ATTR_TARIFF): cv.string},
        "async_select_tariff",
    )

    legacy_component.async_register_entity_service(
        SERVICE_SELECT_NEXT_TARIFF, {}, "async_next_tariff"
    )


class TariffSelect(SelectEntity, RestoreEntity):
    """Representation of a Tariff selector."""

    def __init__(self, name, tariffs, add_legacy_entities, unique_id):
        """Initialize a tariff selector."""
        self._attr_name = name
        self._attr_unique_id = unique_id
        self._current_tariff = None
        self._tariffs = tariffs
        self._attr_icon = TARIFF_ICON
        self._attr_should_poll = False
        self._add_legacy_entities = add_legacy_entities

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

        if self._add_legacy_entities:
            await self._add_legacy_entities([LegacyTariffSelect(self.entity_id)])

        state = await self.async_get_last_state()
        if not state or state.state not in self._tariffs:
            self._current_tariff = self._tariffs[0]
        else:
            self._current_tariff = state.state

    async def async_select_option(self, option: str) -> None:
        """Select new tariff (option)."""
        self._current_tariff = option
        self.async_write_ha_state()


class LegacyTariffSelect(Entity):
    """Backwards compatibility for deprecated utility_meter select entity."""

    def __init__(self, tracked_entity_id):
        """Initialize the entity."""
        self._attr_icon = TARIFF_ICON
        # Set name to influence entity_id
        self._attr_name = split_entity_id(tracked_entity_id)[1]
        self.tracked_entity_id = tracked_entity_id

    @callback
    def async_state_changed_listener(self, event: Event | None = None) -> None:
        """Handle child updates."""
        if (
            state := self.hass.states.get(self.tracked_entity_id)
        ) is None or state.state == STATE_UNAVAILABLE:
            self._attr_available = False
            return

        self._attr_available = True

        self._attr_name = state.attributes.get(ATTR_FRIENDLY_NAME)
        self._attr_state = state.state
        self._attr_extra_state_attributes = {
            ATTR_TARIFFS: state.attributes.get(ATTR_OPTIONS)
        }

    async def async_added_to_hass(self) -> None:
        """Register callbacks."""

        @callback
        def _async_state_changed_listener(event: Event | None = None) -> None:
            """Handle child updates."""
            self.async_state_changed_listener(event)
            self.async_write_ha_state()

        self.async_on_remove(
            async_track_state_change_event(
                self.hass, [self.tracked_entity_id], _async_state_changed_listener
            )
        )

        # Call once on adding
        _async_state_changed_listener()

    async def async_select_tariff(self, tariff):
        """Select new option."""
        _LOGGER.warning(
            "The 'utility_meter.select_tariff' service has been deprecated and will "
            "be removed in HA Core 2022.7. Please use 'select.select_option' instead",
        )
        await self.hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {ATTR_ENTITY_ID: self.tracked_entity_id, ATTR_OPTION: tariff},
            blocking=True,
            context=self._context,
        )

    async def async_next_tariff(self):
        """Offset current index."""
        _LOGGER.warning(
            "The 'utility_meter.next_tariff' service has been deprecated and will "
            "be removed in HA Core 2022.7. Please use 'select.select_option' instead",
        )
        if (
            not self.available
            or (state := self.hass.states.get(self.tracked_entity_id)) is None
        ):
            return
        tariffs = state.attributes.get(ATTR_OPTIONS)
        current_tariff = state.state
        current_index = tariffs.index(current_tariff)
        new_index = (current_index + 1) % len(tariffs)

        await self.async_select_tariff(tariffs[new_index])
