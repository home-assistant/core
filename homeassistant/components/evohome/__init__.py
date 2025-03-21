"""Support for (EMEA/EU-based) Honeywell TCC systems.

Such systems provide heating/cooling and DHW and include Evohome, Round Thermostat, and
others.

Note that the API used by this integration's client does not support cooling.
"""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Final

from evohomeasync2.const import SZ_CAN_BE_TEMPORARY, SZ_SYSTEM_MODE, SZ_TIMING_MODE
from evohomeasync2.schemas.const import (
    S2_DURATION as SZ_DURATION,
    S2_PERIOD as SZ_PERIOD,
    SystemMode as EvoSystemMode,
)
import voluptuous as vol

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import (
    ATTR_MODE,
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    CONF_USERNAME,
    Platform,
)
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.service import verify_domain_control
from homeassistant.helpers.typing import ConfigType

from .const import (
    ATTR_DURATION,
    ATTR_PERIOD,
    CONF_LOCATION_IDX,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MINIMUM_SCAN_INTERVAL_LEGACY,
    EvoService,
)
from .coordinator import EvoDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA: Final = vol.Schema(  # scan_interval here is a timedelta
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_USERNAME): cv.string,
                vol.Required(CONF_PASSWORD): cv.string,
                vol.Optional(CONF_LOCATION_IDX, default=0): cv.positive_int,
                vol.Optional(
                    CONF_SCAN_INTERVAL, default=timedelta(seconds=DEFAULT_SCAN_INTERVAL)
                ): vol.All(
                    cv.time_period,
                    vol.Range(min=timedelta(seconds=MINIMUM_SCAN_INTERVAL_LEGACY)),
                ),
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)

PLATFORMS = (Platform.CLIMATE, Platform.WATER_HEATER)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Create evohome config entry from YAML."""

    if not hass.config_entries.async_entries(DOMAIN) and DOMAIN in config:
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN, context={"source": SOURCE_IMPORT}, data=config[DOMAIN]
            )
        )

    return True


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Load the Evohome config entry."""

    coordinator = EvoDataUpdateCoordinator(
        hass, _LOGGER, config_entry=config_entry, name=f"{DOMAIN}_coordinator"
    )

    await coordinator.async_first_refresh()

    if not coordinator.last_update_success:
        _LOGGER.error(f"Failed to fetch initial data: {coordinator.last_exception}")  # noqa: G004
        return False

    config_entry.runtime_data = {"coordinator": coordinator}

    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)

    _register_domain_services(hass)

    return True


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Unload the Evohome config entry."""

    return await hass.config_entries.async_unload_platforms(config_entry, PLATFORMS)


@callback
def _register_domain_services(hass: HomeAssistant) -> None:
    """Set up the service handlers for the system/zone operating modes.

    Not all Honeywell TCC-compatible systems support all operating modes. In addition,
    each mode will require any of four distinct service schemas. This has to be
    enumerated before registering the appropriate handlers.

    It appears that all TCC-compatible systems support the same three zones modes.
    """

    # _register_domain_services() is safe only whilst "single_config_entry" is true

    def get_coordinator() -> EvoDataUpdateCoordinator:
        config_entry = hass.config_entries.async_entries(DOMAIN)[0]
        result: EvoDataUpdateCoordinator = config_entry.runtime_data["coordinator"]
        return result

    coordinator = get_coordinator()

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

    assert coordinator.tcs is not None  # mypy

    hass.services.async_register(DOMAIN, EvoService.REFRESH_SYSTEM, force_refresh)

    # Enumerate which operating modes are supported by this system
    modes = list(coordinator.tcs.allowed_system_modes)

    # Not all systems support "AutoWithReset": register this handler only if required
    if EvoSystemMode.AUTO_WITH_RESET in coordinator.tcs.modes:
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
