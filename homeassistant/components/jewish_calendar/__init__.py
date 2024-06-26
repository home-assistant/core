"""The jewish_calendar component."""

from __future__ import annotations

from functools import partial

from hdate import Location
import voluptuous as vol

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import (
    CONF_ELEVATION,
    CONF_LANGUAGE,
    CONF_LATITUDE,
    CONF_LOCATION,
    CONF_LONGITUDE,
    CONF_NAME,
    CONF_TIME_ZONE,
    Platform,
)
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant, callback
import homeassistant.helpers.config_validation as cv
import homeassistant.helpers.entity_registry as er
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue
from homeassistant.helpers.typing import ConfigType

from .binary_sensor import BINARY_SENSORS
from .const import (
    CONF_CANDLE_LIGHT_MINUTES,
    CONF_DIASPORA,
    CONF_HAVDALAH_OFFSET_MINUTES,
    DEFAULT_CANDLE_LIGHT,
    DEFAULT_DIASPORA,
    DEFAULT_HAVDALAH_OFFSET_MINUTES,
    DEFAULT_LANGUAGE,
    DEFAULT_NAME,
    DOMAIN,
)
from .sensor import INFO_SENSORS, TIME_SENSORS

PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR, Platform.SENSOR]

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.All(
            cv.deprecated(DOMAIN),
            {
                vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
                vol.Optional(CONF_DIASPORA, default=DEFAULT_DIASPORA): cv.boolean,
                vol.Inclusive(CONF_LATITUDE, "coordinates"): cv.latitude,
                vol.Inclusive(CONF_LONGITUDE, "coordinates"): cv.longitude,
                vol.Optional(CONF_LANGUAGE, default=DEFAULT_LANGUAGE): vol.In(
                    ["hebrew", "english"]
                ),
                vol.Optional(
                    CONF_CANDLE_LIGHT_MINUTES, default=DEFAULT_CANDLE_LIGHT
                ): int,
                # Default of 0 means use 8.5 degrees / 'three_stars' time.
                vol.Optional(
                    CONF_HAVDALAH_OFFSET_MINUTES,
                    default=DEFAULT_HAVDALAH_OFFSET_MINUTES,
                ): int,
            },
        )
    },
    extra=vol.ALLOW_EXTRA,
)


def get_unique_prefix(
    location: Location,
    language: str,
    candle_lighting_offset: int | None,
    havdalah_offset: int | None,
) -> str:
    """Create a prefix for unique ids."""
    # location.altitude was unset before 2024.6 when this method
    # was used to create the unique id. As such it would always
    # use the default altitude of 754.
    config_properties = [
        location.latitude,
        location.longitude,
        location.timezone,
        754,
        location.diaspora,
        language,
        candle_lighting_offset,
        havdalah_offset,
    ]
    prefix = "_".join(map(str, config_properties))
    return f"{prefix}"


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Jewish Calendar component."""
    if DOMAIN not in config:
        return True

    async_create_issue(
        hass,
        HOMEASSISTANT_DOMAIN,
        f"deprecated_yaml_{DOMAIN}",
        is_fixable=False,
        issue_domain=DOMAIN,
        breaks_in_ha_version="2024.12.0",
        severity=IssueSeverity.WARNING,
        translation_key="deprecated_yaml",
        translation_placeholders={
            "domain": DOMAIN,
            "integration_title": DEFAULT_NAME,
        },
    )

    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_IMPORT}, data=config[DOMAIN]
        )
    )

    return True


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Set up a configuration entry for Jewish calendar."""
    language = config_entry.data.get(CONF_LANGUAGE, DEFAULT_LANGUAGE)
    diaspora = config_entry.data.get(CONF_DIASPORA, DEFAULT_DIASPORA)
    candle_lighting_offset = config_entry.options.get(
        CONF_CANDLE_LIGHT_MINUTES, DEFAULT_CANDLE_LIGHT
    )
    havdalah_offset = config_entry.options.get(
        CONF_HAVDALAH_OFFSET_MINUTES, DEFAULT_HAVDALAH_OFFSET_MINUTES
    )

    location = await hass.async_add_executor_job(
        partial(
            Location,
            name=hass.config.location_name,
            diaspora=diaspora,
            latitude=config_entry.data.get(CONF_LATITUDE, hass.config.latitude),
            longitude=config_entry.data.get(CONF_LONGITUDE, hass.config.longitude),
            altitude=config_entry.data.get(CONF_ELEVATION, hass.config.elevation),
            timezone=config_entry.data.get(CONF_TIME_ZONE, hass.config.time_zone),
        )
    )

    hass.data.setdefault(DOMAIN, {})[config_entry.entry_id] = {
        CONF_LANGUAGE: language,
        CONF_DIASPORA: diaspora,
        CONF_LOCATION: location,
        CONF_CANDLE_LIGHT_MINUTES: candle_lighting_offset,
        CONF_HAVDALAH_OFFSET_MINUTES: havdalah_offset,
    }

    # Update unique ID to be unrelated to user defined options
    old_prefix = get_unique_prefix(
        location, language, candle_lighting_offset, havdalah_offset
    )

    ent_reg = er.async_get(hass)
    entries = er.async_entries_for_config_entry(ent_reg, config_entry.entry_id)
    if not entries or any(entry.unique_id.startswith(old_prefix) for entry in entries):
        async_update_unique_ids(ent_reg, config_entry.entry_id, old_prefix)

    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)

    async def update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
        # Trigger update of states for all platforms
        await hass.config_entries.async_reload(config_entry.entry_id)

    config_entry.async_on_unload(config_entry.add_update_listener(update_listener))
    return True


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(
        config_entry, PLATFORMS
    )

    if unload_ok:
        hass.data[DOMAIN].pop(config_entry.entry_id)

    return unload_ok


@callback
def async_update_unique_ids(
    ent_reg: er.EntityRegistry, new_prefix: str, old_prefix: str
) -> None:
    """Update unique ID to be unrelated to user defined options.

    Introduced with release 2024.6
    """
    platform_descriptions = {
        Platform.BINARY_SENSOR: BINARY_SENSORS,
        Platform.SENSOR: (*INFO_SENSORS, *TIME_SENSORS),
    }
    for platform, descriptions in platform_descriptions.items():
        for description in descriptions:
            new_unique_id = f"{new_prefix}-{description.key}"
            old_unique_id = f"{old_prefix}_{description.key}"
            if entity_id := ent_reg.async_get_entity_id(
                platform, DOMAIN, old_unique_id
            ):
                ent_reg.async_update_entity(entity_id, new_unique_id=new_unique_id)
