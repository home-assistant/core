"""Config flow for Bosch Alarm integration."""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
import logging
import ssl
from typing import Any, Self

from bosch_alarm_mode2 import Panel
import voluptuous as vol

from homeassistant.config_entries import (
    SOURCE_DHCP,
    SOURCE_RECONFIGURE,
    SOURCE_USER,
    ConfigEntryState,
    ConfigFlow,
    ConfigFlowResult,
)
from homeassistant.const import (
    CONF_CODE,
    CONF_HOST,
    CONF_MAC,
    CONF_MODEL,
    CONF_PASSWORD,
    CONF_PORT,
)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo

from .const import CONF_INSTALLER_CODE, CONF_USER_CODE, DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_PORT, default=7700): cv.positive_int,
    }
)

STEP_AUTH_DATA_SCHEMA_SOLUTION = vol.Schema(
    {
        vol.Required(CONF_USER_CODE): str,
    }
)

STEP_AUTH_DATA_SCHEMA_AMAX = vol.Schema(
    {
        vol.Required(CONF_INSTALLER_CODE): str,
        vol.Required(CONF_PASSWORD): str,
    }
)

STEP_AUTH_DATA_SCHEMA_BG = vol.Schema(
    {
        vol.Required(CONF_PASSWORD): str,
    }
)

STEP_INIT_DATA_SCHEMA = vol.Schema({vol.Optional(CONF_CODE): str})


async def try_connect(
    data: dict[str, Any], load_selector: int = 0
) -> tuple[str, int | None]:
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """
    panel = Panel(
        host=data[CONF_HOST],
        port=data[CONF_PORT],
        automation_code=data.get(CONF_PASSWORD),
        installer_or_user_code=data.get(CONF_INSTALLER_CODE, data.get(CONF_USER_CODE)),
    )

    try:
        await panel.connect(load_selector)
    finally:
        await panel.disconnect()

    return (panel.model, panel.serial_number)


class BoschAlarmConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Bosch Alarm."""

    def __init__(self) -> None:
        """Init config flow."""

        self._data: dict[str, Any] = {}
        self.mac: str | None = None
        self.host: str | None = None

    def is_matching(self, other_flow: Self) -> bool:
        """Return True if other_flow is matching this flow."""
        return self.mac == other_flow.mac or self.host == other_flow.host

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self.host = user_input[CONF_HOST]
            if self.source == SOURCE_USER:
                self._async_abort_entries_match({CONF_HOST: user_input[CONF_HOST]})
            try:
                # Use load_selector = 0 to fetch the panel model without authentication.
                (model, _) = await try_connect(user_input, 0)
            except (
                OSError,
                ConnectionRefusedError,
                ssl.SSLError,
                asyncio.exceptions.TimeoutError,
            ) as e:
                _LOGGER.error("Connection Error: %s", e)
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                self._data = user_input
                self._data[CONF_MODEL] = model

                if self.source == SOURCE_RECONFIGURE:
                    if (
                        self._get_reconfigure_entry().data[CONF_MODEL]
                        != self._data[CONF_MODEL]
                    ):
                        return self.async_abort(reason="device_mismatch")
                return await self.async_step_auth()
        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_DATA_SCHEMA, user_input
            ),
            errors=errors,
        )

    async def async_step_dhcp(
        self, discovery_info: DhcpServiceInfo
    ) -> ConfigFlowResult:
        """Handle DHCP discovery."""
        self.mac = format_mac(discovery_info.macaddress)
        self.host = discovery_info.ip
        if self.hass.config_entries.flow.async_has_matching_flow(self):
            return self.async_abort(reason="already_in_progress")

        for entry in self.hass.config_entries.async_entries(DOMAIN):
            if entry.data.get(CONF_MAC) == self.mac:
                result = self.hass.config_entries.async_update_entry(
                    entry,
                    data={
                        **entry.data,
                        CONF_HOST: discovery_info.ip,
                    },
                )
                if result:
                    self.hass.config_entries.async_schedule_reload(entry.entry_id)
                return self.async_abort(reason="already_configured")
            if entry.data[CONF_HOST] == discovery_info.ip:
                if (
                    not entry.data.get(CONF_MAC)
                    and entry.state == ConfigEntryState.LOADED
                ):
                    result = self.hass.config_entries.async_update_entry(
                        entry,
                        data={
                            **entry.data,
                            CONF_MAC: self.mac,
                        },
                    )
                    if result:
                        self.hass.config_entries.async_schedule_reload(entry.entry_id)
                return self.async_abort(reason="already_configured")
        try:
            # Use load_selector = 0 to fetch the panel model without authentication.
            (model, _) = await try_connect(
                {CONF_HOST: discovery_info.ip, CONF_PORT: 7700}, 0
            )
        except (
            OSError,
            ConnectionRefusedError,
            ssl.SSLError,
            asyncio.exceptions.TimeoutError,
        ):
            return self.async_abort(reason="cannot_connect")
        except Exception:
            _LOGGER.exception("Unexpected exception")
            return self.async_abort(reason="unknown")
        self.context["title_placeholders"] = {
            "model": model,
            "host": discovery_info.ip,
        }
        self._data = {
            CONF_HOST: discovery_info.ip,
            CONF_MAC: self.mac,
            CONF_MODEL: model,
            CONF_PORT: 7700,
        }

        return await self.async_step_auth()

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the reconfigure step."""
        return await self.async_step_user()

    async def async_step_auth(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the auth step."""
        errors: dict[str, str] = {}

        # Each model variant requires a different authentication flow
        if "Solution" in self._data[CONF_MODEL]:
            schema = STEP_AUTH_DATA_SCHEMA_SOLUTION
        elif "AMAX" in self._data[CONF_MODEL]:
            schema = STEP_AUTH_DATA_SCHEMA_AMAX
        else:
            schema = STEP_AUTH_DATA_SCHEMA_BG

        if user_input is not None:
            self._data.update(user_input)
            try:
                (model, serial_number) = await try_connect(
                    self._data, Panel.LOAD_EXTENDED_INFO
                )
            except (PermissionError, ValueError) as e:
                errors["base"] = "invalid_auth"
                _LOGGER.error("Authentication Error: %s", e)
            except (
                OSError,
                ConnectionRefusedError,
                ssl.SSLError,
                TimeoutError,
            ) as e:
                _LOGGER.error("Connection Error: %s", e)
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                if serial_number:
                    await self.async_set_unique_id(str(serial_number))
                if self.source in (SOURCE_USER, SOURCE_DHCP):
                    if serial_number:
                        self._abort_if_unique_id_configured()
                    else:
                        self._async_abort_entries_match(
                            {CONF_HOST: self._data[CONF_HOST]}
                        )
                    return self.async_create_entry(
                        title=f"Bosch {model}", data=self._data
                    )
                if serial_number:
                    self._abort_if_unique_id_mismatch(reason="device_mismatch")

                return self.async_update_reload_and_abort(
                    self._get_reconfigure_entry(),
                    data=self._data,
                )

        return self.async_show_form(
            step_id="auth",
            data_schema=self.add_suggested_values_to_schema(schema, user_input),
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Perform reauth upon an authentication error."""
        self._data = dict(entry_data)
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the reauth step."""
        errors: dict[str, str] = {}

        # Each model variant requires a different authentication flow
        if "Solution" in self._data[CONF_MODEL]:
            schema = STEP_AUTH_DATA_SCHEMA_SOLUTION
        elif "AMAX" in self._data[CONF_MODEL]:
            schema = STEP_AUTH_DATA_SCHEMA_AMAX
        else:
            schema = STEP_AUTH_DATA_SCHEMA_BG

        if user_input is not None:
            reauth_entry = self._get_reauth_entry()
            self._data.update(user_input)
            try:
                (_, _) = await try_connect(self._data, Panel.LOAD_EXTENDED_INFO)
            except (PermissionError, ValueError) as e:
                errors["base"] = "invalid_auth"
                _LOGGER.error("Authentication Error: %s", e)
            except (
                OSError,
                ConnectionRefusedError,
                ssl.SSLError,
                TimeoutError,
            ) as e:
                _LOGGER.error("Connection Error: %s", e)
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_update_reload_and_abort(
                    reauth_entry,
                    data_updates=user_input,
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=self.add_suggested_values_to_schema(schema, user_input),
            errors=errors,
        )
