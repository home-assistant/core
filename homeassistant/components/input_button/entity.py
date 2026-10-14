"""Entities for the Input Button integration."""

from typing import Self, override

from homeassistant.components.button import ButtonEntity
from homeassistant.const import ATTR_EDITABLE, CONF_ICON, CONF_ID, CONF_NAME
from homeassistant.helpers import collection
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN


# pylint: disable-next=home-assistant-enforce-class-module
class InputButton(collection.CollectionEntity, ButtonEntity, RestoreEntity):
    """Representation of a button."""

    _unrecorded_attributes = frozenset({ATTR_EDITABLE})

    _attr_should_poll = False
    editable: bool

    def __init__(self, config: ConfigType) -> None:
        """Initialize a button."""
        self._config = config
        self._attr_unique_id = config[CONF_ID]

    @classmethod
    @override
    def from_storage(cls, config: ConfigType) -> Self:
        """Return entity instance initialized from storage."""
        button = cls(config)
        button.editable = True
        return button

    @classmethod
    @override
    def from_yaml(cls, config: ConfigType) -> Self:
        """Return entity instance initialized from yaml."""
        button = cls(config)
        button.entity_id = f"{DOMAIN}.{config[CONF_ID]}"
        button.editable = False
        return button

    @property
    @override
    def name(self) -> str | None:
        """Return name of the button."""
        return self._config.get(CONF_NAME)

    @property
    @override
    def icon(self) -> str | None:
        """Return the icon to be used for this entity."""
        return self._config.get(CONF_ICON)

    @property
    @override
    def extra_state_attributes(self) -> dict[str, bool]:
        """Return the state attributes of the entity."""
        return {ATTR_EDITABLE: self.editable}

    @override
    async def async_press(self) -> None:
        """Press the button.

        Left empty intentionally.
        The input button itself doesn't trigger anything.
        """

    @override
    async def async_update_config(self, config: ConfigType) -> None:
        """Handle when the config is updated."""
        self._config = config
        self.async_write_ha_state()
