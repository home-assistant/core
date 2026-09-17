"""Component for integrating entur public transport."""

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .api import (
    EnturApiError,
    async_get_stop_place,
    format_stop_place_title,
    line_id_label,
)
from .const import (
    CONF_ROUTE_LABELS,
    CONF_STOP_PLACE_TYPES,
    CONF_WHITELIST_LINES,
    DOMAIN,
    SUBENTRY_TYPE_STOP_PLACE,
)

PLATFORMS = (Platform.SENSOR,)
CONFIG_SCHEMA = cv.platform_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Entur integration."""
    if hass.config_entries.async_entries(DOMAIN):
        return True

    for sensor_config in config.get("sensor", []):
        if sensor_config.get("platform") != DOMAIN:
            continue
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": SOURCE_IMPORT},
                data=dict(sensor_config),
            )
        )

    return True


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
        if (
            CONF_ROUTE_LABELS in subentry.data
            and CONF_STOP_PLACE_TYPES in subentry.data
        ):
            continue

        line_ids = list(subentry.data.get(CONF_WHITELIST_LINES, []))
        route_labels = {line_id: line_id_label(line_id) for line_id in line_ids}
        try:
            place = await async_get_stop_place(hass, subentry.data["stop_id"])
        except (EnturApiError, KeyError):
            place = None

        data = dict(subentry.data)
        data.setdefault(CONF_ROUTE_LABELS, route_labels)
        data.setdefault(
            CONF_STOP_PLACE_TYPES,
            list(place.stop_place_types) if place else [],
        )
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
