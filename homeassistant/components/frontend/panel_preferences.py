"""Panel preferences for the frontend."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.const import EVENT_PANELS_UPDATED
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import collection, storage
from homeassistant.helpers.typing import VolDictType
from homeassistant.util.hass_dict import HassKey

DOMAIN = "frontend"

CONF_SHOW_IN_SIDEBAR = "show_in_sidebar"

STORAGE_KEY = f"{DOMAIN}_panel_preferences"
STORAGE_VERSION = 1

DATA_PANEL_PREFERENCES: HassKey[PanelPreferencesCollection] = HassKey(
    "frontend_panel_preferences"
)

PANEL_PREFERENCE_CREATE_FIELDS: VolDictType = {
    vol.Required("panel_id"): str,
    vol.Optional(CONF_SHOW_IN_SIDEBAR): bool,
}

PANEL_PREFERENCE_UPDATE_FIELDS: VolDictType = {
    vol.Optional(CONF_SHOW_IN_SIDEBAR): bool,
}


async def async_setup_panel_preferences(hass: HomeAssistant) -> None:
    """Set up panel preferences."""
    panel_prefs_collection = PanelPreferencesCollection(hass)
    await panel_prefs_collection.async_load()

    hass.data[DATA_PANEL_PREFERENCES] = panel_prefs_collection

    collection.DictStorageCollectionWebsocket(
        panel_prefs_collection,
        "frontend/panel_preferences",
        "panel_preference",
        PANEL_PREFERENCE_CREATE_FIELDS,
        PANEL_PREFERENCE_UPDATE_FIELDS,
    ).async_setup(hass)


class PanelPreferencesCollection(collection.DictStorageCollection):
    """Panel preferences collection."""

    CREATE_SCHEMA = vol.Schema(PANEL_PREFERENCE_CREATE_FIELDS)
    UPDATE_SCHEMA = vol.Schema(PANEL_PREFERENCE_UPDATE_FIELDS)

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize panel preferences collection."""
        super().__init__(
            storage.Store(hass, STORAGE_VERSION, STORAGE_KEY),
        )

    async def _process_create_data(self, data: dict[str, Any]) -> dict[str, Any]:
        """Validate the config is valid."""
        return self.CREATE_SCHEMA(data)  # type: ignore[no-any-return]

    @callback
    def _get_suggested_id(self, info: dict[str, Any]) -> str:
        """Suggest an ID based on the panel_id."""
        return str(info["panel_id"])

    async def _update_data(
        self, item: dict[str, Any], update_data: dict[str, Any]
    ) -> dict[str, Any]:
        """Return a new updated item."""
        update_data = self.UPDATE_SCHEMA(update_data)
        updated = {**item, **update_data}
        # Fire panels updated event so frontend knows to refresh
        self.hass.bus.async_fire(EVENT_PANELS_UPDATED)
        return updated

    def _create_item(self, item_id: str, data: dict[str, Any]) -> dict[str, Any]:
        """Create an item from its validated, serialized representation."""
        # Fire panels updated event so frontend knows to refresh
        self.hass.bus.async_fire(EVENT_PANELS_UPDATED)
        return super()._create_item(item_id, data)

    async def async_delete_item(self, item_id: str) -> None:
        """Delete a panel preference."""
        await super().async_delete_item(item_id)
        # Fire panels updated event so frontend knows to refresh
        self.hass.bus.async_fire(EVENT_PANELS_UPDATED)


@callback
def async_get_panel_preferences(
    hass: HomeAssistant,
) -> dict[str, dict[str, Any]]:
    """Get panel preferences."""
    if DATA_PANEL_PREFERENCES not in hass.data:
        return {}

    collection_obj: PanelPreferencesCollection = hass.data[DATA_PANEL_PREFERENCES]
    return collection_obj.data
