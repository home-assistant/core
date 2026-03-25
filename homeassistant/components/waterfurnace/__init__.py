"""Support for WaterFurnace geothermal systems."""

from __future__ import annotations

import asyncio
import logging

import voluptuous as vol
from waterfurnace.waterfurnace import WaterFurnace, WFCredentialError, WFException

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv, issue_registry as ir
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN, INTEGRATION_TITLE
from .coordinator import WaterFurnaceCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.SENSOR]

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_USERNAME): cv.string,
                vol.Required(CONF_PASSWORD): cv.string,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)
type WaterFurnaceConfigEntry = ConfigEntry[dict[str, WaterFurnaceCoordinator]]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Import the WaterFurnace configuration from YAML."""
    if DOMAIN not in config:
        return True

    hass.async_create_task(_async_setup(hass, config))

    return True


async def _async_setup(hass: HomeAssistant, config: ConfigType) -> None:
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data=config[DOMAIN],
    )
    if (
        result.get("type") is FlowResultType.ABORT
        and result.get("reason") != "already_configured"
    ):
        ir.async_create_issue(
            hass,
            DOMAIN,
            f"deprecated_yaml_import_issue_{result.get('reason')}",
            breaks_in_ha_version="2026.8.0",
            is_fixable=False,
            issue_domain=DOMAIN,
            severity=ir.IssueSeverity.WARNING,
            translation_key=f"deprecated_yaml_import_issue_{result.get('reason')}",
            translation_placeholders={
                "domain": DOMAIN,
                "integration_title": INTEGRATION_TITLE,
            },
        )
        return

    ir.async_create_issue(
        hass,
        HOMEASSISTANT_DOMAIN,
        "deprecated_yaml",
        breaks_in_ha_version="2026.8.0",
        is_fixable=False,
        issue_domain=DOMAIN,
        severity=ir.IssueSeverity.WARNING,
        translation_key="deprecated_yaml",
        translation_placeholders={
            "domain": DOMAIN,
            "integration_title": INTEGRATION_TITLE,
        },
    )


async def _async_setup_coordinator(
    hass: HomeAssistant,
    username: str,
    password: str,
    device_index: int,
    entry: WaterFurnaceConfigEntry,
) -> tuple[str, WaterFurnaceCoordinator]:
    """Set up a coordinator for a device."""

    device_client = WaterFurnace(username, password, device=device_index)
    await hass.async_add_executor_job(device_client.login)
    coordinator = WaterFurnaceCoordinator(hass, device_client, entry)
    await coordinator.async_config_entry_first_refresh()

    if device_client.gwid is None:
        raise ConfigEntryNotReady(
            f"Invalid GWID for device at index {device_index}: {device_client.gwid}"
        )
    return device_client.gwid, coordinator


async def async_setup_entry(
    hass: HomeAssistant, entry: WaterFurnaceConfigEntry
) -> bool:
    """Set up WaterFurnace from a config entry."""
    username = entry.data[CONF_USERNAME]
    password = entry.data[CONF_PASSWORD]

    client = WaterFurnace(username, password)

    try:
        await hass.async_add_executor_job(client.login)
    except WFCredentialError as err:
        raise ConfigEntryAuthFailed(
            "Authentication failed. Please update your credentials."
        ) from err

    results = await asyncio.gather(
        *[
            _async_setup_coordinator(hass, username, password, index, entry)
            for index in range(len(client.devices) if client.devices else 0)
        ]
    )
    entry.runtime_data = dict(results)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_migrate_entry(
    hass: HomeAssistant, entry: WaterFurnaceConfigEntry
) -> bool:
    """Migrate old entry."""

    if entry.version == 1 and entry.minor_version < 2:
        # Migrate from gwid-based unique_id to account_id-based unique_id
        client = WaterFurnace(entry.data[CONF_USERNAME], entry.data[CONF_PASSWORD])
        try:
            await hass.async_add_executor_job(client.login)
        except WFCredentialError, WFException:
            _LOGGER.error("Failed to login during migration to account_id")
            return False

        if client.account_id is None:
            _LOGGER.error("Account ID is invalid during migration")
            return False

        hass.config_entries.async_update_entry(
            entry, unique_id=str(client.account_id), minor_version=2
        )
        _LOGGER.info("Migrated config entry unique_id to account_id")

    return True
