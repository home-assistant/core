"""Platform for Roth Touchline floor heating controller."""

from __future__ import annotations

from pytouchline_extended import PyTouchline

from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue
from homeassistant.helpers.typing import ConfigType

from .const import _LOGGER, DOMAIN

PLATFORMS = [Platform.CLIMATE]


async def _async_import(hass: HomeAssistant, base_config: ConfigType) -> None:
    """Import a config entry from configuration.yaml."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_IMPORT},
        data=base_config[DOMAIN],
    )
    if (
        result["type"] == FlowResultType.CREATE_ENTRY
        or result["reason"] == "single_instance_allowed"
    ):
        async_create_issue(
            hass,
            HOMEASSISTANT_DOMAIN,
            f"deprecated_yaml_{DOMAIN}",
            breaks_in_ha_version="2024.10.0",
            is_fixable=False,
            issue_domain=DOMAIN,
            severity=IssueSeverity.WARNING,
            translation_key="deprecated_yaml",
            translation_placeholders={
                "domain": DOMAIN,
                "integration_title": "Touchline",
            },
        )
        return
    async_create_issue(
        hass,
        DOMAIN,
        f"deprecated_yaml_import_issue_{result['reason']}",
        breaks_in_ha_version="2024.10.0",
        is_fixable=False,
        issue_domain=DOMAIN,
        severity=IssueSeverity.WARNING,
        translation_key=f"deprecated_yaml_import_issue_{result['reason']}",
        translation_placeholders={
            "domain": DOMAIN,
            "integration_title": "Touchline",
        },
    )


async def async_setup(hass: HomeAssistant, base_config: ConfigType) -> bool:
    """Set up the Touchline component."""
    if DOMAIN in base_config:
        hass.async_create_task(_async_import(hass, base_config))
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Roth Touchline from a config entry."""

    host = entry.data[CONF_HOST]
    _LOGGER.debug(
        "Host: %s",
        host,
    )

    py_touchline = PyTouchline(url=host)
    number_of_devices = int(
        await hass.async_add_executor_job(py_touchline.get_number_of_devices)
    )

    _LOGGER.debug(
        "Host: %s, Number of devices found: %s",
        host,
        number_of_devices,
    )

    if not number_of_devices:
        raise ConfigEntryNotReady
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = py_touchline
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    return True


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
