"""Support for NX584 alarm control panels."""

import asyncio
from dataclasses import dataclass
from typing import Any

from nx584 import client as nx584_client
import requests
from yarl import URL

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv, issue_registry as ir
from homeassistant.helpers.typing import ConfigType
from homeassistant.util.hass_dict import HassKey

from .const import DEFAULT_NAME, DOMAIN, REQUEST_TIMEOUT
from .services import async_setup_services

CONFIG_SCHEMA = cv.platform_only_config_schema(DOMAIN)

PLATFORMS = [Platform.ALARM_CONTROL_PANEL, Platform.BINARY_SENSOR]

DATA_IMPORT_LOCK: HassKey[asyncio.Lock] = HassKey(f"{DOMAIN}_import_lock")


@dataclass
class NX584Data:
    """Runtime data of an NX584 config entry."""

    client: nx584_client.Client
    zones: list[dict[str, Any]]
    version: str


type NX584ConfigEntry = ConfigEntry[NX584Data]


def create_client(host: str, port: int) -> nx584_client.Client:
    """Create a client for the NX584 server."""
    return nx584_client.Client(
        str(URL.build(scheme="http", host=host, port=port)), timeout=REQUEST_TIMEOUT
    )


def _fetch_zones(client: nx584_client.Client) -> tuple[list[dict[str, Any]], str]:
    """Return the zones and the version of the server."""
    return client.list_zones(), client.get_version()


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the NX584 component."""
    async_setup_services(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: NX584ConfigEntry) -> None:
    """Set up NX584 from a config entry."""
    client = create_client(entry.data[CONF_HOST], entry.data[CONF_PORT])
    try:
        zones, version = await hass.async_add_executor_job(_fetch_zones, client)
    except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as err:
        raise ConfigEntryNotReady(
            f"Unable to connect to the NX584 server at {entry.data[CONF_HOST]}"
        ) from err

    entry.runtime_data = NX584Data(client, zones, version)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)


async def async_unload_entry(hass: HomeAssistant, entry: NX584ConfigEntry) -> None:
    """Unload a config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)


async def async_import_yaml(hass: HomeAssistant, import_data: dict[str, Any]) -> None:
    """Import a YAML platform into the config entry of its server."""
    # The alarm and binary sensor platforms of one server import one at a time,
    # so the second one merges into the entry the first one created.
    async with hass.data.setdefault(DATA_IMPORT_LOCK, asyncio.Lock()):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data=import_data,
        )

    if (
        result["type"] is FlowResultType.ABORT
        and result["reason"] != "already_configured"
    ):
        ir.async_create_issue(
            hass,
            DOMAIN,
            f"deprecated_yaml_import_issue_{result['reason']}",
            breaks_in_ha_version="2027.5.0",
            is_fixable=False,
            issue_domain=DOMAIN,
            severity=ir.IssueSeverity.WARNING,
            translation_key=f"deprecated_yaml_import_issue_{result['reason']}",
            translation_placeholders={
                "domain": DOMAIN,
                "integration_title": DEFAULT_NAME,
            },
        )
        return

    ir.async_create_issue(
        hass,
        HOMEASSISTANT_DOMAIN,
        f"deprecated_yaml_{DOMAIN}",
        breaks_in_ha_version="2027.5.0",
        is_fixable=False,
        issue_domain=DOMAIN,
        severity=ir.IssueSeverity.WARNING,
        translation_key="deprecated_yaml",
        translation_placeholders={
            "domain": DOMAIN,
            "integration_title": DEFAULT_NAME,
        },
    )
