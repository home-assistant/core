"""The swiss_public_transport component."""
import logging

from opendata_transport import OpendataTransport
from opendata_transport.exceptions import (
    OpendataTransportConnectionError,
    OpendataTransportError,
)

from homeassistant import config_entries, core
from homeassistant.const import Platform
from homeassistant.exceptions import ConfigEntryError, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    CONF_ACCESSIBILITY,
    CONF_BIKE,
    CONF_COUCHETTE,
    CONF_DATE,
    CONF_DESTINATION,
    CONF_DIRECT,
    CONF_IS_ARRIVAL,
    CONF_LIMIT,
    CONF_OFFSET,
    CONF_PAGE,
    CONF_SLEEPER,
    CONF_START,
    CONF_TIME,
    CONF_TRANSPORTATIONS,
    CONF_VIA,
    DEFAULT_IS_ARRIVAL,
    DEFAULT_LIMIT,
    DEFAULT_PAGE,
    DOMAIN,
)
from .helper import dict_duration_to_str_duration, offset_opendata

_LOGGER = logging.getLogger(__name__)


PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(
    hass: core.HomeAssistant, entry: config_entries.ConfigEntry
) -> bool:
    """Set up Swiss public transport from a config entry."""
    config = entry.data

    start = config[CONF_START]
    destination = config[CONF_DESTINATION]
    limit = int(config.get(CONF_LIMIT, DEFAULT_LIMIT))
    page = int(config.get(CONF_PAGE, DEFAULT_PAGE))
    date = config.get(CONF_DATE, None)
    time = config.get(CONF_TIME, None)
    offset = (
        dict_duration_to_str_duration(config.get(CONF_OFFSET, None))
        if config.get(CONF_OFFSET, None)
        else None
    )
    is_arrival = config.get(CONF_IS_ARRIVAL, DEFAULT_IS_ARRIVAL)
    transportations = config.get(CONF_TRANSPORTATIONS, None)
    direct = config.get(CONF_DIRECT, None)
    sleeper = config.get(CONF_SLEEPER, None)
    couchette = config.get(CONF_COUCHETTE, None)
    bike = config.get(CONF_BIKE, None)
    accessibility = config.get(CONF_ACCESSIBILITY, None)
    via = config.get(CONF_VIA, None)

    session = async_get_clientsession(hass)
    opendata = OpendataTransport(
        start,
        destination,
        session,
        limit=limit,
        page=page,
        date=date,
        time=time,
        isArrivalTime=is_arrival,
        transportations=transportations,
        direct=direct,
        sleeper=sleeper,
        couchette=couchette,
        bike=bike,
        accessibility=accessibility,
        via=via,
    )

    if offset and not date and not time:
        offset_opendata(opendata, offset)

    try:
        await opendata.async_get_data()
    except OpendataTransportConnectionError as e:
        raise ConfigEntryNotReady(
            f"Timeout while connecting for entry '{start} {destination}'"
        ) from e
    except OpendataTransportError as e:
        _LOGGER.error(
            "Setup failed for entry '%s %s', check at http://transport.opendata.ch/examples/stationboard.html if your station names are valid",
            start,
            destination,
        )
        raise ConfigEntryError(
            f"Setup failed for entry '{start} {destination}' with invalid data"
        ) from e

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = opendata

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(
    hass: core.HomeAssistant, entry: config_entries.ConfigEntry
) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
