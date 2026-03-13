"""Config flow for the Solarwatt integration."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

from aiohttp.client_exceptions import ClientError
import voluptuous as vol
from yarl import URL

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import API_PATH, DEFAULT_PORT, DOMAIN

_LOGGER = logging.getLogger(__name__)


async def validate_input(
    hass: HomeAssistant,
    data: dict[str, Any],
) -> dict[str, Any]:
    """Validate the user input by talking to the Solarwatt device."""
    session = async_get_clientsession(hass)

    protocol = "http"
    url = URL.build(
        scheme=protocol,
        host=data[CONF_HOST],
        port=data[CONF_PORT],
        path=API_PATH,  # "/all"
    )

    _LOGGER.debug("Testing Solarwatt connection to %s", url)

    async with session.get(url) as resp:
        if resp.status != 200:
            body = await resp.text()
            raise ClientError(f"Solarwatt responded with HTTP {resp.status}: {body}")

        payload = await resp.json()

    # Extract serial from payload["ID"]["SN"], if present
    serial = None
    if isinstance(payload, dict):
        serial = (payload.get("ID") or {}).get("SN")

    if not serial:
        _LOGGER.debug(
            "Could not find serial number in Solarwatt payload; payload keys: %s",
            list(payload.keys()),
        )

    return {
        "serial": str(serial) if serial else None,
        "title": data[CONF_HOST],
    }


class SolarwattConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Solarwatt."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._data: dict[str, Any] = {
            CONF_HOST: "",
            CONF_PORT: DEFAULT_PORT,
        }

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self._data[CONF_HOST] = user_input[CONF_HOST]
            self._data[CONF_PORT] = user_input[CONF_PORT]

            try:
                info = await validate_input(self.hass, self._data)
            except ClientError:
                _LOGGER.exception("Error connecting to Solarwatt device")
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected error while validating Solarwatt config")
                errors["base"] = "unknown"
            else:
                serial = info.get("serial")

                if serial:
                    await self.async_set_unique_id(str(serial))
                    self._abort_if_unique_id_configured()
                else:
                    _LOGGER.debug("Proceeding without unique_id")
                    errors["base"] = "cannot_retrieve_device_info"

                return self.async_create_entry(
                    title=info["title"],
                    data=self._data,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST, default=self._data[CONF_HOST]): cv.string,
                    vol.Required(CONF_PORT, default=self._data[CONF_PORT]): cv.port,
                }
            ),
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle reauth."""
        entry = self._get_reauth_entry()
        return self.async_update_reload_and_abort(entry)
