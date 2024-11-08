"""The volkszaehler component."""

from datetime import timedelta
import logging
import re

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import (
    CONF_FROM,
    CONF_MONITORED_CONDITIONS,
    CONF_SCANINTERVAL,
    CONF_TO,
    CONF_UUID,
    DEFAULT_HOST,
    DEFAULT_MONITORED_CONDITIONS,
    DEFAULT_NAME,
    DEFAULT_PORT,
    DEFAULT_SCANINTERVAL,
    DOMAIN,
)

CONFIG_SCHEMA = cv.platform_only_config_schema(DOMAIN)

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Volkszaehler component from YAML configuration."""
    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {"imported_entries": set()}

    if "sensor" in config:
        for entry in config["sensor"]:
            if entry.get("platform") == DOMAIN:
                uuid = entry.get(CONF_UUID).strip()
                uuid = re.sub(r"[\x00-\x1F]+", "", uuid)
                host = entry.get(CONF_HOST, DEFAULT_HOST)
                port = entry.get(CONF_PORT, DEFAULT_PORT)
                name = entry.get(CONF_NAME, DEFAULT_NAME)
                param_from = entry.get(CONF_FROM, "")
                param_to = entry.get(CONF_TO, "")
                unique_id = f"{name}_{uuid}_{host}:{port}_{param_from}_{param_to}"

                scan_interval = entry.get(CONF_SCANINTERVAL, DEFAULT_SCANINTERVAL)
                uuid = entry.get(CONF_UUID).strip()
                uuid = re.sub(r"[\x00-\x1F]+", "", uuid)

                if isinstance(scan_interval, timedelta):
                    scan_interval = int(scan_interval.seconds)

                existing_entries = hass.config_entries.async_entries(DOMAIN)
                existing_uuids = {e.data.get(CONF_UUID) for e in existing_entries}
                existing_names = {e.data.get(CONF_NAME) for e in existing_entries}

                if uuid in existing_uuids:
                    _LOGGER.warning(
                        "Skipped importing entry with duplicate UUID: %s", uuid
                    )
                    continue

                name = entry.get(CONF_NAME, DEFAULT_NAME)
                if name in existing_names:
                    _LOGGER.warning(
                        "Skipped importing entry with duplicate name: %s", name
                    )
                    continue

                if unique_id not in hass.data[DOMAIN]["imported_entries"]:
                    yaml_config = {
                        CONF_HOST: host,
                        CONF_PORT: port,
                        CONF_NAME: name,
                        CONF_UUID: uuid,
                        CONF_FROM: param_from,
                        CONF_TO: param_to,
                        CONF_SCANINTERVAL: scan_interval,
                        CONF_MONITORED_CONDITIONS: entry.get(
                            CONF_MONITORED_CONDITIONS, [DEFAULT_MONITORED_CONDITIONS]
                        ),
                    }

                    hass.async_create_task(
                        hass.config_entries.flow.async_init(
                            DOMAIN, context={"source": SOURCE_IMPORT}, data=yaml_config
                        )
                    )

                    hass.data[DOMAIN]["imported_entries"].add(unique_id)
                    _LOGGER.info("Imported Volkszaehler entry: %s", unique_id)

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Volkszaehler from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = entry.data

    await _async_setup_platforms(hass, entry)

    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    return True


async def _async_setup_platforms(hass: HomeAssistant, entry: ConfigEntry):
    """Set up platforms for Volkszaehler."""
    await hass.config_entries.async_forward_entry_setups(entry, ["sensor"])


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a Volkszaehler config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, ["sensor"])

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle an options update or reload."""
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)
