"""Wrapper for global settings stored in the The Things network entry."""
import logging
from types import MappingProxyType
from typing import TYPE_CHECKING, Any

from homeassistant.config_entries import ConfigEntry

from .const import (
    OPTIONS_FIELD_ENTITY_TYPE,
    OPTIONS_MENU_EDIT_DEVICES,
    OPTIONS_MENU_EDIT_FIELDS,
)

if TYPE_CHECKING:
    from .coordinator import TTNCoordinator
    from .entity import TTN_Entity

_LOGGER = logging.getLogger(__name__)


class TTN_EntrySettings:
    """Wrapper for global settings stored in the The Things network entry."""

    def __init__(self, entry: ConfigEntry) -> None:
        """Init the EntrySettings wrapper."""

        self.__entry = entry

    def get_entities(self) -> dict[str, "TTN_Entity"]:
        """Get created TTN entities."""

        if not hasattr(self.__entry, "entities"):
            self.__entry.entities = dict[str, "TTN_Entity"]({})
        return self.__entry.entities  # type: ignore[attr-defined, no-any-return]

    def get_coordinator(self) -> "TTNCoordinator":
        """Get coordinator."""
        return self.__entry.coordinator  # type: ignore[attr-defined, no-any-return]

    def get_options(self) -> MappingProxyType[str, MappingProxyType[str, Any]]:
        """Get integration options."""
        return self.__entry.options

    def get_device_options(self, device_id: str) -> MappingProxyType[str, Any]:
        """Get device options stored in the entry."""
        devices: MappingProxyType[
            str, MappingProxyType[str, str]
        ] = self.get_options().get(
            OPTIONS_MENU_EDIT_DEVICES,
            MappingProxyType[str, MappingProxyType[str, str]]({}),
        )
        return devices.get(device_id, MappingProxyType[str, str]({}))

    def get_field_options(
        self, device_id: str, field_id: str
    ) -> MappingProxyType[str, Any]:
        """Get field options stored in the entry."""

        fields: MappingProxyType[
            str, MappingProxyType[str, Any]
        ] = self.get_options().get(
            OPTIONS_MENU_EDIT_FIELDS,
            MappingProxyType[str, MappingProxyType[str, Any]]({}),
        )
        return fields.get(field_id, MappingProxyType[str, Any]({}))

    def get_entity_type(self, device_id: str, field_id: str) -> str | None:
        """Get entity type based on the field_id and the integration options."""

        return self.get_field_options(device_id, field_id).get(
            OPTIONS_FIELD_ENTITY_TYPE, None
        )
