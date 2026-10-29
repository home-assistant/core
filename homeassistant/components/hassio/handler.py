"""Handler for Supervisor."""

from dataclasses import dataclass
from http import HTTPStatus
import logging
import os
from pathlib import Path
from typing import Any

from aiohasupervisor import SupervisorClient
from aiohasupervisor.models import SupervisorOptions
import aiohttp
from yarl import URL

from homeassistant.const import EVENT_HOMEASSISTANT_CLOSE
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import (
    MAXIMUM_HEADER_SIZE,
    async_get_clientsession,
)
from homeassistant.helpers.json import json_dumps
from homeassistant.helpers.singleton import singleton
from homeassistant.util.hass_dict import HassKey

from .const import (
    ATTR_MESSAGE,
    ATTR_RESULT,
    DOMAIN,
    ENV_SUPERVISOR,
    ENV_SUPERVISOR_SOCKET,
    ENV_SUPERVISOR_TOKEN,
    X_HASS_SOURCE,
)

_LOGGER = logging.getLogger(__name__)

KEY_PASSTHROUGH_SUPERVISOR_CLIENT: HassKey[HassIO] = HassKey(DOMAIN)
KEY_SUPERVISOR_CLIENT: HassKey[SupervisorClient] = HassKey("supervisor_client")
KEY_SUPERVISOR_CONNECTION: HassKey[SupervisorConnection] = HassKey(
    "hassio_supervisor_connection"
)


class HassioAPIError(RuntimeError):
    """Return if a API trow a error."""


@dataclass(frozen=True, slots=True)
class SupervisorConnection:
    """Transport Home Assistant uses to reach Supervisor."""

    session: aiohttp.ClientSession
    base_url: URL
    # If set, session must connect to this socket
    unix_socket: Path | None = None

    @property
    def auth_headers(self) -> dict[str, str]:
        """Return headers authenticating Home Assistant to Supervisor."""
        # Supervisor identifies the caller by the socket and ignores tokens there
        if self.unix_socket is not None:
            return {}
        return {
            aiohttp.hdrs.AUTHORIZATION: (
                f"Bearer {os.environ.get(ENV_SUPERVISOR_TOKEN, '')}"
            )
        }


class HassIO:
    """Small API wrapper for Supervisor."""

    def __init__(self, connection: SupervisorConnection) -> None:
        """Initialize Supervisor API wrapper."""
        self._connection = connection

    async def send_command(
        self,
        command: str,
        method: str = "post",
        payload: Any | None = None,
        timeout: int | None = 10,
        return_text: bool = False,
        *,
        params: dict[str, Any] | None = None,
        range_header: str | None = None,
        source: str = "core.handler",
    ) -> Any:
        """Send API command to Supervisor.

        This method is a coroutine.
        """
        joined_url = self._connection.base_url.with_path(command)
        # This check is to make sure the normalized URL string
        # is the same as the URL string that was passed in. If
        # they are different, then the passed in command URL
        # contained characters that were removed by the normalization
        # such as ../../../../etc/passwd
        if joined_url.raw_path != command:
            _LOGGER.error("Invalid request %s", command)
            raise HassioAPIError

        headers = {**self._connection.auth_headers, X_HASS_SOURCE: source}
        if range_header is not None:
            headers[aiohttp.hdrs.RANGE] = range_header

        try:
            response = await self._connection.session.request(
                method,
                joined_url,
                params=params,
                json=payload,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=timeout),
            )

            if response.status != HTTPStatus.OK:
                try:
                    error = await response.json(encoding="utf-8")
                except aiohttp.ContentTypeError:
                    # Errors raised outside Supervisor's API handlers are plain text
                    raise HassioAPIError(
                        await response.text(encoding="utf-8")
                    ) from None
                if error.get(ATTR_RESULT) == "error":
                    raise HassioAPIError(error.get(ATTR_MESSAGE))

                _LOGGER.error(
                    "Request to %s method %s returned with code %d",
                    command,
                    method,
                    response.status,
                )
                raise HassioAPIError

            if return_text:
                return await response.text(encoding="utf-8")

            return await response.json(encoding="utf-8")

        except TimeoutError:
            _LOGGER.error("Timeout on %s request", command)

        except aiohttp.ClientError as err:
            _LOGGER.error("Client error on %s request %s", command, err)

        raise HassioAPIError


@callback
def _async_create_supervisor_socket_session(
    hass: HomeAssistant, unix_socket: Path
) -> aiohttp.ClientSession:
    """Create a session connecting to Supervisor over its Unix socket."""
    session = aiohttp.ClientSession(
        connector=aiohttp.UnixConnector(path=str(unix_socket)),
        json_serialize=json_dumps,
        # Every response comes from host "localhost", so a real cookie jar would
        # replay cookies set through ingress to all apps, users and Supervisor
        cookie_jar=aiohttp.DummyCookieJar(),
        max_line_size=MAXIMUM_HEADER_SIZE,
        max_field_size=MAXIMUM_HEADER_SIZE,
    )

    async def _async_close_session(event: Event) -> None:
        await session.close()

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_CLOSE, _async_close_session)
    return session


@singleton(KEY_SUPERVISOR_CONNECTION)
def get_supervisor_connection(hass: HomeAssistant) -> SupervisorConnection:
    """Return the transport to the Supervisor this Core runs under."""
    if supervisor_socket := os.environ.get(ENV_SUPERVISOR_SOCKET):
        unix_socket = Path(supervisor_socket)
        return SupervisorConnection(
            _async_create_supervisor_socket_session(hass, unix_socket),
            URL("http://localhost"),
            unix_socket,
        )
    return SupervisorConnection(
        async_get_clientsession(hass), URL(f"http://{os.environ[ENV_SUPERVISOR]}")
    )


@singleton(KEY_PASSTHROUGH_SUPERVISOR_CLIENT)
def get_passthrough_supervisor_client(hass: HomeAssistant) -> HassIO:
    """Return the handler for the Supervisor API passthrough."""
    return HassIO(get_supervisor_connection(hass))


@singleton(KEY_SUPERVISOR_CLIENT)
def get_supervisor_client(hass: HomeAssistant) -> SupervisorClient:
    """Return supervisor client."""
    connection = get_supervisor_connection(hass)
    if connection.unix_socket is not None:
        return SupervisorClient(
            str(connection.base_url),
            session=connection.session,
            source="core/aiohasupervisor",
            unix_socket=connection.unix_socket,
        )
    return SupervisorClient(
        str(connection.base_url),
        os.environ.get(ENV_SUPERVISOR_TOKEN, ""),
        session=connection.session,
        source="core/aiohasupervisor",
    )


async def async_update_diagnostics(hass: HomeAssistant, diagnostics: bool) -> None:
    """Update Supervisor diagnostics toggle.

    The caller of the function should handle SupervisorError.
    """
    await get_supervisor_client(hass).supervisor.set_options(
        SupervisorOptions(diagnostics=diagnostics)
    )
