"""Entities for the Input Select integration."""

from collections import Counter
import logging
from typing import Self, override

from homeassistant.components.select import (
    SelectEntity,
    SelectEntityCapabilityAttribute,
)
from homeassistant.const import CONF_ICON, CONF_ID, CONF_NAME, CONF_OPTIONS
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import collection
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.typing import ConfigType

from .const import CONF_INITIAL, DOMAIN, InputSelectEntityStateAttribute

_LOGGER = logging.getLogger(__package__)


# pylint: disable-next=home-assistant-enforce-class-module
class InputSelect(collection.CollectionEntity, SelectEntity, RestoreEntity):
    """Representation of a select input."""

    _entity_component_unrecorded_attributes = (
        SelectEntity._entity_component_unrecorded_attributes  # noqa: SLF001
        - {SelectEntityCapabilityAttribute.OPTIONS}
    )
    _unrecorded_attributes = frozenset({InputSelectEntityStateAttribute.EDITABLE})

    _attr_should_poll = False
    editable: bool

    def __init__(self, config: ConfigType) -> None:
        """Initialize a select input."""
        self._attr_current_option = config.get(CONF_INITIAL)
        self._attr_icon = config.get(CONF_ICON)
        self._attr_name = config.get(CONF_NAME)
        self._attr_options = config[CONF_OPTIONS]
        self._attr_unique_id = config[CONF_ID]

    @classmethod
    @override
    def from_storage(cls, config: ConfigType) -> Self:
        """Return entity instance initialized from storage."""
        input_select = cls(config)
        input_select.editable = True
        return input_select

    @classmethod
    @override
    def from_yaml(cls, config: ConfigType) -> Self:
        """Return entity instance initialized from yaml."""
        input_select = cls(config)
        input_select.entity_id = f"{DOMAIN}.{config[CONF_ID]}"
        input_select.editable = False
        return input_select

    @override
    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added."""
        await super().async_added_to_hass()
        if self.current_option is not None:
            return

        state = await self.async_get_last_state()
        if not state or state.state not in self.options:
            self._attr_current_option = self.options[0]
        else:
            self._attr_current_option = state.state

    @property
    @override
    def extra_state_attributes(self) -> dict[str, bool]:
        """Return the state attributes."""
        return {InputSelectEntityStateAttribute.EDITABLE: self.editable}

    @override
    async def async_select_option(self, option: str) -> None:
        """Select new option."""
        if option not in self.options:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="invalid_option",
                translation_placeholders={
                    "entity_id": self.entity_id,
                    "option": option,
                    "options": ", ".join(self.options),
                },
            )
        self._attr_current_option = option
        self.async_write_ha_state()

    async def async_set_options(self, options: list[str]) -> None:
        """Set options."""
        if duplicates := [
            option for option, count in Counter(options).items() if count > 1
        ]:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="duplicate_options",
                translation_placeholders={
                    "entity_id": self.entity_id,
                    "duplicates": ", ".join(duplicates),
                },
            )

        self._attr_options = options

        if self.current_option not in self.options:
            _LOGGER.warning(
                "Current option: %s no longer valid (possible options: %s)",
                self.current_option,
                ", ".join(self.options),
            )
            self._attr_current_option = options[0]

        self.async_write_ha_state()

    @override
    async def async_update_config(self, config: ConfigType) -> None:
        """Handle when the config is updated."""
        self._attr_icon = config.get(CONF_ICON)
        self._attr_name = config.get(CONF_NAME)
        self._attr_options = config[CONF_OPTIONS]
        self.async_write_ha_state()
