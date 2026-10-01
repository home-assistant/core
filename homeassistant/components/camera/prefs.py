"""Preference management for camera component."""

from collections.abc import Mapping
from dataclasses import asdict, dataclass
from typing import Final, cast

from homeassistant.components.stream import Orientation
from homeassistant.core import Event, HomeAssistant, callback, split_entity_id
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.storage import Store
from homeassistant.helpers.typing import UNDEFINED, UndefinedType

from .const import DATA_CAMERA_PREFS, DOMAIN, PREF_ORIENTATION, PREF_PRELOAD_STREAM

STORAGE_KEY: Final = DOMAIN
STORAGE_VERSION: Final = 1


@dataclass
class DynamicStreamSettings:
    """Stream settings which are managed and updated by the camera entity."""

    preload_stream: bool = False
    orientation: Orientation = Orientation.NO_TRANSFORM


class CameraPreferences:
    """Handle camera preferences."""

    _preload_prefs: dict[str, dict[str, bool | Orientation]]

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize camera prefs."""
        self._hass = hass
        # The orientation prefs are stored in in the entity registry options
        # The preload_stream prefs are stored in this Store
        self._store = Store[dict[str, dict[str, bool | Orientation]]](
            hass, STORAGE_VERSION, STORAGE_KEY
        )
        self._dynamic_stream_settings_by_entity_id: dict[
            str, DynamicStreamSettings
        ] = {}

    async def async_load(self) -> None:
        """Initialize the camera preferences."""
        self._preload_prefs = await self._store.async_load() or {}
        self._hass.bus.async_listen(
            er.EVENT_ENTITY_REGISTRY_UPDATED,
            self._async_entity_registry_updated,
            event_filter=self._async_entity_registry_filter,
        )

    @callback
    def _async_entity_registry_filter(
        self, event_data: er.EventEntityRegistryUpdatedData
    ) -> bool:
        """Filter entity registry events for renamed cameras."""
        return (
            event_data["action"] == "update"
            and "old_entity_id" in event_data
            and split_entity_id(event_data["entity_id"])[0] == DOMAIN
        )

    @callback
    def _async_entity_registry_updated(
        self, event: Event[er.EventEntityRegistryUpdatedData]
    ) -> None:
        """Move the preferences of a renamed camera to its new entity_id."""
        data = event.data
        assert data["action"] == "update"
        old_entity_id = data["old_entity_id"]
        new_entity_id = data["entity_id"]

        # Keep the same object, a running Stream holds a reference to it
        if settings := self._dynamic_stream_settings_by_entity_id.pop(
            old_entity_id, None
        ):
            self._dynamic_stream_settings_by_entity_id[new_entity_id] = settings
        else:
            self._dynamic_stream_settings_by_entity_id.pop(new_entity_id, None)

        old_prefs = self._preload_prefs.pop(old_entity_id, None)
        new_prefs = self._preload_prefs.pop(new_entity_id, None)
        if old_prefs is not None:
            self._preload_prefs[new_entity_id] = old_prefs
        if old_prefs is not None or new_prefs is not None:
            self._store.async_delay_save(lambda: self._preload_prefs, 0)

    async def async_update(
        self,
        entity_id: str,
        *,
        preload_stream: bool | UndefinedType = UNDEFINED,
        orientation: Orientation | UndefinedType = UNDEFINED,
    ) -> dict[str, bool | Orientation]:
        """Update camera preferences.

        Also update the DynamicStreamSettings if they exist.
        preload_stream is stored in a Store
        orientation is stored in the Entity Registry

        Returns a dict with the preferences on success.
        Raises HomeAssistantError on failure.
        """
        dynamic_stream_settings = self._dynamic_stream_settings_by_entity_id.get(
            entity_id
        )
        if preload_stream is not UNDEFINED:
            if dynamic_stream_settings:
                dynamic_stream_settings.preload_stream = preload_stream
            self._preload_prefs[entity_id] = {PREF_PRELOAD_STREAM: preload_stream}
            await self._store.async_save(self._preload_prefs)

        if orientation is not UNDEFINED:
            if (registry := er.async_get(self._hass)).async_get(entity_id):
                registry.async_update_entity_options(
                    entity_id, DOMAIN, {PREF_ORIENTATION: orientation}
                )
            else:
                raise HomeAssistantError(
                    "Orientation is only supported on entities set up through config"
                    " flows"
                )
            if dynamic_stream_settings:
                dynamic_stream_settings.orientation = orientation
        return asdict(await self.get_dynamic_stream_settings(entity_id))

    async def get_dynamic_stream_settings(
        self, entity_id: str
    ) -> DynamicStreamSettings:
        """Get the DynamicStreamSettings for the entity."""
        if settings := self._dynamic_stream_settings_by_entity_id.get(entity_id):
            return settings
        # Get preload stream setting from prefs
        # Get orientation setting from entity registry
        reg_entry = er.async_get(self._hass).async_get(entity_id)
        er_prefs: Mapping = reg_entry.options.get(DOMAIN, {}) if reg_entry else {}
        settings = DynamicStreamSettings(
            preload_stream=cast(
                bool,
                self._preload_prefs.get(entity_id, {}).get(PREF_PRELOAD_STREAM, False),
            ),
            orientation=er_prefs.get(PREF_ORIENTATION, Orientation.NO_TRANSFORM),
        )
        self._dynamic_stream_settings_by_entity_id[entity_id] = settings
        return settings


async def get_dynamic_camera_stream_settings(
    hass: HomeAssistant, entity_id: str
) -> DynamicStreamSettings:
    """Get dynamic stream settings for a camera entity."""
    if DATA_CAMERA_PREFS not in hass.data:
        raise HomeAssistantError("Camera integration not set up")
    return await hass.data[DATA_CAMERA_PREFS].get_dynamic_stream_settings(entity_id)
