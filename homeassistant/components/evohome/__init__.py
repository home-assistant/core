"""Support for (EMEA/EU-based) Honeywell TCC systems.

Such systems provide heating/cooling and DHW and include Evohome, Round Thermostat, and
others.

Note that the API used by this integration's client does not support cooling.
"""

import logging
from typing import Final

import evohomeasync as ec1
import evohomeasync2 as ec2
import probatio

from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import (
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    CONF_USERNAME,
    Platform,
)
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers import config_validation as cv, issue_registry as ir
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.storage import Store
from homeassistant.helpers.typing import ConfigType

from .const import (
    CONF_LOCATION_IDX,
    DOMAIN,
    SCAN_INTERVAL_DEFAULT,
    SCAN_INTERVAL_MINIMUM,
    STORAGE_KEY,
    STORAGE_VER,
)
from .coordinator import (
    EvoAccountCoordinator,
    EvoConfigEntry,
    EvoData,
    EvoLocationCoordinator,
)
from .services import async_setup_services
from .storage import TokenManager

_LOGGER = logging.getLogger(__name__)

PLATFORMS: Final = [Platform.BUTTON, Platform.CLIMATE, Platform.WATER_HEATER]

_YAML_BREAKS_IN_HA_VERSION: Final = "2027.7.0"

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

    async_setup_services(hass)

    if DOMAIN in config:
        hass.async_create_task(_async_import_yaml(hass, config[DOMAIN]))

    return True


async def _async_import_yaml(hass: HomeAssistant, conf: ConfigType) -> None:
    """Import the YAML configuration, and raise the repair issues it needs."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={CONF_USERNAME: conf[CONF_USERNAME], CONF_PASSWORD: conf[CONF_PASSWORD]},
    )

    if result["type"] is FlowResultType.ABORT and result["reason"] not in (
        "already_configured",
        "single_instance_allowed",
    ):
        ir.async_create_issue(
            hass,
            DOMAIN,
            f"deprecated_yaml_import_issue_{result['reason']}",
            breaks_in_ha_version=_YAML_BREAKS_IN_HA_VERSION,
            is_fixable=False,
            issue_domain=DOMAIN,
            severity=ir.IssueSeverity.WARNING,
            translation_key=f"deprecated_yaml_import_issue_{result['reason']}",
        )
        return

    ir.async_create_issue(
        hass,
        HOMEASSISTANT_DOMAIN,
        f"deprecated_yaml_{DOMAIN}",
        breaks_in_ha_version=_YAML_BREAKS_IN_HA_VERSION,
        is_fixable=False,
        issue_domain=DOMAIN,
        severity=ir.IssueSeverity.WARNING,
        translation_key="deprecated_yaml",
        translation_placeholders={
            "domain": DOMAIN,
            "integration_title": "Honeywell Total Connect Comfort (Europe)",
        },
    )

    if (
        conf[CONF_LOCATION_IDX] != 0
        or conf[CONF_SCAN_INTERVAL] != SCAN_INTERVAL_DEFAULT
    ):
        ir.async_create_issue(
            hass,
            DOMAIN,
            "deprecated_yaml_options",
            breaks_in_ha_version=_YAML_BREAKS_IN_HA_VERSION,
            is_fixable=False,
            severity=ir.IssueSeverity.WARNING,
            translation_key="deprecated_yaml_options",
        )


async def async_setup_entry(hass: HomeAssistant, entry: EvoConfigEntry) -> None:
    """Set up evohome from a config entry."""

    token_manager = TokenManager(
        hass,
        entry.data[CONF_USERNAME],
        entry.data[CONF_PASSWORD],
        async_get_clientsession(hass),
    )
    account_coord = EvoAccountCoordinator(
        hass,
        _LOGGER,
        entry,
        ec2.EvohomeClient(token_manager),
        name=f"{DOMAIN}_account_coordinator",
        update_interval=SCAN_INTERVAL_DEFAULT,
        client_v1=ec1.EvohomeClient(token_manager),
    )
    await account_coord.async_config_entry_first_refresh()

    location_coords: list[EvoLocationCoordinator] = []
    for location in account_coord.client.locations:
        if location.tcs is None:
            _LOGGER.debug("Ignoring location %s, as it has no TCS", location.id)
            continue

        location_coord = EvoLocationCoordinator(
            hass,
            _LOGGER,
            entry,
            account_coord,
            location,
            name=f"{DOMAIN}_location_coordinator_{location.id}",
            update_interval=SCAN_INTERVAL_DEFAULT,
        )
        await location_coord.async_config_entry_first_refresh()
        location_coords.append(location_coord)

    if not location_coords:
        raise ConfigEntryError(translation_domain=DOMAIN, translation_key="no_systems")

    entry.runtime_data = EvoData(account=account_coord, locations=location_coords)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)


async def async_unload_entry(hass: HomeAssistant, entry: EvoConfigEntry) -> None:
    """Unload an evohome config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)


async def async_remove_entry(hass: HomeAssistant, entry: EvoConfigEntry) -> None:
    """Remove the cached tokens of a deleted evohome config entry."""
    await Store(hass, STORAGE_VER, STORAGE_KEY).async_remove()
