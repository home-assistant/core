"""Support for (EMEA/EU-based) Honeywell TCC systems.

Such systems provide heating/cooling and DHW and include Evohome, Round Thermostat, and
others.

Note that the API used by this integration's client does not support cooling.
"""

from dataclasses import dataclass
import logging
from typing import Final

import evohomeasync as ec1
import evohomeasync2 as ec2
import probatio

from homeassistant.const import (
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    CONF_USERNAME,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, issue_registry as ir
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
from .coordinator import EvoAccountCoordinator, EvoLocationCoordinator
from .services import async_setup_services
from .storage import TokenManager

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA: Final = probatio.Schema(
    {
        DOMAIN: probatio.Schema(
            {
                probatio.Required(CONF_USERNAME): cv.string,
                probatio.Required(probatio.Secret(CONF_PASSWORD)): cv.string,
                probatio.Optional(CONF_LOCATION_IDX, default=0): cv.positive_int,
                probatio.Optional(
                    CONF_SCAN_INTERVAL, default=SCAN_INTERVAL_DEFAULT
                ): probatio.All(
                    cv.time_period, probatio.Range(min=SCAN_INTERVAL_MINIMUM)
                ),
            }
        )
    },
    extra=probatio.ALLOW_EXTRA,
)


@dataclass
class EvoData:
    """Dataclass for storing evohome data."""

    account: EvoAccountCoordinator
    coordinator: EvoLocationCoordinator
    loc_idx: int
    tcs: ec2.ControlSystem


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Evohome integration."""

    # Remove any (persistent) repair issues for deprecations that have been completed
    for issue_id in (
        "deprecated_clear_zone_override_service",
        "deprecated_preset_reset",
        "deprecated_reset_system_service",
        "deprecated_set_system_mode_service",
    ):
        ir.async_delete_issue(hass, DOMAIN, issue_id)

    token_manager = TokenManager(
        hass,
        config[DOMAIN][CONF_USERNAME],
        config[DOMAIN][CONF_PASSWORD],
        async_get_clientsession(hass),
    )
    account = EvoAccountCoordinator(
        hass,
        _LOGGER,
        ec2.EvohomeClient(token_manager),
        name=f"{DOMAIN}_account_coordinator",
        update_interval=config[DOMAIN][CONF_SCAN_INTERVAL],
        client_v1=ec1.EvohomeClient(token_manager),
    )
    coordinator = EvoLocationCoordinator(
        hass,
        _LOGGER,
        account,
        name=f"{DOMAIN}_coordinator",
        update_interval=config[DOMAIN][CONF_SCAN_INTERVAL],
        location_idx=config[DOMAIN][CONF_LOCATION_IDX],
    )

    for coord in (account, coordinator):
        await coord.async_register_shutdown()
        await coord.async_first_refresh()

        if not coord.last_update_success:
            _LOGGER.error(f"Failed to fetch initial data: {coord.last_exception}")  # noqa: G004
            return False

    assert coordinator.tcs is not None  # mypy

    hass.data[EVOHOME_DATA] = EvoData(
        account=account,
        coordinator=coordinator,
        loc_idx=coordinator.loc_idx,
        tcs=coordinator.tcs,
    )

    hass.async_create_task(
        async_load_platform(hass, Platform.CLIMATE, DOMAIN, {}, config)
    )
    hass.async_create_task(
        async_load_platform(hass, Platform.BUTTON, DOMAIN, {}, config)
    )
    if coordinator.tcs.hotwater:
        hass.async_create_task(
            async_load_platform(hass, Platform.WATER_HEATER, DOMAIN, {}, config)
        )

    async_setup_services(hass)

    return True
