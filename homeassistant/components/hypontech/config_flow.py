"""Config flow for the Hypontech Cloud integration."""

from collections.abc import Mapping
import logging
from typing import Any, override

from hyponcloud import KNOWN_OEMS, AdminInfo, AuthenticationError, HyponCloud
import voluptuous as vol

from homeassistant.config_entries import SOURCE_USER, ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .const import CONF_OEM, DEFAULT_OEM, DOMAIN

_LOGGER = logging.getLogger(__name__)

OEM_OPTIONS = [
    SelectOptionDict(value=str(oem.id), label=f"{oem.name} ({oem.monitoring_url})")
    for oem in KNOWN_OEMS
]

STEP_REAUTH_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


def _data_schema(default_oem: int = DEFAULT_OEM) -> vol.Schema:
    """Return the config flow data schema."""
    return vol.Schema(
        {
            vol.Required(CONF_USERNAME): str,
            vol.Required(CONF_PASSWORD): str,
            vol.Required(CONF_OEM, default=str(default_oem)): SelectSelector(
                SelectSelectorConfig(
                    options=OEM_OPTIONS,
                    mode=SelectSelectorMode.DROPDOWN,
                )
            ),
        }
    )


def _entry_data(user_input: Mapping[str, Any]) -> dict[str, Any]:
    """Normalize config entry data from user input."""
    return {**user_input, CONF_OEM: int(user_input[CONF_OEM])}


def _unique_id(account_id: str, oem: int) -> str:
    """Return a backwards-compatible unique id for the account and OEM."""
    if oem == DEFAULT_OEM:
        return account_id
    return f"{oem}:{account_id}"


class HypontechConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Hypontech Cloud."""

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._default_oem = DEFAULT_OEM

    async def _async_validate_input(
        self, entry_data: Mapping[str, Any]
    ) -> tuple[AdminInfo | None, dict[str, str]]:
        """Validate user input."""
        errors: dict[str, str] = {}
        session = async_get_clientsession(self.hass)
        hypon = HyponCloud(
            entry_data[CONF_USERNAME],
            entry_data[CONF_PASSWORD],
            session,
            oem=entry_data[CONF_OEM],
        )
        try:
            await hypon.connect()
            return await hypon.get_admin_info(), errors
        except AuthenticationError:
            errors["base"] = "invalid_auth"
        except TimeoutError, ConnectionError:
            errors["base"] = "cannot_connect"
        except Exception:
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        return None, errors

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        default_oem = self._default_oem
        if user_input is not None:
            entry_data = _entry_data(user_input)
            default_oem = entry_data[CONF_OEM]
            admin_info, errors = await self._async_validate_input(entry_data)
            if admin_info is not None:
                await self.async_set_unique_id(
                    _unique_id(admin_info.id, entry_data[CONF_OEM])
                )
                if self.source == SOURCE_USER:
                    self._abort_if_unique_id_configured()
                    return self.async_create_entry(
                        title=entry_data[CONF_USERNAME],
                        data=entry_data,
                    )
                self._abort_if_unique_id_mismatch(reason="wrong_account")
                return self.async_update_reload_and_abort(
                    self._get_reauth_entry(),
                    data_updates={
                        CONF_USERNAME: entry_data[CONF_USERNAME],
                        CONF_PASSWORD: entry_data[CONF_PASSWORD],
                    },
                )

        return self.async_show_form(
            step_id="user", data_schema=_data_schema(default_oem), errors=errors
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle reauthentication."""
        self._default_oem = int(entry_data.get(CONF_OEM, DEFAULT_OEM))
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reauthentication confirmation."""
        errors: dict[str, str] = {}
        if user_input is not None:
            entry_data = {**user_input, CONF_OEM: self._default_oem}
            admin_info, errors = await self._async_validate_input(entry_data)
            if admin_info is not None:
                await self.async_set_unique_id(
                    _unique_id(admin_info.id, entry_data[CONF_OEM])
                )
                self._abort_if_unique_id_mismatch(reason="wrong_account")
                return self.async_update_reload_and_abort(
                    self._get_reauth_entry(),
                    data_updates={
                        CONF_USERNAME: entry_data[CONF_USERNAME],
                        CONF_PASSWORD: entry_data[CONF_PASSWORD],
                    },
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=STEP_REAUTH_DATA_SCHEMA,
            errors=errors,
        )
