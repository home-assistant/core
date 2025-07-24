"""Support for (EMEA/EU-based) Honeywell TCC systems.

Such systems provide heating/cooling and DHW and include Evohome, Round Thermostat, and
others.

Note that the API used by this integration's client does not support cooling.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
import logging
from typing import Final

import evohomeasync as ec1
import evohomeasync2 as ec2
from evohomeasync2.const import SZ_CAN_BE_TEMPORARY, SZ_SYSTEM_MODE, SZ_TIMING_MODE
from evohomeasync2.schemas.const import (
    S2_DURATION as SZ_DURATION,
    S2_PERIOD as SZ_PERIOD,
    SystemMode as EvoSystemMode,
)
import voluptuous as vol

from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_MODE,
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    CONF_USERNAME,
    Platform,
)
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.helpers import config_validation as cv, entity_registry as er
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.discovery import async_load_platform
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.service import verify_domain_control
from homeassistant.helpers.typing import ConfigType
from homeassistant.util.hass_dict import HassKey

from .const import (
    ATTR_DURATION,
    ATTR_DURATION_UNTIL,
    ATTR_PERIOD,
    ATTR_SETPOINT,
    CONF_LOCATION_IDX,
    DOMAIN,
    SCAN_INTERVAL_DEFAULT,
    SCAN_INTERVAL_MINIMUM,
    EvoService,
)
from .coordinator import EvoDataUpdateCoordinator
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

# system mode schemas are built dynamically when the services are registered
# because supported modes can vary for edge-case systems

RESET_ZONE_OVERRIDE_SCHEMA: Final = vol.Schema(
    {vol.Required(ATTR_ENTITY_ID): cv.entity_id}
)
SET_ZONE_OVERRIDE_SCHEMA: Final = vol.Schema(
    {
        vol.Required(ATTR_ENTITY_ID): cv.entity_id,
        vol.Required(ATTR_SETPOINT): vol.All(
            vol.Coerce(float), vol.Range(min=4.0, max=35.0)
        ),
        vol.Optional(ATTR_DURATION_UNTIL): vol.All(
            cv.time_period, vol.Range(min=timedelta(days=0), max=timedelta(days=1))
        ),
    }
)

EVOHOME_KEY: HassKey[EvoData] = HassKey(DOMAIN)


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

    hass.data[EVOHOME_KEY] = EvoData(
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


@callback
def setup_service_functions(
    hass: HomeAssistant, coordinator: EvoDataUpdateCoordinator
) -> None:
    """Set up the service handlers for the system/zone operating modes.

    Not all Honeywell TCC-compatible systems support all operating modes. In addition,
    each mode will require any of four distinct service schemas. This has to be
    enumerated before registering the appropriate handlers.

    It appears that all TCC-compatible systems support the same three zones modes.
    """

    @verify_domain_control(hass, DOMAIN)
    async def force_refresh(call: ServiceCall) -> None:
        """Obtain the latest state data via the vendor's RESTful API."""
        await coordinator.async_refresh()

    @verify_domain_control(hass, DOMAIN)
    async def set_system_mode(call: ServiceCall) -> None:
        """Set the system mode."""
        assert coordinator.tcs is not None  # mypy

        payload = {
            "unique_id": coordinator.tcs.id,
            "service": call.service,
            "data": call.data,
        }
        async_dispatcher_send(hass, DOMAIN, payload)

    @verify_domain_control(hass, DOMAIN)
    async def set_zone_override(call: ServiceCall) -> None:
        """Set the zone override (setpoint)."""
        entity_id = call.data[ATTR_ENTITY_ID]

        registry = er.async_get(hass)
        registry_entry = registry.async_get(entity_id)

        if registry_entry is None or registry_entry.platform != DOMAIN:
            raise ValueError(f"'{entity_id}' is not a known {DOMAIN} entity")

        if registry_entry.domain != "climate":
            raise ValueError(f"'{entity_id}' is not an {DOMAIN} controller/zone")

        payload = {
            "unique_id": registry_entry.unique_id,
            "service": call.service,
            "data": call.data,
        }

        async_dispatcher_send(hass, DOMAIN, payload)

    assert coordinator.tcs is not None  # mypy

    hass.services.async_register(DOMAIN, EvoService.REFRESH_SYSTEM, force_refresh)

    # Enumerate which operating modes are supported by this system
    modes = list(coordinator.tcs.allowed_system_modes)

    # Not all systems support "AutoWithReset": register this handler only if required
    if any(
        m[SZ_SYSTEM_MODE]
        for m in modes
        if m[SZ_SYSTEM_MODE] == EvoSystemMode.AUTO_WITH_RESET
    ):
        hass.services.async_register(DOMAIN, EvoService.RESET_SYSTEM, set_system_mode)

    system_mode_schemas = []
    modes = [m for m in modes if m[SZ_SYSTEM_MODE] != EvoSystemMode.AUTO_WITH_RESET]

    # Permanent-only modes will use this schema
    perm_modes = [m[SZ_SYSTEM_MODE] for m in modes if not m[SZ_CAN_BE_TEMPORARY]]
    if perm_modes:  # any of: "Auto", "HeatingOff": permanent only
        schema = vol.Schema({vol.Required(ATTR_MODE): vol.In(perm_modes)})
        system_mode_schemas.append(schema)

    modes = [m for m in modes if m[SZ_CAN_BE_TEMPORARY]]

    # These modes are set for a number of hours (or indefinitely): use this schema
    temp_modes = [m[SZ_SYSTEM_MODE] for m in modes if m[SZ_TIMING_MODE] == SZ_DURATION]
    if temp_modes:  # any of: "AutoWithEco", permanent or for 0-24 hours
        schema = vol.Schema(
            {
                vol.Required(ATTR_MODE): vol.In(temp_modes),
                vol.Optional(ATTR_DURATION): vol.All(
                    cv.time_period,
                    vol.Range(min=timedelta(hours=0), max=timedelta(hours=24)),
                ),
            }
        )
        system_mode_schemas.append(schema)

    # These modes are set for a number of days (or indefinitely): use this schema
    temp_modes = [m[SZ_SYSTEM_MODE] for m in modes if m[SZ_TIMING_MODE] == SZ_PERIOD]
    if temp_modes:  # any of: "Away", "Custom", "DayOff", permanent or for 1-99 days
        schema = vol.Schema(
            {
                vol.Required(ATTR_MODE): vol.In(temp_modes),
                vol.Optional(ATTR_PERIOD): vol.All(
                    cv.time_period,
                    vol.Range(min=timedelta(days=1), max=timedelta(days=99)),
                ),
            }
        )
        system_mode_schemas.append(schema)

    if system_mode_schemas:
        hass.services.async_register(
            DOMAIN,
            EvoService.SET_SYSTEM_MODE,
            set_system_mode,
            schema=vol.Schema(vol.Any(*system_mode_schemas)),
        )

    # The zone modes are consistent across all systems and use the same schema
    hass.services.async_register(
        DOMAIN,
        EvoService.RESET_ZONE_OVERRIDE,
        set_zone_override,
        schema=RESET_ZONE_OVERRIDE_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        EvoService.SET_ZONE_OVERRIDE,
        set_zone_override,
        schema=SET_ZONE_OVERRIDE_SCHEMA,
    )
