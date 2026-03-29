"""Support for OPNsense Routers."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any, cast

from pyopnsense import diagnostics
from pyopnsense.exceptions import APIException
import voluptuous as vol

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_API_KEY, CONF_URL, CONF_VERIFY_SSL, Platform
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import (
    config_validation as cv,
    discovery,
    issue_registry as ir,
)
from homeassistant.helpers.typing import ConfigType

from .const import (
    CONF_API_SECRET,
    CONF_INTERFACE_CLIENT,
    CONF_TRACKER_INTERFACES,
    DOMAIN,
    INTEGRATION_TITLE,
    OPNSENSE_DATA,
)

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_URL): cv.url,
                vol.Required(CONF_API_KEY): cv.string,
                vol.Required(CONF_API_SECRET): cv.string,
                vol.Optional(CONF_VERIFY_SSL, default=False): cv.boolean,
                vol.Optional(CONF_TRACKER_INTERFACES, default=[]): vol.All(
                    cv.ensure_list, [cv.string]
                ),
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


def _entry_storage(hass: HomeAssistant) -> dict[str, dict[str, Any]]:
    """Return integration storage mapping keyed by config entry id."""
    return cast(dict[str, dict[str, Any]], hass.data.setdefault(OPNSENSE_DATA, {}))


async def _async_import_from_yaml(
    hass: HomeAssistant, yaml_config: Mapping[str, Any]
) -> None:
    """Import YAML config into a config entry and raise a deprecation issue."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={
            CONF_URL: yaml_config[CONF_URL],
            CONF_API_KEY: yaml_config[CONF_API_KEY],
            CONF_API_SECRET: yaml_config[CONF_API_SECRET],
            CONF_VERIFY_SSL: yaml_config.get(CONF_VERIFY_SSL, False),
            CONF_TRACKER_INTERFACES: list(yaml_config.get(CONF_TRACKER_INTERFACES, [])),
        },
    )

    if (
        result.get("type") == FlowResultType.ABORT
        and result.get("reason") != "already_configured"
    ):
        _LOGGER.warning("Failed to import OPNsense YAML config: %s", result)
        return

    ir.async_create_issue(
        hass,
        HOMEASSISTANT_DOMAIN,
        f"deprecated_yaml_{DOMAIN}",
        breaks_in_ha_version="2027.1.0",
        is_fixable=False,
        issue_domain=DOMAIN,
        severity=ir.IssueSeverity.WARNING,
        translation_key="deprecated_yaml",
        translation_placeholders={
            "domain": DOMAIN,
            "integration_title": INTEGRATION_TITLE,
        },
    )


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the OPNsense integration."""
    if DOMAIN in config:
        hass.async_create_task(_async_import_from_yaml(hass, config[DOMAIN]))
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up OPNsense from a config entry."""
    data = entry.data

    url = data[CONF_URL]
    api_key = data[CONF_API_KEY]
    api_secret = data[CONF_API_SECRET]
    verify_ssl = data[CONF_VERIFY_SSL]
    tracker_interfaces = data.get(CONF_TRACKER_INTERFACES, [])

    interfaces_client = diagnostics.InterfaceClient(
        api_key, api_secret, url, verify_ssl, timeout=20
    )

    try:
        await hass.async_add_executor_job(interfaces_client.get_arp)
    except APIException as err:
        raise ConfigEntryNotReady(
            "Failure while connecting to OPNsense API endpoint"
        ) from err

    if tracker_interfaces:
        netinsight_client = diagnostics.NetworkInsightClient(
            api_key, api_secret, url, verify_ssl, timeout=20
        )

        try:
            interfaces = await hass.async_add_executor_job(
                lambda: list(netinsight_client.get_interfaces().values())
            )
        except APIException as err:
            raise ConfigEntryNotReady(
                "Failure while validating OPNsense tracker interfaces"
            ) from err

        for interface in tracker_interfaces:
            if interface not in interfaces:
                raise ConfigEntryNotReady(
                    f"Specified OPNsense tracker interface {interface} is not found"
                )

    entry.runtime_data = {
        CONF_INTERFACE_CLIENT: interfaces_client,
        CONF_TRACKER_INTERFACES: list(tracker_interfaces),
    }
    _entry_storage(hass)[entry.entry_id] = entry.runtime_data

    await discovery.async_load_platform(
        hass,
        Platform.DEVICE_TRACKER,
        DOMAIN,
        {"entry_id": entry.entry_id},
        hass.config.as_dict(),
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload an OPNsense config entry."""
    if OPNSENSE_DATA in hass.data:
        hass.data[OPNSENSE_DATA].pop(entry.entry_id, None)
    return True
