"""Config flow for Tesla Powerwall integration."""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
import logging
from typing import Any

from aiohttp import CookieJar
from tesla_powerwall import (
    AccessDeniedError,
    MissingAttributeError,
    Powerwall,
    PowerwallUnreachableError,
    SiteInfoResponse,
)
import voluptuous as vol

from homeassistant.components import dhcp
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigEntryState,
    ConfigFlow,
    ConfigFlowResult,
)
from homeassistant.const import CONF_IP_ADDRESS, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from homeassistant.util.network import is_ip_address

from . import async_last_update_was_successful
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


ENTRY_FAILURE_STATES = {
    ConfigEntryState.SETUP_ERROR,
    ConfigEntryState.SETUP_RETRY,
}


async def _login_and_fetch_site_info(
    power_wall: Powerwall, password: str
) -> tuple[SiteInfoResponse, str]:
    """Login to the powerwall and fetch the base info."""
    if password is not None:
        await power_wall.login(password)

    return await asyncio.gather(
        power_wall.get_site_info(), power_wall.get_gateway_din()
    )


async def _powerwall_is_reachable(ip_address: str, password: str) -> bool:
    """Check if the powerwall is reachable."""
    try:
        async with Powerwall(ip_address) as power_wall:
            await power_wall.login(password)
    except AccessDeniedError:
        return True
    except PowerwallUnreachableError:
        return False
    return True


async def validate_input(hass: HomeAssistant, data: dict[str, str]) -> dict[str, str]:
    """Validate the user input allows us to connect.

    Data has the keys from schema with values provided by the user.
    """
    session = async_create_clientsession(
        hass, verify_ssl=False, cookie_jar=CookieJar(unsafe=True)
    )
    async with Powerwall(data[CONF_IP_ADDRESS], http_session=session) as power_wall:
        password = data[CONF_PASSWORD]

        try:
            site_info, gateway_din = await _login_and_fetch_site_info(
                power_wall, password
            )
        except MissingAttributeError as err:
            # Only log the exception without the traceback
            _LOGGER.error(str(err))
            raise WrongVersion from err

        # Return info that you want to store in the config entry.
        return {"title": site_info.site_name, "unique_id": gateway_din.upper()}


class PowerwallConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Tesla Powerwall."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the powerwall flow."""
        self.ip_address: str | None = None
        self.title: str | None = None

    async def _async_powerwall_is_offline(self, entry: ConfigEntry) -> bool:
        """Check if the power wall is offline.

        We define offline by the config entry
        is in a failure/retry state or the updates
        are failing and the powerwall is unreachable
        since device may be updating.
        """
        ip_address = entry.data[CONF_IP_ADDRESS]
        password = entry.data[CONF_PASSWORD]
        return bool(
            entry.state in ENTRY_FAILURE_STATES
            or not async_last_update_was_successful(self.hass, entry)
        ) and not await _powerwall_is_reachable(ip_address, password)

    async def async_step_dhcp(
        self, discovery_info: dhcp.DhcpServiceInfo
    ) -> ConfigFlowResult:
        """Handle dhcp discovery."""
        self.ip_address = discovery_info.ip
        gateway_din = discovery_info.hostname.upper()
        # The hostname is the gateway_din (unique_id)
        await self.async_set_unique_id(gateway_din)
        for entry in self._async_current_entries(include_ignore=False):
            if entry.data[CONF_IP_ADDRESS] == discovery_info.ip:
                if entry.unique_id is not None and is_ip_address(entry.unique_id):
                    if self.hass.config_entries.async_update_entry(
                        entry, unique_id=gateway_din
                    ):
                        self.hass.config_entries.async_schedule_reload(entry.entry_id)
                return self.async_abort(reason="already_configured")
            if entry.unique_id == gateway_din:
                if await self._async_powerwall_is_offline(entry):
                    if self.hass.config_entries.async_update_entry(
                        entry, data={**entry.data, CONF_IP_ADDRESS: self.ip_address}
                    ):
                        self.hass.config_entries.async_schedule_reload(entry.entry_id)
                return self.async_abort(reason="already_configured")
        # Still need to abort for ignored entries
        self._abort_if_unique_id_configured()
        self.context["title_placeholders"] = {
            "name": gateway_din,
            "ip_address": self.ip_address,
        }
        errors, info, _ = await self._async_try_connect(
            {CONF_IP_ADDRESS: self.ip_address, CONF_PASSWORD: gateway_din[-5:]}
        )
        if errors:
            if CONF_PASSWORD in errors:
                # The default password is the gateway din last 5
                # if it does not work, we have to ask
                return await self.async_step_user()
            return self.async_abort(reason="cannot_connect")
        assert info is not None
        self.title = info["title"]
        return await self.async_step_confirm_discovery()

    async def _async_try_connect(
        self, user_input: dict[str, Any]
    ) -> tuple[dict[str, Any] | None, dict[str, str] | None, dict[str, str]]:
        """Try to connect to the powerwall."""
        info = None
        errors: dict[str, str] = {}
        description_placeholders: dict[str, str] = {}
        try:
            info = await validate_input(self.hass, user_input)
        except (PowerwallUnreachableError, TimeoutError) as ex:
            errors[CONF_IP_ADDRESS] = "cannot_connect"
            description_placeholders = {"error": str(ex)}
        except WrongVersion as ex:
            errors["base"] = "wrong_version"
            description_placeholders = {"error": str(ex)}
        except AccessDeniedError as ex:
            errors[CONF_PASSWORD] = "invalid_auth"
            description_placeholders = {"error": str(ex)}
        except Exception as ex:
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
            description_placeholders = {"error": str(ex)}

        return errors, info, description_placeholders

    async def async_step_confirm_discovery(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm a discovered powerwall."""
        assert self.ip_address is not None
        assert self.title is not None
        assert self.unique_id is not None
        if user_input is not None:
            return self.async_create_entry(
                title=self.title,
                data={
                    CONF_IP_ADDRESS: self.ip_address,
                    CONF_PASSWORD: self.unique_id[-5:],
                },
            )

        self._set_confirm_only()
        self.context["title_placeholders"] = {
            "name": self.title,
            "ip_address": self.ip_address,
        }
        return self.async_show_form(
            step_id="confirm_discovery",
            description_placeholders={
                "name": self.title,
                "ip_address": self.ip_address,
            },
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] | None = {}
        description_placeholders: dict[str, str] = {}
        if user_input is not None:
            errors, info, description_placeholders = await self._async_try_connect(
                user_input
            )
            if not errors:
                assert info is not None
                if info["unique_id"]:
                    await self.async_set_unique_id(
                        info["unique_id"], raise_on_progress=False
                    )
                    self._abort_if_unique_id_configured(
                        updates={CONF_IP_ADDRESS: user_input[CONF_IP_ADDRESS]}
                    )
                self._async_abort_entries_match({CONF_IP_ADDRESS: self.ip_address})
                return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_IP_ADDRESS, default=self.ip_address): str,
                    vol.Optional(CONF_PASSWORD): str,
                }
            ),
            errors=errors,
            description_placeholders=description_placeholders,
        )

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reauth confirmation."""
        errors: dict[str, str] | None = {}
        description_placeholders: dict[str, str] = {}
        reauth_entry = self._get_reauth_entry()
        if user_input is not None:
            errors, _, description_placeholders = await self._async_try_connect(
                {CONF_IP_ADDRESS: reauth_entry.data[CONF_IP_ADDRESS], **user_input}
            )
            if not errors:
                return self.async_update_reload_and_abort(
                    reauth_entry, data_updates=user_input
                )

        self.context["title_placeholders"] = {
            "name": reauth_entry.title,
            "ip_address": reauth_entry.data[CONF_IP_ADDRESS],
        }
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Optional(CONF_PASSWORD): str}),
            errors=errors,
            description_placeholders=description_placeholders,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle configuration by re-auth."""
        return await self.async_step_reauth_confirm()


class WrongVersion(HomeAssistantError):
    """Error indicating we cannot interact with the powerwall software version."""
