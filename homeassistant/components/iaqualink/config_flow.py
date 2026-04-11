"""Config flow to configure zone component."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import httpx
from iaqualink.exception import (
    AqualinkServiceException,
    AqualinkServiceUnauthorizedException,
)
import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlowWithReload,
)
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv

from .const import CONF_SYSTEMS, DOMAIN
from .utils import async_get_aqualink_client

CREDENTIALS_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


async def async_get_systems(
    hass: HomeAssistant, username: str, password: str
) -> tuple[dict[str, Any] | None, str | None]:
    """Fetch systems from iAqualink and map failures to flow error reasons."""
    try:
        async with await async_get_aqualink_client(
            hass, username, password
        ) as aqualink:
            systems = await aqualink.get_systems()
    except AqualinkServiceUnauthorizedException:
        return None, "invalid_auth"
    except AqualinkServiceException, TimeoutError, httpx.HTTPError:
        return None, "cannot_connect"

    if not systems:
        return None, "no_systems"

    return systems, None


def _build_systems_schema(
    system_keys: dict[str, str], selected_systems: list[str]
) -> vol.Schema:
    """Build the schema used by both config and options flow system selection."""
    return vol.Schema(
        {
            vol.Optional(
                CONF_SYSTEMS,
                default=selected_systems,
            ): cv.multi_select(system_keys),
        }
    )


class AqualinkFlowHandler(ConfigFlow, domain=DOMAIN):
    """Aqualink config flow."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize flow state."""
        self._pending_user_input: dict[str, Any] | None = None
        self._system_keys: dict[str, str] | None = None

    async def _async_test_credentials(
        self, user_input: dict[str, Any]
    ) -> dict[str, str]:
        """Validate credentials against iAqualink."""
        try:
            async with await async_get_aqualink_client(
                self.hass, user_input[CONF_USERNAME], user_input[CONF_PASSWORD]
            ):
                pass
        except AqualinkServiceUnauthorizedException:
            return {"base": "invalid_auth"}
        except AqualinkServiceException, TimeoutError, httpx.HTTPError:
            return {"base": "cannot_connect"}

        return {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow start."""
        errors: dict[str, str] = {}

        if user_input is not None:
            errors = await self._async_test_credentials(user_input)
            if not errors:
                systems, systems_error = await async_get_systems(
                    self.hass,
                    user_input[CONF_USERNAME],
                    user_input[CONF_PASSWORD],
                )
                if systems is None:
                    assert systems_error is not None
                    errors = {"base": systems_error}
                else:
                    self._pending_user_input = user_input
                    self._system_keys = {
                        system.serial: system.name for system in systems.values()
                    }
                    return await self.async_step_systems()

        return self.async_show_form(
            step_id="user",
            data_schema=CREDENTIALS_DATA_SCHEMA,
            errors=errors,
        )

    async def async_step_systems(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle selecting which systems to include."""
        if self._pending_user_input is None or self._system_keys is None:
            return await self.async_step_user()

        if user_input is not None:
            return self.async_create_entry(
                title=self._pending_user_input[CONF_USERNAME],
                data=self._pending_user_input,
                options=user_input,
            )

        return self.async_show_form(
            step_id="systems",
            data_schema=_build_systems_schema(
                self._system_keys,
                list(self._system_keys.keys()),
            ),
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle flow triggered by an authentication failure."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle confirmation of reauthentication."""
        errors = {}

        reauth_entry = self._get_reauth_entry()
        if user_input is not None:
            errors = await self._async_test_credentials(user_input)
            if not errors:
                return self.async_update_reload_and_abort(
                    reauth_entry,
                    title=user_input[CONF_USERNAME],
                    data_updates={
                        CONF_USERNAME: user_input[CONF_USERNAME],
                        CONF_PASSWORD: user_input[CONF_PASSWORD],
                    },
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=CREDENTIALS_DATA_SCHEMA,
            errors=errors,
        )

    @staticmethod
    def async_get_options_flow(config_entry: ConfigEntry) -> AqualinkOptionsFlowHandler:
        """Create the options flow."""
        return AqualinkOptionsFlowHandler()


class AqualinkOptionsFlowHandler(OptionsFlowWithReload):
    """Options flow for Aqualink."""

    def __init__(self) -> None:
        """Initialize the options flow state."""
        self._system_keys: dict[str, str] | None = None

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage options."""
        if user_input is not None and self._system_keys is not None:
            return self.async_create_entry(title="", data=user_input)

        # Fetch systems from API
        username = self.config_entry.data[CONF_USERNAME]
        password = self.config_entry.data[CONF_PASSWORD]

        systems, error_reason = await async_get_systems(self.hass, username, password)

        if systems is None:
            assert error_reason is not None
            return self.async_show_form(
                step_id="init",
                data_schema=_build_systems_schema({}, []),
                errors={"base": error_reason},
            )

        # Build schema with all systems as selectable checkboxes
        self._system_keys = {system.serial: system.name for system in systems.values()}

        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        # Get currently selected systems from options (or default to all)
        current_systems = self.config_entry.options.get(
            CONF_SYSTEMS, list(self._system_keys.keys())
        )

        return self.async_show_form(
            step_id="init",
            data_schema=_build_systems_schema(self._system_keys, current_systems),
        )
