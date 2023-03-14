"""Sensor to indicate whether the current day is a workday."""
import logging
from typing import Any

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_COUNTRY, CONF_NAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue
from homeassistant.helpers.typing import ConfigType

from . import util
from .binary_sensor import WorkdayBinarySensor
from .const import (
    ALLOWED_DAYS,
    CONF_ADD_HOLIDAYS,
    CONF_EXCLUDES,
    CONF_OFFSET,
    CONF_PROVINCE,
    CONF_REMOVE_HOLIDAYS,
    CONF_WORKDAYS,
    DEFAULT_EXCLUDES,
    DEFAULT_OFFSET,
    DEFAULT_WORKDAYS,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)
PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Handle Workday setup from YAML."""
    # This used to be under the binary_sensor platform, now it's its own platform
    if "binary_sensor" not in config:
        return True

    for sensor_config in config["binary_sensor"]:
        if sensor_config["platform"] != "workday":
            continue

        workday_data: dict[str, Any] = {
            CONF_NAME: sensor_config["name"],
            CONF_COUNTRY: sensor_config["country"],
            CONF_PROVINCE: sensor_config.get("province", ""),
            CONF_WORKDAYS: sensor_config.get("workdays", DEFAULT_WORKDAYS),
            CONF_EXCLUDES: sensor_config.get("excludes", DEFAULT_EXCLUDES),
            CONF_OFFSET: int(sensor_config.get("days_offset", DEFAULT_OFFSET)),
        }

        for day in workday_data[CONF_WORKDAYS] + workday_data[CONF_EXCLUDES]:
            assert day in ALLOWED_DAYS

        add_holidays = sensor_config.get("add_holidays", [])
        remove_holidays = sensor_config.get("remove_holidays", [])

        workday_data[CONF_ADD_HOLIDAYS] = ",".join(
            sorted([d.strftime("%Y-%m-%d") for d in add_holidays])
        )
        workday_data[CONF_REMOVE_HOLIDAYS] = ",".join(
            sorted([d.strftime("%Y-%m-%d") for d in remove_holidays])
        )

        _LOGGER.debug("Importing Workday config from YAML: %s", workday_data)

        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": SOURCE_IMPORT},
                data=workday_data,
            )
        )

    async_create_issue(
        hass,
        DOMAIN,
        "deprecated_yaml",
        breaks_in_ha_version="2023.5.0",
        is_fixable=False,
        severity=IssueSeverity.WARNING,
        translation_key="deprecated_yaml",
    )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Workday from a config entry."""

    _LOGGER.debug(
        "Setting up a new Workday entry: %s", util.config_entry_to_string(entry)
    )

    hass.data.setdefault(DOMAIN, {})
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    if not entry.update_listeners:
        entry.add_update_listener(update_listener)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.debug("Unloading Workday entry %s", util.config_entry_to_string(entry))
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        _LOGGER.debug("Removing Workday sensor for entry_id=%s", entry.entry_id)
        hass.data[DOMAIN].pop(entry.entry_id)

    _LOGGER.debug("Workday sensor %s unload_ok=%s", entry.entry_id, unload_ok)
    return unload_ok


async def update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    _LOGGER.debug("Updating Workday listener: %s", util.config_entry_to_string(entry))
    sensor: WorkdayBinarySensor | None = hass.data[DOMAIN].get(entry.entry_id, None)
    if sensor is None:
        _LOGGER.warning(
            "Tried to update config for Workday sensor %s (%s) but none found!",
            entry.unique_id,
            entry.entry_id,
        )
        return

    sensor.update_attributes(entry)
    await sensor.async_update()

    await hass.config_entries.async_reload(entry.entry_id)
