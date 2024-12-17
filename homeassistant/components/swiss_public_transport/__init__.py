"""The swiss_public_transport component."""

import logging

from opendata_transport import OpendataTransport
from opendata_transport.exceptions import (
    OpendataTransportConnectionError,
    OpendataTransportError,
)

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError, ConfigEntryNotReady
from homeassistant.helpers import (
    config_validation as cv,
    device_registry as dr,
    entity_registry as er,
)
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import ConfigType

from .const import (
    CONF_DESTINATION,
    CONF_START,
    CONF_TIME_FIXED,
    CONF_TIME_OFFSET,
    CONF_TIME_STATION,
    CONF_VIA,
    DEFAULT_TIME_STATION,
    DOMAIN,
    PLACEHOLDERS,
)
from .coordinator import (
    SwissPublicTransportConfigEntry,
    SwissPublicTransportDataUpdateCoordinator,
)
from .helper import offset_opendata, unique_id_from_config
from .services import setup_services

_LOGGER = logging.getLogger(__name__)


PLATFORMS: list[Platform] = [Platform.SENSOR]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Swiss public transport component."""
    setup_services(hass)
    return True


async def async_setup_entry(
    hass: HomeAssistant, entry: SwissPublicTransportConfigEntry
) -> bool:
    """Set up Swiss public transport from a config entry."""
    config = entry.data

    start = config[CONF_START]
    destination = config[CONF_DESTINATION]

    time_offset: dict[str, int] | None = config.get(CONF_TIME_OFFSET)

    session = async_get_clientsession(hass)
    opendata = OpendataTransport(
        start,
        destination,
        session,
        via=config.get(CONF_VIA),
        time=config.get(CONF_TIME_FIXED),
        isArrivalTime=config.get(CONF_TIME_STATION, DEFAULT_TIME_STATION) == "arrival",
    )
    if time_offset:
        offset_opendata(opendata, time_offset)

    try:
        await opendata.async_get_data()
    except OpendataTransportConnectionError as e:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="request_timeout",
            translation_placeholders={
                "config_title": entry.title,
                "error": str(e),
            },
        ) from e
    except OpendataTransportError as e:
        raise ConfigEntryError(
            translation_domain=DOMAIN,
            translation_key="invalid_data",
            translation_placeholders={
                **PLACEHOLDERS,
                "config_title": entry.title,
                "error": str(e),
            },
        ) from e

    coordinator = SwissPublicTransportDataUpdateCoordinator(hass, opendata, time_offset)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: SwissPublicTransportConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_migrate_entry(
    hass: HomeAssistant, config_entry: SwissPublicTransportConfigEntry
) -> bool:
    """Migrate config entry."""
    _LOGGER.debug("Migrating from version %s", config_entry.version)

    if config_entry.version > 3:
        # This means the user has downgraded from a future version
        return False

    if config_entry.version == 1 and config_entry.minor_version == 1:
        # Remove wrongly registered devices and entries
        new_unique_id = unique_id_from_config(config_entry.data)
        entity_registry = er.async_get(hass)
        device_registry = dr.async_get(hass)
        device_entries = dr.async_entries_for_config_entry(
            device_registry, config_entry_id=config_entry.entry_id
        )
        for dev in device_entries:
            device_registry.async_update_device(
                dev.id, remove_config_entry_id=config_entry.entry_id
            )

        entity_id = entity_registry.async_get_entity_id(
            Platform.SENSOR, DOMAIN, "None_departure"
        )
        if entity_id:
            entity_registry.async_update_entity(
                entity_id=entity_id,
                new_unique_id=f"{new_unique_id}_departure",
            )
            _LOGGER.debug(
                "Faulty entity with unique_id 'None_departure' migrated to new unique_id '%s'",
                f"{new_unique_id}_departure",
            )

        # Set a valid unique id for config entries
        hass.config_entries.async_update_entry(
            config_entry, unique_id=new_unique_id, minor_version=2
        )

    if config_entry.version < 3:
        # Via stations and time/offset settings now available, which are not backwards compatible if used, changes unique id
        hass.config_entries.async_update_entry(config_entry, version=3, minor_version=1)

    _LOGGER.debug(
        "Migration to version %s.%s successful",
        config_entry.version,
        config_entry.minor_version,
    )

    return True
