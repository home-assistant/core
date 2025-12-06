"""The component for STIEBEL ELTRON heat pumps with ISGWeb Modbus module."""

import logging
from typing import Any

from pystiebeleltron import StiebelEltronModbusError, get_controller_model
import voluptuous as vol

from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PORT,
    DEVICE_DEFAULT_NAME,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers import config_validation as cv, issue_registry as ir
from homeassistant.helpers.typing import ConfigType

from .const import CONF_HUB, DEFAULT_HUB, DOMAIN
from .coordinator import StiebelEltronConfigEntry, StiebelEltronDataCoordinator

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
        "reason" in result
        and result.get("type") is FlowResultType.ABORT
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
        breaks_in_ha_version="2025.11.0",
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


async def async_setup_entry(
    hass: HomeAssistant, entry: StiebelEltronConfigEntry
) -> bool:
    """Set up STIEBEL ELTRON from a config entry."""

    host = str(entry.data.get(CONF_HOST))
    port_data = entry.data.get(CONF_PORT)
    port = int(port_data) if port_data is not None else 502

    try:
        model = await get_controller_model(host, port)
    except StiebelEltronModbusError as exception:
        raise ConfigEntryError(exception) from exception

    coordinator = StiebelEltronDataCoordinator(hass, entry, model, host, port)

    entry.runtime_data = coordinator
    await coordinator.async_config_entry_first_refresh()

    await hass.config_entries.async_forward_entry_setups(entry, _PLATFORMS)
    return True


async def async_unload_entry(
    hass: HomeAssistant,
    entry: StiebelEltronConfigEntry,
) -> bool:
    """Unload a config entry."""
    coordinator = entry.runtime_data
    await coordinator.close()
    return await hass.config_entries.async_unload_platforms(entry, _PLATFORMS)
