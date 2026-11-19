"""Support for exposing regular REST commands as services."""

import logging
from types import MappingProxyType
from typing import Any

import probatio

from homeassistant.config_entries import (
    SOURCE_IGNORE,
    SOURCE_IMPORT,
    ConfigEntry,
    ConfigSubentry,
    ConfigSubentryData,
)
from homeassistant.const import (
    CONF_AUTHENTICATION,
    CONF_HEADERS,
    CONF_METHOD,
    CONF_PASSWORD,
    CONF_PAYLOAD,
    CONF_TIMEOUT,
    CONF_URL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
    HTTP_BASIC_AUTHENTICATION,
    HTTP_DIGEST_AUTHENTICATION,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, issue_registry as ir
from homeassistant.helpers.template import Template
from homeassistant.helpers.typing import ConfigType

from .const import (
    CONF_ACTION,
    CONF_CONTENT_TYPE,
    CONF_INSECURE_CIPHER,
    CONF_SKIP_URL_ENCODING,
    DOMAIN,
    SUBENTRY_TYPE_COMMAND,
)
from .services import async_register_rest_command, async_setup_services

_LOGGER = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 10
DEFAULT_METHOD = "get"
DEFAULT_VERIFY_SSL = True

SUPPORT_REST_METHODS = ["get", "patch", "post", "put", "delete"]


COMMAND_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_URL): cv.template,
        probatio.Optional(CONF_METHOD, default=DEFAULT_METHOD): probatio.All(
            probatio.Lower, probatio.In(SUPPORT_REST_METHODS)
        ),
        probatio.Optional(CONF_HEADERS): probatio.Schema({cv.string: cv.template}),
        probatio.Optional(CONF_AUTHENTICATION): probatio.In(
            [HTTP_BASIC_AUTHENTICATION, HTTP_DIGEST_AUTHENTICATION]
        ),
        # A colon cannot be encoded into basic credentials, RFC 7617#section-2
        probatio.Inclusive(CONF_USERNAME, "authentication"): probatio.All(
            cv.string, probatio.Match(r"^[^:]*$")
        ),
        probatio.Inclusive(probatio.Secret(CONF_PASSWORD), "authentication"): cv.string,
        probatio.Optional(CONF_PAYLOAD): cv.template,
        probatio.Optional(CONF_TIMEOUT, default=DEFAULT_TIMEOUT): probatio.Coerce(int),
        probatio.Optional(CONF_CONTENT_TYPE): cv.string,
        probatio.Optional(CONF_VERIFY_SSL, default=DEFAULT_VERIFY_SSL): cv.boolean,
        probatio.Optional(CONF_INSECURE_CIPHER, default=False): cv.boolean,
        probatio.Optional(CONF_SKIP_URL_ENCODING, default=False): cv.boolean,
    }
)

CONFIG_SCHEMA = probatio.Schema(
    {DOMAIN: cv.schema_with_slug_keys(COMMAND_SCHEMA)}, extra=probatio.ALLOW_EXTRA
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the REST command component."""
    async_setup_services(hass)
    async_import_yaml_commands(hass, config.get(DOMAIN, {}))

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Set up the REST commands configured in the UI."""
    for subentry in entry.subentries.values():
        command_config = dict(subentry.data)
        name: str = command_config.pop(CONF_ACTION)
        try:
            validated = COMMAND_SCHEMA(command_config)
        except probatio.Invalid as err:
            # One broken command must not take the other commands down with it
            _LOGGER.error("Invalid configuration for %s.%s: %s", DOMAIN, name, err)
            continue
        entry.async_on_unload(async_register_rest_command(hass, name, validated))

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Unload the REST commands configured in the UI."""


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the entry when a command is added, changed or removed."""
    hass.config_entries.async_schedule_reload(entry.entry_id)


def _to_storable(command_config: dict[str, Any]) -> dict[str, Any]:
    """Turn a validated YAML command back into plain values."""
    data: dict[str, Any] = {}
    for key, value in command_config.items():
        if isinstance(value, Template):
            data[key] = value.template
        elif key == CONF_HEADERS:
            data[key] = {name: header.template for name, header in value.items()}
        else:
            data[key] = value
    return data


@callback
def async_import_yaml_commands(
    hass: HomeAssistant, commands: dict[str, dict[str, Any]]
) -> None:
    """Copy the commands from YAML that are not imported yet into the entry."""
    if not commands:
        return

    subentries = [
        ConfigSubentryData(
            data={CONF_ACTION: name, **_to_storable(command_config)},
            subentry_type=SUBENTRY_TYPE_COMMAND,
            title=name,
            unique_id=name,
        )
        for name, command_config in commands.items()
    ]

    if entries := hass.config_entries.async_entries(DOMAIN, include_ignore=True):
        entry = entries[0]
        if entry.source == SOURCE_IGNORE:
            return
        imported = {subentry.unique_id for subentry in entry.subentries.values()}
        for subentry in subentries:
            if subentry["unique_id"] in imported:
                continue
            hass.config_entries.async_add_subentry(
                entry,
                ConfigSubentry(
                    data=MappingProxyType(subentry["data"]),
                    subentry_type=subentry["subentry_type"],
                    title=subentry["title"],
                    unique_id=subentry["unique_id"],
                ),
            )
    else:
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": SOURCE_IMPORT},
                data={"subentries": subentries},
            ),
            eager_start=True,
        )

    ir.async_create_issue(
        hass,
        DOMAIN,
        "yaml_imported",
        is_fixable=False,
        severity=ir.IssueSeverity.WARNING,
        translation_key="yaml_imported",
    )
