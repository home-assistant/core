"""Support for Hydrawise cloud."""

from pydrawise import auth, client

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import issue_registry as ir

from .const import APP_ID, CONF_ADVANCED_SENSORS, DOMAIN, LOGGER
from .coordinator import (
    HydrawiseMainDataUpdateCoordinator,
    HydrawiseUpdateCoordinators,
    HydrawiseWaterUseDataUpdateCoordinator,
)

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.VALVE,
]


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Set up Hydrawise from a config entry."""
    if CONF_USERNAME not in config_entry.data or CONF_PASSWORD not in config_entry.data:
        # The GraphQL API requires username and password to authenticate. If either is
        # missing, reauth is required.
        raise ConfigEntryAuthFailed

    hydrawise = client.Hydrawise(
        auth.Auth(
            config_entry.data[CONF_USERNAME],
            config_entry.data[CONF_PASSWORD],
        ),
        app_id=APP_ID,
    )

    main_coordinator = HydrawiseMainDataUpdateCoordinator(hass, hydrawise)
    await main_coordinator.async_config_entry_first_refresh()

    water_use_coordinator = HydrawiseWaterUseDataUpdateCoordinator(
        hass,
        hydrawise,
        main_coordinator,
        enabled=config_entry.options.get(CONF_ADVANCED_SENSORS, False),
    )
    if water_use_coordinator.enabled:
        await water_use_coordinator.async_config_entry_first_refresh()
    hass.data.setdefault(DOMAIN, {})[config_entry.entry_id] = (
        HydrawiseUpdateCoordinators(
            main=main_coordinator,
            water_use=water_use_coordinator,
        )
    )
    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)
    config_entry.async_on_unload(config_entry.add_update_listener(async_update_options))
    return True


async def async_update_options(hass: HomeAssistant, config_entry: ConfigEntry) -> None:
    """Handle an options update."""
    await hass.config_entries.async_reload(config_entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok


async def async_migrate_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Migrate old entry."""
    LOGGER.debug(
        "Migrating configuration from version %s.%s",
        config_entry.version,
        config_entry.minor_version,
    )

    if config_entry.version == 1:
        if config_entry.minor_version < 2:
            ir.async_create_issue(
                hass,
                DOMAIN,
                "hydrawise_advanced_sensors_disabled",
                breaks_in_ha_version="2025.2.0",
                is_fixable=False,
                learn_more_url="https://github.com/home-assistant/core/issues/130857#issuecomment-2600919282",
                severity=ir.IssueSeverity.ERROR,
                translation_key="advanced_sensors_disabled",
            )

    LOGGER.debug(
        "Migration to configuration version %s.%s successful",
        config_entry.version,
        config_entry.minor_version,
    )
    return True
