"""The Indoor Air Quality integration.

Calculates an Indoor Air Quality (IAQ) index from a configurable set of
sensor sources, using a configurable rating standard.
"""

import logging
from typing import Any, Final, cast

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_DEVICE_ID, Platform
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers.event import (
    EventStateChangedData,
    async_track_state_change_event,
)
from homeassistant.helpers.helper_integration import async_handle_source_entity_changes

from .const import CONF_SOURCES, CONF_STANDARD, DEFAULT_STANDARD, STANDARDS
from .coordinator import SOURCE_SPECS, IndoorAirQualityController
from .helpers import entity_ids_from_sources, unique_id_from_sources

_LOGGER: Final = logging.getLogger(__name__)

PLATFORMS: Final = [Platform.SENSOR]


_SOURCES_SCHEMA: Final = vol.Schema({vol.In(SOURCE_SPECS): str})

_ENTRY_DATA_SCHEMA: Final = vol.Schema(
    {
        vol.Required(CONF_SOURCES): vol.All(
            _SOURCES_SCHEMA,
            vol.Length(min=1),
        ),
        vol.Optional(CONF_STANDARD, default=DEFAULT_STANDARD): vol.In(STANDARDS),
        vol.Optional(CONF_DEVICE_ID): vol.Any(str, None),
    },
    extra=vol.ALLOW_EXTRA,
)


type IndoorAirQualityConfigEntry = ConfigEntry[IndoorAirQualityController]


def _validate_entry_data(entry: IndoorAirQualityConfigEntry) -> dict[str, Any]:
    """Validate ``entry.data``; raise :class:`ConfigEntryError` on failure."""
    try:
        validated = _ENTRY_DATA_SCHEMA(dict(entry.data))
    except vol.Invalid as err:
        raise ConfigEntryError(
            f"Invalid Indoor Air Quality config entry data: {err}"
        ) from err
    return cast(dict[str, Any], validated)


async def async_setup_entry(
    hass: HomeAssistant, entry: IndoorAirQualityConfigEntry
) -> bool:
    """Set up Indoor Air Quality from a config entry."""
    data = _validate_entry_data(entry)
    sources: dict[str, str] = data[CONF_SOURCES]
    device_id: str | None = data.get(CONF_DEVICE_ID)
    standard: str = data[CONF_STANDARD]

    _LOGGER.debug(
        "Initialize controller %s (standard=%s) for sources: %s",
        entry.entry_id,
        standard,
        ", ".join(f"{key}={value}" for key, value in sources.items()),
    )

    controller = IndoorAirQualityController(
        hass, entry.entry_id, entry.title, sources, device_id, standard=standard
    )
    entry.runtime_data = controller

    async def source_entity_removed() -> None:
        """Leave the configured helper device association unchanged."""

    for source_type, source_entity_id in sources.items():

        def set_source_entity_id(
            new_entity_id: str, *, source_type: str = source_type
        ) -> None:
            updated_sources = {**entry.data[CONF_SOURCES], source_type: new_entity_id}
            hass.config_entries.async_update_entry(
                entry,
                data={**entry.data, CONF_SOURCES: updated_sources},
                unique_id=unique_id_from_sources(updated_sources, standard),
            )
            hass.config_entries.async_schedule_reload(entry.entry_id)

        entry.async_on_unload(
            async_handle_source_entity_changes(
                hass,
                helper_config_entry_id=entry.entry_id,
                set_source_entity_id_or_uuid=set_source_entity_id,
                source_device_id=None,
                source_entity_id_or_uuid=source_entity_id,
                source_entity_removed=source_entity_removed,
            )
        )

    @callback
    def _handle_state_change(event: Event[EventStateChangedData]) -> None:
        """Recalculate the IAQ index and notify subscribed entities."""
        controller.update()
        controller.async_update_listeners()

    entity_ids = entity_ids_from_sources(sources)
    if entity_ids:
        entry.async_on_unload(
            async_track_state_change_event(hass, entity_ids, _handle_state_change)
        )

    # Compute initial state.
    controller.update()

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_reload_entry))
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: IndoorAirQualityConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_reload_entry(
    hass: HomeAssistant, entry: IndoorAirQualityConfigEntry
) -> None:
    """Schedule config entry reload on options/data change."""
    hass.config_entries.async_schedule_reload(entry.entry_id)


__all__ = [
    "IndoorAirQualityConfigEntry",
    "IndoorAirQualityController",
    "async_setup_entry",
    "async_unload_entry",
]
