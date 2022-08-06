"""Config flow for Tesla Powerwall integration."""
from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

from tesla_powerwall import (
    AccessDeniedError,
    MissingAttributeError,
    Powerwall,
    PowerwallUnreachableError,
    SiteInfo,
)
import voluptuous as vol

from homeassistant import config_entries, core, exceptions
from homeassistant.components import dhcp
from homeassistant.const import CONF_IP_ADDRESS, CONF_PASSWORD
from homeassistant.data_entry_flow import FlowResult
from homeassistant.util.network import is_ip_address

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


def _login_and_fetch_site_info(
    power_wall: Powerwall, password: str
) -> tuple[SiteInfo, str]:
    """Login to the powerwall and fetch the base info."""
    if password is not None:
        power_wall.login(password)
    return power_wall.get_site_info(), power_wall.get_gateway_din()


async def validate_input(
    hass: core.HomeAssistant, data: dict[str, str]
) -> dict[str, str]:
    """Validate the user input allows us to connect.

    Data has the keys from schema with values provided by the user.
    """

    power_wall = Powerwall(data[CONF_IP_ADDRESS])
    password = data[CONF_PASSWORD]

    try:
        site_info, gateway_din = await hass.async_add_executor_job(
            _login_and_fetch_site_info, power_wall, password
        )
    except MissingAttributeError as err:
        # Only log the exception without the traceback
        _LOGGER.error(str(err))
        raise WrongVersion from err

    # Return info that you want to store in the config entry.
    return {"title": site_info.site_name, "unique_id": gateway_din.upper()}


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Tesla Powerwall."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the powerwall flow."""
        self.ip_address: str | None = None
        self.title: str | None = None
        self.reauth_entry: config_entries.ConfigEntry | None = None

    async def async_step_dhcp(self, discovery_info: dhcp.DhcpServiceInfo) -> FlowResult:
        """Handle dhcp discovery."""
        self.ip_address = discovery_info.ip
        gateway_din = discovery_info.hostname.upper()
        # The hostname is the gateway_din (unique_id)
        await self.async_set_unique_id(gateway_din)
        self._abort_if_unique_id_configured(updates={CONF_IP_ADDRESS: self.ip_address})
        for entry in self._async_current_entries(include_ignore=False):
            if entry.data[CONF_IP_ADDRESS] == discovery_info.ip:
                if entry.unique_id is not None and is_ip_address(entry.unique_id):
                    if self.hass.config_entries.async_update_entry(
                        entry, unique_id=gateway_din
                    ):
                        self.hass.async_create_task(
                            self.hass.config_entries.async_reload(entry.entry_id)
                        )
                return self.async_abort(reason="already_configured")
        self.context["title_placeholders"] = {
            "name": gateway_din,
            "ip_address": self.ip_address,
        }
        errors, info = await self._async_try_connect(
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
    ) -> tuple[dict[str, Any] | None, dict[str, str] | None]:
        """Try to connect to the powerwall."""
        info = None
        errors: dict[str, str] = {}
        try:
            info = await validate_input(self.hass, user_input)
        except PowerwallUnreachableError:
            errors[CONF_IP_ADDRESS] = "cannot_connect"
        except WrongVersion:
            errors["base"] = "wrong_version"
        except AccessDeniedError:
            errors[CONF_PASSWORD] = "invalid_auth"
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"

        return errors, info

    async def async_step_confirm_discovery(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Confirm a discovered powerwall."""
        assert self.ip_address is not None
        assert self.unique_id is not None
        if user_input is not None:
            assert self.title is not None
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
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] | None = {}
        if user_input is not None:
            errors, info = await self._async_try_connect(user_input)
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
        )

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle reauth confirmation."""
        assert self.reauth_entry is not None
        errors: dict[str, str] | None = {}
        if user_input is not None:
            entry_data = self.reauth_entry.data
            errors, _ = await self._async_try_connect(
                {CONF_IP_ADDRESS: entry_data[CONF_IP_ADDRESS], **user_input}
            )
            if not errors:
                self.hass.config_entries.async_update_entry(
                    self.reauth_entry, data={**entry_data, **user_input}
                )
                await self.hass.config_entries.async_reload(self.reauth_entry.entry_id)
                return self.async_abort(reason="reauth_successful")

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Optional(CONF_PASSWORD): str}),
            errors=errors,
        )

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> FlowResult:
        """Handle configuration by re-auth."""
        self.reauth_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        return await self.async_step_reauth_confirm()


class WrongVersion(exceptions.HomeAssistantError):
    """Error to indicate the powerwall uses a software version we cannot interact with."""
