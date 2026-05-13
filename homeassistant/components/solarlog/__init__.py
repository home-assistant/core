"""Solar-Log integration."""

import logging
from urllib.parse import ParseResult, urlparse

from aiohttp import CookieJar
from solarlog_cli.solarlog_connector import SolarLogConnector

from homeassistant.const import CONF_HOST, CONF_TIMEOUT, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.aiohttp_client import async_create_clientsession

from .const import CONF_HAS_PWD
from .coordinator import (
    SolarLogBasicDataCoordinator,
    SolarlogConfigEntry,
    SolarLogDeviceDataCoordinator,
    SolarLogLongtimeDataCoordinator,
)
from .models import SolarlogIntegrationData

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: SolarlogConfigEntry) -> bool:
    """Set up a config entry for solarlog."""

    host_entry = entry.data[CONF_HOST]
    password = entry.data.get("password", "")

    url = urlparse(host_entry, "http")
    netloc = url.netloc or url.path
    path = url.path if url.netloc else ""
    url = ParseResult("http", netloc, path, *url[3:])

    solarlog = SolarLogConnector(
        url.geturl(),
        tz=hass.config.time_zone,
        password=password,
        session=async_create_clientsession(
            hass, cookie_jar=CookieJar(quote_cookie=False)
        ),
    )

    basic_coordinator = SolarLogBasicDataCoordinator(hass, entry, solarlog)

    solarLogData = SolarlogIntegrationData(
        api=solarlog,
        basic_data_coordinator=basic_coordinator,
    )

    await basic_coordinator.async_config_entry_first_refresh()

    entry.runtime_data = solarLogData

    if basic_coordinator.solarlog.extended_data:
        timeout = entry.data.get(CONF_TIMEOUT, 0)
        if timeout <= 150:
            # Increase timeout for next try, skip setup of LongtimeDataCoordinator,
            # if timeout was not the issue (assumed when timeout > 150)
            timeout = timeout + 30
            new = {**entry.data}
            new[CONF_TIMEOUT] = timeout
            hass.config_entries.async_update_entry(entry, data=new)

            entry.runtime_data.longtime_data_coordinator = (
                SolarLogLongtimeDataCoordinator(hass, entry, solarlog, timeout)
            )
            await entry.runtime_data.longtime_data_coordinator.async_config_entry_first_refresh()

        entry.runtime_data.device_data_coordinator = SolarLogDeviceDataCoordinator(
            hass, entry, solarlog
        )
        await entry.runtime_data.device_data_coordinator.async_config_entry_first_refresh()

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: SolarlogConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_migrate_entry(
    hass: HomeAssistant, config_entry: SolarlogConfigEntry
) -> bool:
    """Migrate old entry."""
    _LOGGER.debug("Migrating from version %s", config_entry.version)

    if config_entry.version > 1:
        # This means the user has downgraded from a future version
        return False

    if config_entry.version == 1:
        if config_entry.minor_version < 2:
            # migrate old entity unique id
            entity_reg = er.async_get(hass)
            entities: list[er.RegistryEntry] = er.async_entries_for_config_entry(
                entity_reg, config_entry.entry_id
            )

            for entity in entities:
                if "time" in entity.unique_id:
                    new_uid = entity.unique_id.replace("time", "last_updated")
                    _LOGGER.debug(
                        "migrate unique id '%s' to '%s'", entity.unique_id, new_uid
                    )
                    entity_reg.async_update_entity(
                        entity.entity_id, new_unique_id=new_uid
                    )

        if config_entry.minor_version < 3:
            # migrate config_entry
            new = {**config_entry.data}
            new[CONF_HAS_PWD] = False

            hass.config_entries.async_update_entry(
                config_entry, data=new, minor_version=3, version=1
            )

    _LOGGER.debug(
        "Migration to version %s.%s successful",
        config_entry.version,
        config_entry.minor_version,
    )

    return True
