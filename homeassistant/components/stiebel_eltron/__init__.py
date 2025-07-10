"""The component for STIEBEL ELTRON heat pumps with ISGWeb Modbus module."""

import logging
from typing import Any

from pymodbus.client import ModbusTcpClient
from pystiebeleltron.pystiebeleltron import StiebelEltronAPI
import voluptuous as vol

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PORT,
    DEVICE_DEFAULT_NAME,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv, issue_registry as ir
from homeassistant.helpers.typing import ConfigType

from .const import CONF_HUB, DEFAULT_HUB, DOMAIN

MODBUS_DOMAIN = "modbus"

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Optional(CONF_NAME, default=DEVICE_DEFAULT_NAME): cv.string,
                vol.Optional(CONF_HUB, default=DEFAULT_HUB): cv.string,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)

_LOGGER = logging.getLogger(__name__)
_PLATFORMS: list[Platform] = [Platform.CLIMATE]


async def _async_import(hass: HomeAssistant, config: ConfigType) -> None:
    """Set up the STIEBEL ELTRON component."""
    hub_config: dict[str, Any] | None = None
    if MODBUS_DOMAIN in config:
        for hub in config[MODBUS_DOMAIN]:
            if hub[CONF_NAME] == config[DOMAIN][CONF_HUB]:
                hub_config = hub
                break
    if hub_config is None:
        ir.async_create_issue(
            hass,
            DOMAIN,
            "deprecated_yaml_import_issue_missing_hub",
            breaks_in_ha_version="2025.11.0",
            is_fixable=False,
            issue_domain=DOMAIN,
            severity=ir.IssueSeverity.WARNING,
            translation_key="deprecated_yaml_import_issue_missing_hub",
            translation_placeholders={
                "domain": DOMAIN,
                "integration_title": "Stiebel Eltron",
            },
        )
        return
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={
            CONF_HOST: hub_config[CONF_HOST],
            CONF_PORT: hub_config[CONF_PORT],
            CONF_NAME: config[DOMAIN][CONF_NAME],
        },
    )
    if (
        result.get("type") is FlowResultType.ABORT
        and result.get("reason") != "already_configured"
    ):
        ir.async_create_issue(
            hass,
            DOMAIN,
            f"deprecated_yaml_import_issue_{result['reason']}",
            breaks_in_ha_version="2025.11.0",
            is_fixable=False,
            issue_domain=DOMAIN,
            severity=ir.IssueSeverity.WARNING,
            translation_key=f"deprecated_yaml_import_issue_{result['reason']}",
            translation_placeholders={
                "domain": DOMAIN,
                "integration_title": "Stiebel Eltron",
            },
        )
        return

    ir.async_create_issue(
        hass,
        DOMAIN,
        "deprecated_yaml",
        breaks_in_ha_version="2025.9.0",
        is_fixable=False,
        issue_domain=DOMAIN,
        severity=ir.IssueSeverity.WARNING,
        translation_key="deprecated_yaml",
        translation_placeholders={
            "domain": DOMAIN,
            "integration_title": "Stiebel Eltron",
        },
    )


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the STIEBEL ELTRON component."""
    if DOMAIN in config:
        hass.async_create_task(_async_import(hass, config))
    return True


type StiebelEltronConfigEntry = ConfigEntry[StiebelEltronAPI]


async def async_setup_entry(
    hass: HomeAssistant, entry: StiebelEltronConfigEntry
) -> bool:
    """Set up STIEBEL ELTRON from a config entry."""
    client = StiebelEltronAPI(
        ModbusTcpClient(entry.data[CONF_HOST], port=entry.data[CONF_PORT]), 1
    )

    success = await hass.async_add_executor_job(client.update)
    if not success:
        raise ConfigEntryNotReady("Could not connect to device")

    entry.runtime_data = client

    await hass.config_entries.async_forward_entry_setups(entry, _PLATFORMS)

    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: StiebelEltronConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, _PLATFORMS)
