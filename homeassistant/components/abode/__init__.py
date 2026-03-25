"""Support for the Abode Security System."""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import partial
from http import HTTPStatus
from pathlib import Path
from typing import cast

from jaraco.abode.client import Client as Abode
import jaraco.abode.config
from jaraco.abode.exceptions import (
    AuthenticationException as AbodeAuthenticationException,
    Exception as AbodeException,
)
from jaraco.abode.helpers.timeline import Groups as GROUPS
from requests import Response
from requests.exceptions import ConnectTimeout, HTTPError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_DATE,
    ATTR_DEVICE_ID,
    ATTR_TIME,
    CONF_PASSWORD,
    CONF_USERNAME,
    EVENT_HOMEASSISTANT_STOP,
    Platform,
)
from homeassistant.core import CALLBACK_TYPE, Event, HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import CONF_POLLING, DOMAIN, DOMAIN_DATA, LOGGER
from .services import async_setup_services

ATTR_DEVICE_NAME = "device_name"
ATTR_DEVICE_TYPE = "device_type"
ATTR_EVENT_CODE = "event_code"
ATTR_EVENT_NAME = "event_name"
ATTR_EVENT_TYPE = "event_type"
ATTR_EVENT_UTC = "event_utc"
ATTR_USER_NAME = "user_name"
ATTR_APP_TYPE = "app_type"
ATTR_EVENT_BY = "event_by"

CONFIG_SCHEMA = cv.removed(DOMAIN, raise_if_present=False)

PLATFORMS = [
    Platform.ALARM_CONTROL_PANEL,
    Platform.BINARY_SENSOR,
    Platform.CAMERA,
    Platform.COVER,
    Platform.LIGHT,
    Platform.LOCK,
    Platform.SENSOR,
    Platform.SWITCH,
]


@dataclass
class AbodeSystem:
    """Abode System class."""

    abode: Abode
    polling: bool
    entity_ids: set[str | None] = field(default_factory=set)
    logout_listener: CALLBACK_TYPE | None = None

AUTH_STATUS_CODES: set[int] = {
    HTTPStatus.BAD_REQUEST,
    HTTPStatus.UNAUTHORIZED,
    HTTPStatus.FORBIDDEN,
}


def _start_reauth(
    hass: HomeAssistant,
    entry: ConfigEntry,
    abode: Abode,
    polling: bool,
    error: Exception,
) -> None:
    """Start a reauthentication flow when auth fails at runtime."""
    LOGGER.warning(
        "Abode authentication failed at runtime: %s. Starting reauthentication",
        error,
    )

    # Stop event stream first to avoid aggressive retries while user reauthenticates.
    if not polling:
        try:
            abode.events.stop()
        except Exception as ex:  # noqa: BLE001
            LOGGER.debug("Failed stopping Abode event stream: %s", ex)

    entry.async_start_reauth(hass)


def _is_auth_error(error: Exception) -> bool:
    """Return True if an exception indicates an auth failure."""
    if isinstance(error, AbodeAuthenticationException):
        return True

    if isinstance(error, HTTPError) and error.response is not None:
        return error.response.status_code in AUTH_STATUS_CODES

    if isinstance(error, AbodeException):
        if int(error.errcode) in AUTH_STATUS_CODES:
            return True

        message = error.message.lower()
        return (
            "unauthorized" in message
            or "invalid credentials" in message
            or ("password" in message and "match" in message)
        )

    return False


def _is_auth_like_response(response: Response) -> bool:
    """Return True if a response payload indicates auth failure despite 200 status."""
    status_code = response.status_code
    if status_code in AUTH_STATUS_CODES:
        return True
    if status_code != HTTPStatus.OK:
        return False

    content_type = response.headers.get("Content-Type", "")
    if "application/json" not in content_type.lower():
        return False

    try:
        response_json = response.json()
    except ValueError:
        return False

    if not isinstance(response_json, dict):
        return False

    message = str(response_json.get("message", "")).lower()
    error_code = response_json.get("errorCode")

    # Abode has returned auth errors in JSON payloads; guard that too.
    return error_code in {11002, 13027} or (
        "unauthorized" in message
        or "invalid credentials" in message
        or ("password" in message and "match" in message)
    )


def _install_runtime_auth_guard(
    abode_system: AbodeSystem, hass: HomeAssistant, entry: ConfigEntry
) -> None:
    """Wrap Abode requests to trigger reauth on runtime auth failures."""
    original_send_request = abode_system.abode.send_request

    def wrapped_send_request(
        method: str,
        path: str,
        headers: dict[str, str] | None = None,
        data: dict[str, str] | None = None,
    ) -> Response:
        try:
            response = cast(Response, original_send_request(method, path, headers, data))
        except Exception as ex:
            if _is_auth_error(ex):
                _start_reauth(
                    hass, entry, abode_system.abode, abode_system.polling, ex
                )
            raise

        if _is_auth_like_response(response):
            auth_error = AbodeAuthenticationException(
                (
                    HTTPStatus.UNAUTHORIZED,
                    "Abode returned an authentication error payload",
                )
            )
            _start_reauth(
                hass, entry, abode_system.abode, abode_system.polling, auth_error
            )
            raise auth_error

        return response

    # This is an instance-level wrapper; avoid changing upstream library behavior globally.
    abode_system.abode.send_request = wrapped_send_request


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Abode component."""
    async_setup_services(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Abode integration from a config entry."""
    username = entry.data[CONF_USERNAME]
    password = entry.data[CONF_PASSWORD]
    polling = entry.data[CONF_POLLING]

    # Configure abode library to use config directory for storing data
    jaraco.abode.config.paths.override(user_data=Path(hass.config.path("Abode")))

    # For previous config entries where unique_id is None
    if entry.unique_id is None:
        hass.config_entries.async_update_entry(
            entry, unique_id=entry.data[CONF_USERNAME]
        )

    try:
        abode = await hass.async_add_executor_job(
            Abode, username, password, True, True, True
        )

    except AbodeAuthenticationException as ex:
        raise ConfigEntryAuthFailed(f"Invalid credentials: {ex}") from ex

    except (AbodeException, ConnectTimeout, HTTPError) as ex:
        raise ConfigEntryNotReady(f"Unable to connect to Abode: {ex}") from ex

    hass.data[DOMAIN_DATA] = AbodeSystem(abode, polling)
    _install_runtime_auth_guard(hass.data[DOMAIN_DATA], hass, entry)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    await setup_hass_events(hass)
    await hass.async_add_executor_job(setup_abode_events, hass)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    await hass.async_add_executor_job(hass.data[DOMAIN_DATA].abode.events.stop)
    await hass.async_add_executor_job(hass.data[DOMAIN_DATA].abode.logout)

    if logout_listener := hass.data[DOMAIN_DATA].logout_listener:
        logout_listener()
    hass.data.pop(DOMAIN_DATA)

    return unload_ok


async def setup_hass_events(hass: HomeAssistant) -> None:
    """Home Assistant start and stop callbacks."""

    def logout(event: Event) -> None:
        """Logout of Abode."""
        if not hass.data[DOMAIN_DATA].polling:
            hass.data[DOMAIN_DATA].abode.events.stop()

        hass.data[DOMAIN_DATA].abode.logout()
        LOGGER.info("Logged out of Abode")

    if not hass.data[DOMAIN_DATA].polling:
        await hass.async_add_executor_job(hass.data[DOMAIN_DATA].abode.events.start)

    hass.data[DOMAIN_DATA].logout_listener = hass.bus.async_listen_once(
        EVENT_HOMEASSISTANT_STOP, logout
    )


def setup_abode_events(hass: HomeAssistant) -> None:
    """Event callbacks."""

    def event_callback(event: str, event_json: dict[str, str]) -> None:
        """Handle an event callback from Abode."""
        data = {
            ATTR_DEVICE_ID: event_json.get(ATTR_DEVICE_ID, ""),
            ATTR_DEVICE_NAME: event_json.get(ATTR_DEVICE_NAME, ""),
            ATTR_DEVICE_TYPE: event_json.get(ATTR_DEVICE_TYPE, ""),
            ATTR_EVENT_CODE: event_json.get(ATTR_EVENT_CODE, ""),
            ATTR_EVENT_NAME: event_json.get(ATTR_EVENT_NAME, ""),
            ATTR_EVENT_TYPE: event_json.get(ATTR_EVENT_TYPE, ""),
            ATTR_EVENT_UTC: event_json.get(ATTR_EVENT_UTC, ""),
            ATTR_USER_NAME: event_json.get(ATTR_USER_NAME, ""),
            ATTR_APP_TYPE: event_json.get(ATTR_APP_TYPE, ""),
            ATTR_EVENT_BY: event_json.get(ATTR_EVENT_BY, ""),
            ATTR_DATE: event_json.get(ATTR_DATE, ""),
            ATTR_TIME: event_json.get(ATTR_TIME, ""),
        }

        hass.bus.fire(event, data)

    events = [
        GROUPS.ALARM,
        GROUPS.ALARM_END,
        GROUPS.PANEL_FAULT,
        GROUPS.PANEL_RESTORE,
        GROUPS.AUTOMATION,
        GROUPS.DISARM,
        GROUPS.ARM,
        GROUPS.ARM_FAULT,
        GROUPS.TEST,
        GROUPS.CAPTURE,
        GROUPS.DEVICE,
    ]

    for event in events:
        hass.data[DOMAIN_DATA].abode.events.add_event_callback(
            event, partial(event_callback, event)
        )
