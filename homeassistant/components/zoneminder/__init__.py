"""Support for ZoneMinder."""

import asyncio
from dataclasses import dataclass
from typing import Any

import probatio
from requests.exceptions import (
    ConnectionError as RequestsConnectionError,
    RequestException,
    Timeout as RequestsTimeout,
)
from yarl import URL
from zoneminder.monitor import Monitor
from zoneminder.zm import ZoneMinder

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PATH,
    CONF_SSL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
    Platform,
)
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.exceptions import ConfigEntryError, ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue
from homeassistant.helpers.typing import ConfigType
from homeassistant.util.hass_dict import HassKey

from .const import (
    CONF_PATH_ZMS,
    DEFAULT_PATH,
    DEFAULT_PATH_ZMS,
    DEFAULT_SSL,
    DEFAULT_VERIFY_SSL,
    DOMAIN,
)
from .services import async_setup_services

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.CAMERA,
    Platform.SENSOR,
    Platform.SWITCH,
]

HOST_CONFIG_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_HOST): cv.string,
        probatio.Optional(probatio.Secret(CONF_PASSWORD)): cv.string,
        probatio.Optional(CONF_PATH, default=DEFAULT_PATH): cv.string,
        probatio.Optional(CONF_PATH_ZMS, default=DEFAULT_PATH_ZMS): cv.string,
        probatio.Optional(CONF_SSL, default=DEFAULT_SSL): cv.boolean,
        probatio.Optional(CONF_USERNAME): cv.string,
        probatio.Optional(CONF_VERIFY_SSL, default=DEFAULT_VERIFY_SSL): cv.boolean,
    }
)

CONFIG_SCHEMA = probatio.Schema(
    {DOMAIN: probatio.All(probatio.EnsureList(), [HOST_CONFIG_SCHEMA])},
    extra=probatio.ALLOW_EXTRA,
)

DATA_YAML_CONFIG: HassKey[list[dict[str, Any]]] = HassKey(f"{DOMAIN}_yaml_config")
DATA_IMPORT_LOCK: HassKey[asyncio.Lock] = HassKey(f"{DOMAIN}_import_lock")


@dataclass
class ZoneMinderData:
    """Runtime data of a ZoneMinder config entry."""

    client: ZoneMinder
    monitors: list[Monitor]


type ZoneMinderConfigEntry = ConfigEntry[ZoneMinderData]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the ZoneMinder component."""
    async_setup_services(hass)

    if DOMAIN not in config:
        return True

    hass.data[DATA_YAML_CONFIG] = config[DOMAIN]
    for conf in config[DOMAIN]:
        hass.async_create_task(_async_import(hass, conf))

    return True


async def async_import_platform_yaml(
    hass: HomeAssistant, platform: Platform, platform_data: dict[str, Any]
) -> None:
    """Import a YAML platform section into the entry of every YAML server."""
    async_create_platform_yaml_issue(hass, platform)
    # The platform section has no host, so it applies to every server.
    for conf in hass.data.get(DATA_YAML_CONFIG, []):
        await _async_import(hass, {**conf, **platform_data})


async def _async_import(hass: HomeAssistant, import_data: dict[str, Any]) -> None:
    """Import a ZoneMinder server from YAML and raise the matching issue."""
    # The server and its platform sections import one at a time,
    # so each one merges into the entry the first one created.
    async with hass.data.setdefault(DATA_IMPORT_LOCK, asyncio.Lock()):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_IMPORT}, data=import_data
        )

    if (
        result["type"] is FlowResultType.ABORT
        and (reason := result["reason"]) != "already_configured"
    ):
        host = import_data[CONF_HOST]
        async_create_issue(
            hass,
            DOMAIN,
            f"deprecated_yaml_import_issue_{reason}_{host}",
            breaks_in_ha_version="2027.6.0",
            is_fixable=False,
            issue_domain=DOMAIN,
            severity=IssueSeverity.WARNING,
            translation_key=f"deprecated_yaml_import_issue_{reason}",
            translation_placeholders={
                "domain": DOMAIN,
                "host": host,
                "integration_title": "ZoneMinder",
            },
        )
        return

    async_create_issue(
        hass,
        HOMEASSISTANT_DOMAIN,
        f"deprecated_yaml_{DOMAIN}",
        breaks_in_ha_version="2027.6.0",
        is_fixable=False,
        issue_domain=DOMAIN,
        severity=IssueSeverity.WARNING,
        translation_key="deprecated_yaml",
        translation_placeholders={
            "domain": DOMAIN,
            "integration_title": "ZoneMinder",
        },
    )


@callback
def async_create_platform_yaml_issue(hass: HomeAssistant, platform: Platform) -> None:
    """Raise an issue for a leftover ZoneMinder platform section in YAML."""
    async_create_issue(
        hass,
        DOMAIN,
        f"deprecated_yaml_platform_{platform}",
        breaks_in_ha_version="2027.6.0",
        is_fixable=False,
        issue_domain=DOMAIN,
        severity=IssueSeverity.WARNING,
        translation_key="deprecated_yaml_platform",
        translation_placeholders={"domain": DOMAIN, "platform": platform},
    )


def create_client(data: dict[str, Any]) -> ZoneMinder:
    """Create a ZoneMinder client from config entry data."""
    server_origin = URL.build(
        scheme="https" if data[CONF_SSL] else "http", authority=data[CONF_HOST]
    )
    return ZoneMinder(
        str(server_origin),
        data.get(CONF_USERNAME),
        data.get(CONF_PASSWORD),
        data[CONF_PATH],
        data[CONF_PATH_ZMS],
        data[CONF_VERIFY_SSL],
    )


async def async_setup_entry(hass: HomeAssistant, entry: ZoneMinderConfigEntry) -> None:
    """Set up ZoneMinder from a config entry."""
    client = create_client(dict(entry.data))

    try:
        logged_in = await hass.async_add_executor_job(client.login)
    except (RequestsConnectionError, RequestsTimeout) as err:
        raise ConfigEntryNotReady(
            f"Unable to connect to ZoneMinder at {entry.data[CONF_HOST]}"
        ) from err
    except RequestException as err:
        raise ConfigEntryError(
            f"Invalid request to ZoneMinder at {entry.data[CONF_HOST]}"
        ) from err

    if not logged_in:
        raise ConfigEntryError(
            f"Invalid credentials for ZoneMinder at {entry.data[CONF_HOST]}"
        )
    if not (monitors := await hass.async_add_executor_job(client.get_monitors)):
        raise ConfigEntryNotReady(
            f"Unable to fetch any monitors from ZoneMinder at {entry.data[CONF_HOST]}"
        )

    entry.runtime_data = ZoneMinderData(client=client, monitors=monitors)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)


async def async_unload_entry(hass: HomeAssistant, entry: ZoneMinderConfigEntry) -> None:
    """Unload a ZoneMinder config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)
