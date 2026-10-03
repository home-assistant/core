"""Component for integrating entur public transport."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_SHOW_ON_MAP, Platform
from homeassistant.core import HomeAssistant

from .api import (
    EnturApiError,
    async_get_stop_place,
    async_get_stop_routes,
    format_stop_place_title,
    line_id_label,
)
from .const import (
    CONF_PLATFORM_MODE,
    CONF_QUAY_IDS,
    CONF_ROUTE_LABELS,
    CONF_STOP_PLACE_METADATA_VERSION,
    CONF_STOP_PLACE_NAME,
    CONF_STOP_PLACE_TYPES,
    CONF_WHITELIST_LINES,
    PLATFORM_MODE_ALL,
    STOP_PLACE_METADATA_VERSION,
    SUBENTRY_TYPE_STOP_PLACE,
)

PLATFORMS = (Platform.SENSOR,)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Entur from a config entry."""
    await _async_migrate_subentry_display_data(hass, entry)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def _async_migrate_subentry_display_data(
    hass: HomeAssistant, entry: ConfigEntry
) -> None:
    """Add visible route summaries to subentries created by older versions."""
    for subentry in entry.subentries.values():
        if subentry.subentry_type != SUBENTRY_TYPE_STOP_PLACE:
            continue
        if subentry.data.get(CONF_STOP_PLACE_METADATA_VERSION) == (
            STOP_PLACE_METADATA_VERSION
        ):
            continue

        line_ids = list(subentry.data.get(CONF_WHITELIST_LINES, []))
        route_labels = {line_id: line_id_label(line_id) for line_id in line_ids}
        try:
            place = await async_get_stop_place(hass, subentry.data["stop_id"])
        except EnturApiError, KeyError:
            continue

        routes_loaded = not line_ids
        if line_ids:
            try:
                routes = await async_get_stop_routes(hass, subentry.data["stop_id"])
            except EnturApiError:
                routes = ()
            else:
                routes_loaded = True
                route_labels.update(
                    {route.line_id: route.selection_label for route in routes}
                )

        data = dict(subentry.data)
        data[CONF_ROUTE_LABELS] = {
            line_id: route_labels[line_id] for line_id in line_ids
        }
        data.setdefault(
            CONF_STOP_PLACE_TYPES,
            list(place.stop_place_types) if place else [],
        )
        data.setdefault(CONF_PLATFORM_MODE, PLATFORM_MODE_ALL)
        data.setdefault(CONF_QUAY_IDS, [])
        data.setdefault(CONF_SHOW_ON_MAP, False)
        if place:
            data.setdefault(CONF_STOP_PLACE_NAME, place.name)
        if place and routes_loaded:
            data[CONF_STOP_PLACE_METADATA_VERSION] = STOP_PLACE_METADATA_VERSION
        hass.config_entries.async_update_subentry(
            entry,
            subentry,
            title=format_stop_place_title(
                place.name if place else subentry.title,
                place.type_icons if place else "🚏",
                line_ids,
                route_labels,
            ),
            data=data,
        )


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload an Entur config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the integration when a stop subentry changes."""
    await hass.config_entries.async_reload(entry.entry_id)
