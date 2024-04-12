"""Config flow for PrusaLink integration."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from awesomeversion import AwesomeVersion, AwesomeVersionException
from httpx import HTTPError, InvalidURL
from pyprusalink import PrusaLink
from pyprusalink.types import InvalidAuth, VersionInfo
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.httpx_client import get_async_client

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        # "maker" is currently hardcoded in the firmware
        # https://github.com/prusa3d/Prusa-Firmware-Buddy/blob/bfb0ffc745ee6546e7efdba618d0e7c0f4c909cd/lib/WUI/wui_api.h#L19
        vol.Required(CONF_USERNAME, default="maker"): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


def ensure_printer_is_supported(version: VersionInfo) -> None:
    """Raise NotSupported exception if the printer is not supported."""

    try:
        if AwesomeVersion("2.0.0") <= AwesomeVersion(version["api"]):
            return

        # Workaround to allow PrusaLink 0.7.2 on MK3 and MK2.5 that supports
        # the 2.0.0 API, but doesn't advertise it yet
        if version.get("original", "").startswith(
            ("PrusaLink I3MK3", "PrusaLink I3MK2")
        ) and AwesomeVersion("0.7.2") <= AwesomeVersion(version["server"]):
            return

    except AwesomeVersionException as err:
        raise NotSupported from err

    raise NotSupported


async def validate_input(hass: HomeAssistant, data: dict[str, str]) -> dict[str, str]:
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """
    api = PrusaLink(
        get_async_client(hass),
        data[CONF_HOST],
        data[CONF_USERNAME],
        data[CONF_PASSWORD],
    )

    try:
        async with asyncio.timeout(5):
            version = await api.get_version()

    except (TimeoutError, HTTPError, InvalidURL) as err:
        _LOGGER.error("Could not connect to PrusaLink: %s", err)
        raise CannotConnect from err

    ensure_printer_is_supported(version)

    return {"title": version["hostname"] or version["text"]}


class PrusaLinkConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for PrusaLink."""

    VERSION = 1
    MINOR_VERSION = 2

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=STEP_USER_DATA_SCHEMA
            )

        host = user_input[CONF_HOST].rstrip("/")
        if not host.startswith(("http://", "https://")):
            host = f"http://{host}"

        data = {
            CONF_HOST: host,
            CONF_USERNAME: user_input[CONF_USERNAME],
            CONF_PASSWORD: user_input[CONF_PASSWORD],
        }
        errors = {}

        try:
            info = await validate_input(self.hass, data)
        except CannotConnect:
            errors["base"] = "cannot_connect"
        except NotSupported:
            errors["base"] = "not_supported"
        except InvalidAuth:
            errors["base"] = "invalid_auth"
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            return self.async_create_entry(title=info["title"], data=data)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class NotSupported(HomeAssistantError):
    """Error to indicate we cannot connect."""
