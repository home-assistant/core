"""Advantage Air climate integration."""

from datetime import timedelta
import logging

from advantage_air import ApiError, advantage_air

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_IP_ADDRESS, CONF_PORT, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import ADVANTAGE_AIR_RETRY, DOMAIN
from .models import AdvantageAirData
from .services import async_setup_services

type AdvantageAirDataConfigEntry = ConfigEntry[AdvantageAirData]

ADVANTAGE_AIR_SYNC_INTERVAL = 15
PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.CLIMATE,
    Platform.COVER,
    Platform.LIGHT,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.UPDATE,
]

_LOGGER = logging.getLogger(__name__)
REQUEST_REFRESH_DELAY = 0.5

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the component."""
    async_setup_services(hass)
    return True


async def async_setup_entry(
    hass: HomeAssistant, entry: AdvantageAirDataConfigEntry
) -> bool:
    """Set up Advantage Air config."""
    ip_address = entry.data[CONF_IP_ADDRESS]
    port = entry.data[CONF_PORT]
    api = advantage_air(
        ip_address,
        port=port,
        session=async_get_clientsession(hass),
        retry=ADVANTAGE_AIR_RETRY,
    )

    async def async_get():
        try:
            return await api.async_get()
        except ApiError as err:
            raise UpdateFailed(err) from err

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        config_entry=entry,
        name="Advantage Air",
        update_method=async_get,
        update_interval=timedelta(seconds=ADVANTAGE_AIR_SYNC_INTERVAL),
        request_refresh_debouncer=Debouncer(
            hass, _LOGGER, cooldown=REQUEST_REFRESH_DELAY, immediate=False
        ),
    )

    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = AdvantageAirData(coordinator, api)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: AdvantageAirDataConfigEntry
) -> bool:
    """Unload Advantage Air Config."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
