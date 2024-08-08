"""Config flow to configure the IPP integration."""

from __future__ import annotations

import logging
from typing import Any

from pyipp import (
    IPP,
    IPPConnectionError,
    IPPConnectionUpgradeRequired,
    IPPError,
    IPPParseError,
    IPPResponseError,
    IPPVersionNotSupportedError,
)
import voluptuous as vol

from homeassistant.components import zeroconf
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PORT,
    CONF_SSL,
    CONF_UUID,
    CONF_VERIFY_SSL,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_BASE_PATH, CONF_SERIAL, DOMAIN

_LOGGER = logging.getLogger(__name__)


async def validate_input(hass: HomeAssistant, data: dict) -> dict[str, Any]:
    """Validate the user input allows us to connect.

    Data has the keys from DATA_SCHEMA with values provided by the user.
    """
    session = async_get_clientsession(hass)
    ipp = IPP(
        host=data[CONF_HOST],
        port=data[CONF_PORT],
        base_path=data[CONF_BASE_PATH],
        tls=data[CONF_SSL],
        verify_ssl=data[CONF_VERIFY_SSL],
        session=session,
    )

    printer = await ipp.printer()

    return {CONF_SERIAL: printer.info.serial, CONF_UUID: printer.info.uuid}


class IPPFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle an IPP config flow."""

    VERSION = 1

    def __init__(self) -> None:
        """Set up the instance."""
        self.discovery_info: dict[str, Any] = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initiated by the user."""
        if user_input is None:
            return self._show_setup_form()

        try:
            info = await validate_input(self.hass, user_input)
        except IPPConnectionUpgradeRequired:
            return self._show_setup_form({"base": "connection_upgrade"})
        except (IPPConnectionError, IPPResponseError):
            _LOGGER.debug("IPP Connection/Response Error", exc_info=True)
            return self._show_setup_form({"base": "cannot_connect"})
        except IPPParseError:
            _LOGGER.debug("IPP Parse Error", exc_info=True)
            return self.async_abort(reason="parse_error")
        except IPPVersionNotSupportedError:
            return self.async_abort(reason="ipp_version_error")
        except IPPError:
            _LOGGER.debug("IPP Error", exc_info=True)
            return self.async_abort(reason="ipp_error")

        unique_id = user_input[CONF_UUID] = info[CONF_UUID]

        if not unique_id and info[CONF_SERIAL]:
            _LOGGER.debug(
                "Printer UUID is missing from IPP response. Falling back to IPP serial"
                " number"
            )
            unique_id = info[CONF_SERIAL]
        elif not unique_id:
            _LOGGER.debug("Unable to determine unique id from IPP response")

        await self.async_set_unique_id(unique_id)
        self._abort_if_unique_id_configured(updates={CONF_HOST: user_input[CONF_HOST]})

        return self.async_create_entry(title=user_input[CONF_HOST], data=user_input)

    async def async_step_zeroconf(
        self, discovery_info: zeroconf.ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Handle zeroconf discovery."""
        host = discovery_info.host

        # Avoid probing devices that already have an entry
        self._async_abort_entries_match({CONF_HOST: host})

        port = discovery_info.port
        zctype = discovery_info.type
        name = discovery_info.name.replace(f".{zctype}", "")
        tls = zctype == "_ipps._tcp.local."
        base_path = discovery_info.properties.get("rp", "ipp/print")
        unique_id = discovery_info.properties.get("UUID")

        self.discovery_info.update(
            {
                CONF_HOST: host,
                CONF_PORT: port,
                CONF_SSL: tls,
                CONF_VERIFY_SSL: False,
                CONF_BASE_PATH: f"/{base_path}",
                CONF_NAME: name,
                CONF_UUID: unique_id,
            }
        )

        if unique_id:
            # If we already have the unique id, try to set it now
            # so we can avoid probing the device if its already
            # configured or ignored
            await self._async_set_unique_id_and_abort_if_already_configured(unique_id)

        self.context.update({"title_placeholders": {"name": name}})

        try:
            info = await validate_input(self.hass, self.discovery_info)
        except IPPConnectionUpgradeRequired:
            return self.async_abort(reason="connection_upgrade")
        except (IPPConnectionError, IPPResponseError):
            _LOGGER.debug("IPP Connection/Response Error", exc_info=True)
            return self.async_abort(reason="cannot_connect")
        except IPPParseError:
            _LOGGER.debug("IPP Parse Error", exc_info=True)
            return self.async_abort(reason="parse_error")
        except IPPVersionNotSupportedError:
            return self.async_abort(reason="ipp_version_error")
        except IPPError:
            _LOGGER.debug("IPP Error", exc_info=True)
            return self.async_abort(reason="ipp_error")

        if not unique_id and info[CONF_UUID]:
            _LOGGER.debug(
                "Printer UUID is missing from discovery info. Falling back to IPP UUID"
            )
            unique_id = self.discovery_info[CONF_UUID] = info[CONF_UUID]
        elif not unique_id and info[CONF_SERIAL]:
            _LOGGER.debug(
                "Printer UUID is missing from discovery info and IPP response. Falling"
                " back to IPP serial number"
            )
            unique_id = info[CONF_SERIAL]
        elif not unique_id:
            _LOGGER.debug(
                "Unable to determine unique id from discovery info and IPP response"
            )

        if unique_id and self.unique_id != unique_id:
            await self._async_set_unique_id_and_abort_if_already_configured(unique_id)

        await self._async_handle_discovery_without_unique_id()
        return await self.async_step_zeroconf_confirm()

    async def _async_set_unique_id_and_abort_if_already_configured(
        self, unique_id: str
    ) -> None:
        """Set the unique ID and abort if already configured."""
        await self.async_set_unique_id(unique_id)
        self._abort_if_unique_id_configured(
            updates={
                CONF_HOST: self.discovery_info[CONF_HOST],
                CONF_NAME: self.discovery_info[CONF_NAME],
            },
        )

    async def async_step_zeroconf_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a confirmation flow initiated by zeroconf."""
        if user_input is None:
            return self.async_show_form(
                step_id="zeroconf_confirm",
                description_placeholders={"name": self.discovery_info[CONF_NAME]},
                errors={},
            )

        return self.async_create_entry(
            title=self.discovery_info[CONF_NAME],
            data=self.discovery_info,
        )

    def _show_setup_form(self, errors: dict | None = None) -> ConfigFlowResult:
        """Show the setup form to the user."""
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST): str,
                    vol.Required(CONF_PORT, default=631): int,
                    vol.Required(CONF_BASE_PATH, default="/ipp/print"): str,
                    vol.Required(CONF_SSL, default=False): bool,
                    vol.Required(CONF_VERIFY_SSL, default=False): bool,
                }
            ),
            errors=errors or {},
        )
