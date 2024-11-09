"""Config flow for Tesla Wall Connector integration."""

from __future__ import annotations

import logging
from typing import Any

from tesla_wall_connector import WallConnector
from tesla_wall_connector.exceptions import WallConnectorError
import voluptuous as vol

from homeassistant.components import dhcp
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN, WALLCONNECTOR_DEVICE_NAME, WALLCONNECTOR_SERIAL_NUMBER

_LOGGER = logging.getLogger(__name__)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """
    wall_connector = WallConnector(
        host=data[CONF_HOST], session=async_get_clientsession(hass)
    )

    version = await wall_connector.async_get_version()

    return {
        "title": WALLCONNECTOR_DEVICE_NAME,
        WALLCONNECTOR_SERIAL_NUMBER: version.serial_number,
    }


class TeslaWallConnectorConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Tesla Wall Connector."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize config flow."""
        super().__init__()
        self.ip_address: str | None = None

    async def async_step_dhcp(
        self, discovery_info: dhcp.DhcpServiceInfo
    ) -> ConfigFlowResult:
        """Handle dhcp discovery."""
        self.ip_address = discovery_info.ip
        _LOGGER.debug("Discovered Tesla Wall Connector at [%s]", self.ip_address)

        self._async_abort_entries_match({CONF_HOST: self.ip_address})

        try:
            wall_connector = WallConnector(
                host=self.ip_address, session=async_get_clientsession(self.hass)
            )
            version = await wall_connector.async_get_version()
        except WallConnectorError as ex:
            _LOGGER.debug(
                "Could not read serial number from Tesla WallConnector at [%s]: [%s]",
                self.ip_address,
                ex,
            )
            return self.async_abort(reason="cannot_connect")

        serial_number: str = version.serial_number

        await self.async_set_unique_id(serial_number)
        self._abort_if_unique_id_configured(updates={CONF_HOST: self.ip_address})

        _LOGGER.debug(
            "No entry found for wall connector with IP %s. Serial nr: %s",
            self.ip_address,
            serial_number,
        )

        self.context["title_placeholders"] = {
            CONF_HOST: self.ip_address,
            WALLCONNECTOR_SERIAL_NUMBER: serial_number,
        }
        return await self.async_step_user()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        data_schema = vol.Schema(
            {vol.Required(CONF_HOST, default=self.ip_address): str}
        )
        if user_input is None:
            return self.async_show_form(step_id="user", data_schema=data_schema)
        errors = {}

        try:
            info = await validate_input(self.hass, user_input)
        except WallConnectorError:
            errors["base"] = "cannot_connect"
        except Exception:
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"

        if not errors:
            await self.async_set_unique_id(
                unique_id=info[WALLCONNECTOR_SERIAL_NUMBER], raise_on_progress=True
            )
            self._abort_if_unique_id_configured(
                updates=user_input, reload_on_update=True
            )

            return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=data_schema, errors=errors
        )
