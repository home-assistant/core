"""Support for OPNsense Routers."""

from __future__ import annotations

from collections.abc import Mapping
from http import HTTPStatus
import logging
from typing import Any

from pyopnsense import diagnostics
from pyopnsense.exceptions import APIException
from requests import RequestException
import voluptuous as vol

from homeassistant.components.device_tracker import DOMAIN as DEVICE_TRACKER_DOMAIN
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_API_KEY, CONF_URL, CONF_VERIFY_SSL
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryError, ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv, discovery, issue_registry as ir
from homeassistant.helpers.typing import ConfigType

from .const import (
    CLIENT_TIMEOUT,
    CONF_API_SECRET,
    CONF_INTERFACE_CLIENT,
    CONF_TRACKER_INTERFACES,
    DOMAIN,
    INTEGRATION_TITLE,
    YAML_IMPORT_DEFAULT_VERIFY_SSL,
)

_LOGGER = logging.getLogger(__name__)


class InvalidAuth(Exception):
    """Error to indicate there is invalid auth."""


CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_URL): cv.url,
                vol.Required(CONF_API_KEY): cv.string,
                vol.Required(CONF_API_SECRET): cv.string,
                vol.Optional(CONF_VERIFY_SSL, default=YAML_IMPORT_DEFAULT_VERIFY_SSL): cv.boolean,
                vol.Optional(CONF_TRACKER_INTERFACES, default=[]): vol.All(
                    cv.ensure_list, [cv.string]
                ),
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def _async_import_from_yaml(hass: HomeAssistant, yaml_config: Mapping[str, Any]) -> None:
    """Import YAML config into a config entry and raise a deprecation issue."""
    try:
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data={
                CONF_URL: yaml_config[CONF_URL],
                CONF_API_KEY: yaml_config[CONF_API_KEY],
                CONF_API_SECRET: yaml_config[CONF_API_SECRET],
                # Keep the legacy functionality where SSL default is False.
                CONF_VERIFY_SSL: yaml_config.get(CONF_VERIFY_SSL, YAML_IMPORT_DEFAULT_VERIFY_SSL),
                CONF_TRACKER_INTERFACES: list(yaml_config.get(CONF_TRACKER_INTERFACES, [])),
            },
        )
    except Exception:
        _LOGGER.exception("Unexpected exception while importing OPNsense YAML config")
        ir.async_create_issue(
            hass,
            DOMAIN,
            f"yaml_import_issue_{DOMAIN}",
            is_fixable=False,
            issue_domain=DOMAIN,
            severity=ir.IssueSeverity.ERROR,
            translation_key="deprecated_yaml_import_issue_error",
        )
        return

    result_type = result.get("type")
    if result_type == FlowResultType.ABORT:
        if result.get("reason") != "already_configured":
            _LOGGER.warning("Failed to import OPNsense YAML config: %s", result)
            ir.async_create_issue(
                hass,
                DOMAIN,
                f"yaml_import_issue_{DOMAIN}",
                is_fixable=False,
                issue_domain=DOMAIN,
                severity=ir.IssueSeverity.ERROR,
                translation_key="deprecated_yaml_import_issue_error",
            )
            return
    elif result_type != FlowResultType.CREATE_ENTRY:
        # Flow has not resulted in a successful import; do not create deprecation issue yet.
        _LOGGER.debug("OPNsense YAML import did not complete successfully: %s", result)

        return

    ir.async_create_issue(
        hass,
        HOMEASSISTANT_DOMAIN,
        "deprecated_yaml",
        breaks_in_ha_version="2026.10.0",
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
        api_key, api_secret, url, verify_ssl, timeout=CLIENT_TIMEOUT
    )

    try:
        try:
            await hass.async_add_executor_job(interfaces_client.get_arp)
        except APIException as err:
            if err.status_code in {HTTPStatus.UNAUTHORIZED, HTTPStatus.FORBIDDEN}:
                raise InvalidAuth(
                    "Authentication failed while connecting to OPNsense API endpoint"
                ) from err
            raise ConfigEntryError(
                f"Failure while connecting to OPNsense API endpoint: {err}"
            ) from err
        except RequestException as err:
            raise ConfigEntryNotReady("Failure while connecting to OPNsense API endpoint") from err

        if tracker_interfaces:
            netinsight_client = diagnostics.NetworkInsightClient(
                api_key, api_secret, url, verify_ssl, timeout=CLIENT_TIMEOUT
            )

            try:
                interfaces = await hass.async_add_executor_job(
                    lambda: list(netinsight_client.get_interfaces().values())
                )
            except APIException as err:
                if err.status_code in {HTTPStatus.UNAUTHORIZED, HTTPStatus.FORBIDDEN}:
                    raise InvalidAuth(
                        "Authentication failed while validating OPNsense tracker interfaces"
                    ) from err
                raise ConfigEntryError(
                    f"Failure while validating OPNsense tracker interfaces: {err}"
                ) from err
            except RequestException as err:
                raise ConfigEntryNotReady(
                    "Failure while validating OPNsense tracker interfaces"
                ) from err

            for interface in tracker_interfaces:
                if interface not in interfaces:
                    raise ConfigEntryError(
                        f"Specified OPNsense tracker interface {interface} is not found"
                    )
    except InvalidAuth as err:
        raise ConfigEntryAuthFailed(str(err)) from err

    entry.runtime_data = {
        CONF_INTERFACE_CLIENT: interfaces_client,
        CONF_TRACKER_INTERFACES: list(tracker_interfaces),
    }
    await discovery.async_load_platform(
        hass,
        DEVICE_TRACKER_DOMAIN,
        "opnsense",
        {"entry_id": entry.entry_id},
        {},
    )
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload an OPNsense config entry."""
    entry.runtime_data = None
    return True
