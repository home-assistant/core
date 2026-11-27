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
from homeassistant.exceptions import HomeAssistantError
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
    locations: list[EvoLocationCoordinator]


async def _async_first_refresh(
    coordinator: EvoAccountCoordinator | EvoLocationCoordinator,
) -> bool:
    """Refresh a coordinator for the first time, and return True if it succeeded."""

    await coordinator.async_register_shutdown()
    await coordinator.async_first_refresh()

    if not coordinator.last_update_success:
        # translations aren't available until setup completes, so log the cause
        err = coordinator.last_exception
        if isinstance(err, HomeAssistantError) and err.translation_key:
            err = err.__cause__ or err
        _LOGGER.error("Failed to fetch initial data: %s", err)
        return False
    return True


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Evohome integration."""

    # Remove any (persistent) repair issues for deprecations that have been completed
    for issue_id in (
        "deprecated_clear_zone_override_service",  # Remove in 2027.5.0
        "deprecated_preset_reset",  # Remove in 2027.5.0
        "deprecated_refresh_system_service",  # Remove in 2027.7.0
        "deprecated_reset_system_service",  # Remove in 2027.5.0
        "deprecated_set_system_mode_service",  # Remove in 2027.5.0
    ):
        ir.async_delete_issue(hass, DOMAIN, issue_id)

    token_manager = TokenManager(
        hass,
        config[DOMAIN][CONF_USERNAME],
        config[DOMAIN][CONF_PASSWORD],
        async_get_clientsession(hass),
    )
    account_coord = EvoAccountCoordinator(
        hass,
        _LOGGER,
        ec2.EvohomeClient(token_manager),
        name=f"{DOMAIN}_account_coordinator",
        update_interval=SCAN_INTERVAL_DEFAULT,  # scan_interval is only for locations
        client_v1=ec1.EvohomeClient(token_manager),
    )
    if not await _async_first_refresh(account_coord):
        return False

    locations = account_coord.client.locations
    loc_idx = config[DOMAIN][CONF_LOCATION_IDX]

    if loc_idx >= len(locations):
        _LOGGER.error(
            "Config error: 'location_idx' = %s, but the valid range is 0-%s. "
            "Unable to continue. Fix any configuration errors and restart HA",
            loc_idx,
            len(locations) - 1,
        )
        return False

    location = locations[loc_idx]
    if location.tcs is None:
        _LOGGER.error("Config error: location %s has no TCS", location.id)
        return False

    location_coord = EvoLocationCoordinator(
        hass,
        _LOGGER,
        account_coord,
        location,
        name=f"{DOMAIN}_location_coordinator_{location.id}",
        update_interval=config[DOMAIN][CONF_SCAN_INTERVAL],
    )
    if not await _async_first_refresh(location_coord):
        return False

    hass.data[EVOHOME_DATA] = EvoData(account=account_coord, locations=[location_coord])

    for platform in (Platform.CLIMATE, Platform.BUTTON, Platform.WATER_HEATER):
        hass.async_create_task(async_load_platform(hass, platform, DOMAIN, {}, config))

    async_setup_services(hass)

    return True
