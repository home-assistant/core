"""Support for (EMEA/EU-based) Honeywell TCC systems.

Such systems provide heating/cooling and DHW and include Evohome, Round Thermostat, and
others.

Note that the API used by this integration's client does not support cooling.
"""

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Final

import evohomeasync as ec1
import evohomeasync2 as ec2
import voluptuous as vol

from homeassistant.const import (
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    CONF_USERNAME,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.discovery import async_load_platform
from homeassistant.helpers.typing import ConfigType

from .const import (
    CONF_LOCATION_IDX,
    DOMAIN,
    EVOHOME_DATA,
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


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Evohome integration."""

    token_manager = TokenManager(
        hass,
        config[DOMAIN][CONF_USERNAME],
        config[DOMAIN][CONF_PASSWORD],
        async_get_clientsession(hass),
    )
    coordinator = EvoDataUpdateCoordinator(
        hass,
        _LOGGER,
        ec2.EvohomeClient(token_manager),
        name=f"{DOMAIN}_coordinator",
        update_interval=config[DOMAIN][CONF_SCAN_INTERVAL],
        location_idx=config[DOMAIN][CONF_LOCATION_IDX],
        client_v1=ec1.EvohomeClient(token_manager),
    )

    await coordinator.async_register_shutdown()
    await coordinator.async_first_refresh()

    if not coordinator.last_update_success:
        _LOGGER.error(f"Failed to fetch initial data: {coordinator.last_exception}")  # noqa: G004
        return False

    assert coordinator.tcs is not None  # mypy

    hass.data[EVOHOME_DATA] = EvoData(
        coordinator=coordinator,
        loc_idx=coordinator.loc_idx,
        tcs=coordinator.tcs,
    )

    hass.async_create_task(
        async_load_platform(hass, Platform.CLIMATE, DOMAIN, {}, config)
    )
    if coordinator.tcs.hotwater:
        hass.async_create_task(
            async_load_platform(hass, Platform.WATER_HEATER, DOMAIN, {}, config)
        )

    setup_service_functions(hass, coordinator)

    return True
