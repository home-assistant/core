"""Support for (EMEA/EU-based) Honeywell TCC systems.

Such systems provide heating/cooling and DHW and include Evohome, Round Thermostat, and
others.

Note that the API used by this integration's client does not support cooling.
"""

from dataclasses import dataclass
import logging
from typing import Final

from config_entries import ConfigEntry
import evohomeasync as ec1
import evohomeasync2 as ec2
import voluptuous as vol

from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import CONF_PASSWORD, CONF_SCAN_INTERVAL, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import ConfigType

from .const import (
    CONF_LOCATION_IDX,
    DOMAIN,
    PLATFORMS,
    SCAN_INTERVAL_DEFAULT,
    SCAN_INTERVAL_MINIMUM,
)
from .coordinator import EvoDataUpdateCoordinator
from .services import setup_service_functions
from .storage import TokenManager

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA: Final = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_USERNAME): cv.string,
                vol.Required(CONF_PASSWORD): cv.string,
                vol.Optional(CONF_LOCATION_IDX, default=0): cv.positive_int,
                vol.Optional(
                    CONF_SCAN_INTERVAL, default=SCAN_INTERVAL_DEFAULT
                ): vol.All(cv.time_period, vol.Range(min=SCAN_INTERVAL_MINIMUM)),
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


@dataclass
class EvoData:
    """Dataclass for storing evohome data."""

    coordinator: EvoDataUpdateCoordinator
    loc_idx: int
    tcs: ec2.ControlSystem


type EvohomeConfigEntry = ConfigEntry[EvoData]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Evohome integration."""
    if DOMAIN in config:
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data=config[DOMAIN],
        )
        if result["type"] is FlowResultType.CREATE_ENTRY:
            # issue success
            pass
        else:
            pass
            # issue failure

    return True


async def async_setup_entry(hass: HomeAssistant, entry: EvohomeConfigEntry) -> bool:
    """Set up Evohome from a config entry."""

    token_manager = TokenManager(
        hass,
        entry.data[CONF_USERNAME],
        entry.data[CONF_PASSWORD],
        async_get_clientsession(hass),
    )
    coordinator = EvoDataUpdateCoordinator(
        hass,
        _LOGGER,
        ec2.EvohomeClient(token_manager),
        name=f"{DOMAIN}_coordinator",
        update_interval=SCAN_INTERVAL_DEFAULT,
        location_idx=entry.data[CONF_LOCATION_IDX],
        client_v1=ec1.EvohomeClient(token_manager),
    )

    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = EvoData(
        coordinator=coordinator,
        loc_idx=coordinator.loc_idx,
        tcs=coordinator.tcs,
    )

    setup_service_functions(hass, coordinator)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: EvohomeConfigEntry) -> bool:
    """Unload Evohome config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
