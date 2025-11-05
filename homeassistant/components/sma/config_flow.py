"""Config flow for the sma integration."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

import attrs
from pysma import (
    SmaAuthenticationException,
    SmaConnectionException,
    SmaReadException,
    SMAWebConnect,
)
import voluptuous as vol
from yarl import URL

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import (
    CONF_HOST,
    CONF_MAC,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_SSL,
    CONF_VERIFY_SSL,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo

from .const import CONF_GROUP, DOMAIN, GROUPS

_LOGGER = logging.getLogger(__name__)


async def validate_input(
    hass: HomeAssistant,
    user_input: dict[str, Any],
    data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Validate the user input allows us to connect."""
    session = async_get_clientsession(hass, verify_ssl=user_input[CONF_VERIFY_SSL])

    protocol = "https" if user_input[CONF_SSL] else "http"
    host = data[CONF_HOST] if data is not None else user_input[CONF_HOST]
    url = URL.build(scheme=protocol, host=host)

    sma = SMAWebConnect(
        session, str(url), user_input[CONF_PASSWORD], group=user_input[CONF_GROUP]
    )

    # new_session raises SmaAuthenticationException on failure
    await sma.new_session()
    device_info = await sma.device_info()
    await sma.close_session()

    return attrs.asdict(device_info)


class SmaConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for SMA."""

    VERSION = 1
    MINOR_VERSION = 2

    def __init__(self) -> None:
        """Initialize."""
        self._data: dict[str, Any] = {
            CONF_HOST: vol.UNDEFINED,
            CONF_SSL: False,
            CONF_VERIFY_SSL: True,
            CONF_GROUP: GROUPS[0],
            CONF_PASSWORD: vol.UNDEFINED,
        }
        self._discovery_data: dict[str, Any] = {}

    async def _handle_user_input(
        self, user_input: dict[str, Any], discovery: bool = False
    ) -> tuple[dict[str, str], dict[str, str]]:
        """Handle the user input."""
        errors: dict[str, str] = {}
        device_info: dict[str, str] = {}

        if not discovery:
            self._data[CONF_HOST] = user_input[CONF_HOST]

        self._data[CONF_SSL] = user_input[CONF_SSL]
        self._data[CONF_VERIFY_SSL] = user_input[CONF_VERIFY_SSL]
        self._data[CONF_GROUP] = user_input[CONF_GROUP]
        self._data[CONF_PASSWORD] = user_input[CONF_PASSWORD]

        try:
            device_info = await validate_input(
                self.hass, user_input=user_input, data=self._data
            )
        except SmaConnectionException:
            errors["base"] = "cannot_connect"
        except SmaAuthenticationException:
            errors["base"] = "invalid_auth"
        except SmaReadException:
            errors["base"] = "cannot_retrieve_device_info"
        except Exception:
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"

        return errors, device_info

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """First step in config flow."""
        errors: dict[str, str] = {}
        if user_input is not None:
            errors, device_info = await self._handle_user_input(user_input=user_input)

            if not errors:
                await self.async_set_unique_id(
                    str(device_info["serial"]), raise_on_progress=False
                )
                self._abort_if_unique_id_configured(updates=self._data)

                return self.async_create_entry(
                    title=self._data[CONF_HOST], data=self._data
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST, default=self._data[CONF_HOST]): cv.string,
                    vol.Optional(CONF_SSL, default=self._data[CONF_SSL]): cv.boolean,
                    vol.Optional(
                        CONF_VERIFY_SSL, default=self._data[CONF_VERIFY_SSL]
                    ): cv.boolean,
                    vol.Optional(CONF_GROUP, default=self._data[CONF_GROUP]): vol.In(
                        GROUPS
                    ),
                    vol.Required(CONF_PASSWORD): cv.string,
                }
            ),
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle reauth on credential failure."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Prepare reauth."""
        errors: dict[str, str] = {}
        if user_input is not None:
            reauth_entry = self._get_reauth_entry()
            errors, _device_info = await self._handle_user_input(
                user_input={
                    **reauth_entry.data,
                    CONF_PASSWORD: user_input[CONF_PASSWORD],
                }
            )

            if not errors:
                return self.async_update_reload_and_abort(
                    reauth_entry,
                    data_updates={CONF_PASSWORD: user_input[CONF_PASSWORD]},
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_PASSWORD): cv.string,
                }
            ),
            errors=errors,
        )

    async def async_step_dhcp(
        self, discovery_info: DhcpServiceInfo
    ) -> ConfigFlowResult:
        """Handle DHCP discovery."""
        self._discovery_data[CONF_HOST] = discovery_info.ip
        self._discovery_data[CONF_MAC] = format_mac(discovery_info.macaddress)
        self._discovery_data[CONF_NAME] = discovery_info.hostname
        self._data[CONF_HOST] = discovery_info.ip
        self._data[CONF_MAC] = format_mac(self._discovery_data[CONF_MAC])

        _LOGGER.debug(
            "DHCP discovery detected SMA device: %s, IP: %s, MAC: %s",
            self._discovery_data[CONF_NAME],
            self._discovery_data[CONF_HOST],
            self._discovery_data[CONF_MAC],
        )

        existing_entries_with_host = [
            entry
            for entry in self._async_current_entries(include_ignore=False)
            if entry.data.get(CONF_HOST) == self._data[CONF_HOST]
            and not entry.data.get(CONF_MAC)
        ]

        # If we have an existing entry with the same host but no MAC address,
        # we update the entry with the MAC address and reload it.
        if existing_entries_with_host:
            entry = existing_entries_with_host[0]
            self.async_update_reload_and_abort(
                entry, data_updates={CONF_MAC: self._data[CONF_MAC]}
            )

        # Finally, check if the hostname (which represents the SMA serial number) is unique
        serial_number = discovery_info.hostname.lower()
        # Example hostname: sma12345678-01
        # Remove 'sma' prefix and strip everything after the dash (including the dash)
        if serial_number.startswith("sma"):
            serial_number = serial_number.removeprefix("sma")
        serial_number = serial_number.split("-", 1)[0]
        await self.async_set_unique_id(serial_number)
        self._abort_if_unique_id_configured()

        return await self.async_step_discovery_confirm()

    async def async_step_discovery_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm discovery."""
        errors: dict[str, str] = {}
        if user_input is not None:
            errors, _device_info = await self._handle_user_input(
                user_input=user_input, discovery=True
            )

            if not errors:
                return self.async_create_entry(
                    title=self._data[CONF_HOST], data=self._data
                )

        return self.async_show_form(
            step_id="discovery_confirm",
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_SSL, default=self._data[CONF_SSL]): cv.boolean,
                    vol.Optional(
                        CONF_VERIFY_SSL, default=self._data[CONF_VERIFY_SSL]
                    ): cv.boolean,
                    vol.Optional(CONF_GROUP, default=self._data[CONF_GROUP]): vol.In(
                        GROUPS
                    ),
                    vol.Required(CONF_PASSWORD): cv.string,
                }
            ),
            description_placeholders={CONF_HOST: self._data[CONF_HOST]},
            errors=errors,
        )
