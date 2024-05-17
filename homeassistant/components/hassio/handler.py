"""Handler for Hass.io."""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Coroutine
from http import HTTPStatus
import logging
import os
from typing import Any

import aiohttp
from yarl import URL

from homeassistant.auth.models import RefreshToken
from homeassistant.components.http import (
    CONF_SERVER_HOST,
    CONF_SERVER_PORT,
    CONF_SSL_CERTIFICATE,
)
from homeassistant.const import SERVER_PORT
from homeassistant.core import HomeAssistant
from homeassistant.loader import bind_hass

from .const import ATTR_DISCOVERY, ATTR_MESSAGE, ATTR_RESULT, DOMAIN, X_HASS_SOURCE

_LOGGER = logging.getLogger(__name__)


class HassioAPIError(RuntimeError):
    """Return if a API trow a error."""


def _api_bool[**_P](
    funct: Callable[_P, Coroutine[Any, Any, dict[str, Any]]],
) -> Callable[_P, Coroutine[Any, Any, bool]]:
    """Return a boolean."""

    async def _wrapper(*argv: _P.args, **kwargs: _P.kwargs) -> bool:
        """Wrap function."""
        try:
            data = await funct(*argv, **kwargs)
            return data["result"] == "ok"
        except HassioAPIError:
            return False

    return _wrapper


def api_data[**_P](
    funct: Callable[_P, Coroutine[Any, Any, dict[str, Any]]],
) -> Callable[_P, Coroutine[Any, Any, Any]]:
    """Return data of an api."""

    async def _wrapper(*argv: _P.args, **kwargs: _P.kwargs) -> Any:
        """Wrap function."""
        data = await funct(*argv, **kwargs)
        if data["result"] == "ok":
            return data["data"]
        raise HassioAPIError(data["message"])

    return _wrapper


@bind_hass
async def async_get_addon_info(hass: HomeAssistant, slug: str) -> dict:
    """Return add-on info.

    The add-on must be installed.
    The caller of the function should handle HassioAPIError.
    """
    hassio: HassIO = hass.data[DOMAIN]
    return await hassio.get_addon_info(slug)


@api_data
async def async_get_addon_store_info(hass: HomeAssistant, slug: str) -> dict:
    """Return add-on store info.

    The caller of the function should handle HassioAPIError.
    """
    hassio: HassIO = hass.data[DOMAIN]
    command = f"/store/addons/{slug}"
    return await hassio.send_command(command, method="get")


@bind_hass
async def async_update_diagnostics(hass: HomeAssistant, diagnostics: bool) -> bool:
    """Update Supervisor diagnostics toggle.

    The caller of the function should handle HassioAPIError.
    """
    hassio: HassIO = hass.data[DOMAIN]
    return await hassio.update_diagnostics(diagnostics)


@bind_hass
@api_data
async def async_install_addon(hass: HomeAssistant, slug: str) -> dict:
    """Install add-on.

    The caller of the function should handle HassioAPIError.
    """
    hassio: HassIO = hass.data[DOMAIN]
    command = f"/addons/{slug}/install"
    return await hassio.send_command(command, timeout=None)


@bind_hass
@api_data
async def async_uninstall_addon(hass: HomeAssistant, slug: str) -> dict:
    """Uninstall add-on.

    The caller of the function should handle HassioAPIError.
    """
    hassio: HassIO = hass.data[DOMAIN]
    command = f"/addons/{slug}/uninstall"
    return await hassio.send_command(command, timeout=60)


@bind_hass
@api_data
async def async_update_addon(
    hass: HomeAssistant,
    slug: str,
    backup: bool = False,
) -> dict:
    """Update add-on.

    The caller of the function should handle HassioAPIError.
    """
    hassio: HassIO = hass.data[DOMAIN]
    command = f"/addons/{slug}/update"
    return await hassio.send_command(
        command,
        payload={"backup": backup},
        timeout=None,
    )


@bind_hass
@api_data
async def async_start_addon(hass: HomeAssistant, slug: str) -> dict:
    """Start add-on.

    The caller of the function should handle HassioAPIError.
    """
    hassio: HassIO = hass.data[DOMAIN]
    command = f"/addons/{slug}/start"
    return await hassio.send_command(command, timeout=60)


@bind_hass
@api_data
async def async_restart_addon(hass: HomeAssistant, slug: str) -> dict:
    """Restart add-on.

    The caller of the function should handle HassioAPIError.
    """
    hassio: HassIO = hass.data[DOMAIN]
    command = f"/addons/{slug}/restart"
    return await hassio.send_command(command, timeout=None)


@bind_hass
@api_data
async def async_stop_addon(hass: HomeAssistant, slug: str) -> dict:
    """Stop add-on.

    The caller of the function should handle HassioAPIError.
    """
    hassio: HassIO = hass.data[DOMAIN]
    command = f"/addons/{slug}/stop"
    return await hassio.send_command(command, timeout=60)


@bind_hass
@api_data
async def async_set_addon_options(
    hass: HomeAssistant, slug: str, options: dict
) -> dict:
    """Set add-on options.

    The caller of the function should handle HassioAPIError.
    """
    hassio: HassIO = hass.data[DOMAIN]
    command = f"/addons/{slug}/options"
    return await hassio.send_command(command, payload=options)


@bind_hass
async def async_get_addon_discovery_info(hass: HomeAssistant, slug: str) -> dict | None:
    """Return discovery data for an add-on."""
    hassio: HassIO = hass.data[DOMAIN]
    data = await hassio.retrieve_discovery_messages()
    discovered_addons = data[ATTR_DISCOVERY]
    return next((addon for addon in discovered_addons if addon["addon"] == slug), None)


@bind_hass
@api_data
async def async_create_backup(
    hass: HomeAssistant, payload: dict, partial: bool = False
) -> dict:
    """Create a full or partial backup.

    The caller of the function should handle HassioAPIError.
    """
    hassio: HassIO = hass.data[DOMAIN]
    backup_type = "partial" if partial else "full"
    command = f"/backups/new/{backup_type}"
    return await hassio.send_command(command, payload=payload, timeout=None)


@bind_hass
@api_data
async def async_update_os(hass: HomeAssistant, version: str | None = None) -> dict:
    """Update Home Assistant Operating System.

    The caller of the function should handle HassioAPIError.
    """
    hassio: HassIO = hass.data[DOMAIN]
    command = "/os/update"
    return await hassio.send_command(
        command,
        payload={"version": version},
        timeout=None,
    )


@bind_hass
@api_data
async def async_update_supervisor(hass: HomeAssistant) -> dict:
    """Update Home Assistant Supervisor.

    The caller of the function should handle HassioAPIError.
    """
    hassio: HassIO = hass.data[DOMAIN]
    command = "/supervisor/update"
    return await hassio.send_command(command, timeout=None)


@bind_hass
@api_data
async def async_update_core(
    hass: HomeAssistant, version: str | None = None, backup: bool = False
) -> dict:
    """Update Home Assistant Core.

    The caller of the function should handle HassioAPIError.
    """
    hassio: HassIO = hass.data[DOMAIN]
    command = "/core/update"
    return await hassio.send_command(
        command,
        payload={"version": version, "backup": backup},
        timeout=None,
    )


@bind_hass
@_api_bool
async def async_apply_suggestion(hass: HomeAssistant, suggestion_uuid: str) -> dict:
    """Apply a suggestion from supervisor's resolution center."""
    hassio: HassIO = hass.data[DOMAIN]
    command = f"/resolution/suggestion/{suggestion_uuid}"
    return await hassio.send_command(command, timeout=None)


@api_data
async def async_get_green_settings(hass: HomeAssistant) -> dict[str, bool]:
    """Return settings specific to Home Assistant Green."""
    hassio: HassIO = hass.data[DOMAIN]
    return await hassio.send_command("/os/boards/green", method="get")


@api_data
async def async_set_green_settings(
    hass: HomeAssistant, settings: dict[str, bool]
) -> dict:
    """Set settings specific to Home Assistant Green.

    Returns an empty dict.
    """
    hassio: HassIO = hass.data[DOMAIN]
    return await hassio.send_command(
        "/os/boards/green", method="post", payload=settings
    )


@api_data
async def async_get_yellow_settings(hass: HomeAssistant) -> dict[str, bool]:
    """Return settings specific to Home Assistant Yellow."""
    hassio: HassIO = hass.data[DOMAIN]
    return await hassio.send_command("/os/boards/yellow", method="get")


@api_data
async def async_set_yellow_settings(
    hass: HomeAssistant, settings: dict[str, bool]
) -> dict:
    """Set settings specific to Home Assistant Yellow.

    Returns an empty dict.
    """
    hassio: HassIO = hass.data[DOMAIN]
    return await hassio.send_command(
        "/os/boards/yellow", method="post", payload=settings
    )


@api_data
async def async_reboot_host(hass: HomeAssistant) -> dict:
    """Reboot the host.

    Returns an empty dict.
    """
    hassio: HassIO = hass.data[DOMAIN]
    return await hassio.send_command("/host/reboot", method="post", timeout=60)


class HassIO:
    """Small API wrapper for Hass.io."""

    def __init__(
        self,
        loop: asyncio.AbstractEventLoop,
        websession: aiohttp.ClientSession,
        ip: str,
    ) -> None:
        """Initialize Hass.io API."""
        self.loop = loop
        self.websession = websession
        self._ip = ip
        self._base_url = URL(f"http://{ip}")

    @_api_bool
    def is_connected(self) -> Coroutine:
        """Return true if it connected to Hass.io supervisor.

        This method returns a coroutine.
        """
        return self.send_command("/supervisor/ping", method="get", timeout=15)

    @api_data
    def get_info(self) -> Coroutine:
        """Return generic Supervisor information.

        This method returns a coroutine.
        """
        return self.send_command("/info", method="get")

    @api_data
    def get_host_info(self) -> Coroutine:
        """Return data for Host.

        This method returns a coroutine.
        """
        return self.send_command("/host/info", method="get")

    @api_data
    def get_os_info(self) -> Coroutine:
        """Return data for the OS.

        This method returns a coroutine.
        """
        return self.send_command("/os/info", method="get")

    @api_data
    def get_core_info(self) -> Coroutine:
        """Return data for Home Asssistant Core.

        This method returns a coroutine.
        """
        return self.send_command("/core/info", method="get")

    @api_data
    def get_supervisor_info(self) -> Coroutine:
        """Return data for the Supervisor.

        This method returns a coroutine.
        """
        return self.send_command("/supervisor/info", method="get")

    @api_data
    def get_addon_info(self, addon: str) -> Coroutine:
        """Return data for a Add-on.

        This method returns a coroutine.
        """
        return self.send_command(f"/addons/{addon}/info", method="get")

    @api_data
    def get_core_stats(self) -> Coroutine:
        """Return stats for the core.

        This method returns a coroutine.
        """
        return self.send_command("/core/stats", method="get")

    @api_data
    def get_addon_stats(self, addon: str) -> Coroutine:
        """Return stats for an Add-on.

        This method returns a coroutine.
        """
        return self.send_command(f"/addons/{addon}/stats", method="get")

    @api_data
    def get_supervisor_stats(self) -> Coroutine:
        """Return stats for the supervisor.

        This method returns a coroutine.
        """
        return self.send_command("/supervisor/stats", method="get")

    def get_addon_changelog(self, addon: str) -> Coroutine:
        """Return changelog for an Add-on.

        This method returns a coroutine.
        """
        return self.send_command(
            f"/addons/{addon}/changelog", method="get", return_text=True
        )

    @api_data
    def get_store(self) -> Coroutine:
        """Return data from the store.

        This method returns a coroutine.
        """
        return self.send_command("/store", method="get")

    @api_data
    def get_ingress_panels(self) -> Coroutine:
        """Return data for Add-on ingress panels.

        This method returns a coroutine.
        """
        return self.send_command("/ingress/panels", method="get")

    @_api_bool
    def restart_homeassistant(self) -> Coroutine:
        """Restart Home-Assistant container.

        This method returns a coroutine.
        """
        return self.send_command("/homeassistant/restart")

    @_api_bool
    def stop_homeassistant(self) -> Coroutine:
        """Stop Home-Assistant container.

        This method returns a coroutine.
        """
        return self.send_command("/homeassistant/stop")

    @_api_bool
    def refresh_updates(self) -> Coroutine:
        """Refresh available updates.

        This method returns a coroutine.
        """
        return self.send_command("/refresh_updates", timeout=300)

    @api_data
    def retrieve_discovery_messages(self) -> Coroutine:
        """Return all discovery data from Hass.io API.

        This method returns a coroutine.
        """
        return self.send_command("/discovery", method="get", timeout=60)

    @api_data
    def get_discovery_message(self, uuid: str) -> Coroutine:
        """Return a single discovery data message.

        This method returns a coroutine.
        """
        return self.send_command(f"/discovery/{uuid}", method="get")

    @api_data
    def get_resolution_info(self) -> Coroutine:
        """Return data for Supervisor resolution center.

        This method returns a coroutine.
        """
        return self.send_command("/resolution/info", method="get")

    @api_data
    def get_suggestions_for_issue(
        self, issue_id: str
    ) -> Coroutine[Any, Any, dict[str, Any]]:
        """Return suggestions for issue from Supervisor resolution center.

        This method returns a coroutine.
        """
        return self.send_command(
            f"/resolution/issue/{issue_id}/suggestions", method="get"
        )

    @_api_bool
    async def update_hass_api(
        self, http_config: dict[str, Any], refresh_token: RefreshToken
    ):
        """Update Home Assistant API data on Hass.io."""
        port = http_config.get(CONF_SERVER_PORT) or SERVER_PORT
        options = {
            "ssl": CONF_SSL_CERTIFICATE in http_config,
            "port": port,
            "refresh_token": refresh_token.token,
        }

        if http_config.get(CONF_SERVER_HOST) is not None:
            options["watchdog"] = False
            _LOGGER.warning(
                "Found incompatible HTTP option 'server_host'. Watchdog feature"
                " disabled"
            )

        return await self.send_command("/homeassistant/options", payload=options)

    @_api_bool
    def update_hass_timezone(self, timezone: str) -> Coroutine:
        """Update Home-Assistant timezone data on Hass.io.

        This method returns a coroutine.
        """
        return self.send_command("/supervisor/options", payload={"timezone": timezone})

    @_api_bool
    def update_diagnostics(self, diagnostics: bool) -> Coroutine:
        """Update Supervisor diagnostics setting.

        This method returns a coroutine.
        """
        return self.send_command(
            "/supervisor/options", payload={"diagnostics": diagnostics}
        )

    @_api_bool
    def apply_suggestion(self, suggestion_uuid: str) -> Coroutine:
        """Apply a suggestion from supervisor's resolution center.

        This method returns a coroutine.
        """
        return self.send_command(f"/resolution/suggestion/{suggestion_uuid}")

    async def send_command(
        self,
        command: str,
        method: str = "post",
        payload: Any | None = None,
        timeout: int | None = 10,
        return_text: bool = False,
        *,
        source: str = "core.handler",
    ) -> Any:
        """Send API command to Hass.io.

        This method is a coroutine.
        """
        url = f"http://{self._ip}{command}"
        joined_url = self._base_url.join(URL(command))
        # This check is to make sure the normalized URL string
        # is the same as the URL string that was passed in. If
        # they are different, then the passed in command URL
        # contained characters that were removed by the normalization
        # such as ../../../../etc/passwd
        if url != str(joined_url):
            _LOGGER.error("Invalid request %s", command)
            raise HassioAPIError

        try:
            response = await self.websession.request(
                method,
                joined_url,
                json=payload,
                headers={
                    aiohttp.hdrs.AUTHORIZATION: (
                        f"Bearer {os.environ.get('SUPERVISOR_TOKEN', '')}"
                    ),
                    X_HASS_SOURCE: source,
                },
                timeout=aiohttp.ClientTimeout(total=timeout),
            )

            if response.status != HTTPStatus.OK:
                error = await response.json(encoding="utf-8")
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
