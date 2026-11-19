"""Support for exposing regular REST commands as services."""

from collections.abc import Mapping
from typing import Any

import probatio

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_AUTHENTICATION,
    CONF_HEADERS,
    CONF_METHOD,
    CONF_PASSWORD,
    CONF_PATH,
    CONF_PAYLOAD,
    CONF_TIMEOUT,
    CONF_URL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
    HTTP_BASIC_AUTHENTICATION,
    HTTP_DIGEST_AUTHENTICATION,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, issue_registry as ir
from homeassistant.helpers.typing import ConfigType

from .const import (
    CONF_ACTION,
    CONF_CONTENT_TYPE,
    CONF_INSECURE_CIPHER,
    CONF_SKIP_URL_ENCODING,
    DOMAIN,
    SECTION_ADDITIONAL,
    SECTION_AUTH,
)
from .services import async_register_rest_command, async_setup_services

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
    for name, command_config in config.get(DOMAIN, {}).items():
        async_register_rest_command(hass, name, command_config)

    async_setup_services(hass)

    return True


type RestCommandConfigEntry = ConfigEntry[set[str]]


def flatten(data: Mapping[str, Any]) -> dict[str, Any]:
    """Move the values out of the form sections and drop empty values."""
    flat = dict(data)
    for key in (SECTION_AUTH, SECTION_ADDITIONAL):
        flat.update(flat.pop(key, {}))
    # An empty username or password is valid, like in YAML: some servers
    # expect only a username, others only a token as the password
    return {
        key: value
        for key, value in flat.items()
        if value not in (None, "", {})
        or (key in (CONF_USERNAME, CONF_PASSWORD) and value == "")
    }


def merge_command_config(
    server: Mapping[str, Any], command: Mapping[str, Any]
) -> dict[str, Any]:
    """Combine the settings of a server with those of one of its commands."""
    server, command = flatten(server), flatten(command)
    config = {**server, **command}
    config[CONF_URL] = server[CONF_URL] + config.pop(CONF_PATH, "")
    # Headers of the command are added to those of the server, and win.
    # Header names are case-insensitive, so they are compared in lowercase.
    headers = {
        str(name).lower(): (name, value)
        for source in (server, command)
        for name, value in source.get(CONF_HEADERS, {}).items()
    }
    if headers:
        config[CONF_HEADERS] = dict(headers.values())
    return config


async def async_setup_entry(hass: HomeAssistant, entry: RestCommandConfigEntry) -> None:
    """Set up the REST commands configured in the UI."""
    # The actions this entry registered, so reloading YAML leaves them alone
    entry.runtime_data = set()
    for subentry in entry.subentries.values():
        command_config = merge_command_config(entry.data, subentry.data)
        name: str = command_config.pop(CONF_ACTION)
        issue_id = f"invalid_command_{subentry.subentry_id}"
        try:
            validated = COMMAND_SCHEMA(command_config)
        except probatio.Invalid as err:
            # One broken command must not take the other commands down with it
            ir.async_create_issue(
                hass,
                DOMAIN,
                issue_id,
                config_entry_id=entry.entry_id,
                config_subentry_id=subentry.subentry_id,
                is_fixable=False,
                severity=ir.IssueSeverity.ERROR,
                translation_key="invalid_command",
                translation_placeholders={
                    "action": f"{DOMAIN}.{name}",
                    "server": entry.title,
                    "error": str(err),
                },
            )
            continue
        ir.async_delete_issue(hass, DOMAIN, issue_id)
        entry.async_on_unload(async_register_rest_command(hass, name, validated))
        entry.runtime_data.add(name)

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))


async def async_unload_entry(
    hass: HomeAssistant, entry: RestCommandConfigEntry
) -> None:
    """Unload the REST commands configured in the UI."""


async def _async_update_listener(
    hass: HomeAssistant, entry: RestCommandConfigEntry
) -> None:
    """Reload the entry when a command is added, changed or removed."""
    hass.config_entries.async_schedule_reload(entry.entry_id)
