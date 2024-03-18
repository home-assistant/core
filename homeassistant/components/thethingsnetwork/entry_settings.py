"""Wrapper for global settings stored in the The Things network entry."""
import logging
from types import MappingProxyType
from typing import Any

from homeassistant.config_entries import ConfigEntry

from .const import (
    OPTIONS_FIELD_DEVICE_SCOPE,
    OPTIONS_FIELD_ENTITY_TYPE,
    OPTIONS_MENU_EDIT_DEVICES,
    OPTIONS_MENU_EDIT_FIELDS,
)

_LOGGER = logging.getLogger(__name__)


class TTN_EntrySettings:
    """Wrapper for global settings stored in the The Things network entry."""

    def __init__(self, entry: ConfigEntry) -> None:
        """Init the EntrySettings wrapper."""

        self.__entry = entry

    def get_entities(self) -> dict:
        """Get created TTN entities."""

        if not hasattr(self.__entry, "entities"):
            self.__entry.entities = {}
        return self.__entry.entities  # type: ignore[attr-defined]

    def get_coordinator(self):
        """Get coordinator."""
        return self.__entry.coordinator

    def get_options(self) -> MappingProxyType[str, Any]:
        """Get integration options."""
        return self.__entry.options

    def get_device_options(self, device_id) -> dict[str, Any]:
        """Get device options stored in the entry."""
        devices = self.get_options().get(OPTIONS_MENU_EDIT_DEVICES, {})
        return devices.get(device_id, {})

    def get_field_options(self, device_id, field_id):
        """Get field options stored in the entry."""

        fields = self.get_options().get(OPTIONS_MENU_EDIT_FIELDS, {})
        field_opts = fields.get(field_id, {})
        if field_opts.get(OPTIONS_FIELD_DEVICE_SCOPE, device_id) == device_id:
            return field_opts
        return {}

    def get_entity_type(self, device_id, field_id):
        """Get entity type based on the field_id and the integration options."""

        return self.get_field_options(device_id, field_id).get(
            OPTIONS_FIELD_ENTITY_TYPE, None
        )
