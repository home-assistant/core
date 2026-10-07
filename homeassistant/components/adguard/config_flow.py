"""Config flow to configure the AdGuard Home integration."""

from collections.abc import Mapping
from typing import Any, override

from adguardhome import (
    AdGuardHome,
    AdGuardHomeAuthenticationError,
    AdGuardHomeConnectionError,
    AdGuardHomeError,
)
import probatio
from yarl import URL

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SSL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.service_info.hassio import HassioServiceInfo

from .const import DOMAIN, LOGGER


async def _async_validate_connection(
    hass: HomeAssistant,
    *,
    host: str,
    port: int,
    ssl: bool,
    verify_ssl: bool,
    username: str | None = None,
    password: str | None = None,
) -> str | None:
    """Return the error connecting to AdGuard Home ends in, if any."""
    adguard = AdGuardHome(
        URL.build(scheme="https" if ssl else "http", host=host, port=port),
        username=username,
        password=password,
        verify_ssl=verify_ssl,
        session=async_get_clientsession(hass, verify_ssl),
    )

    try:
        await adguard.status()
    except AdGuardHomeConnectionError:
        return "cannot_connect"
    except AdGuardHomeAuthenticationError:
        return "invalid_auth"
    except AdGuardHomeError:
        LOGGER.exception("Unexpected error connecting to AdGuard Home")
        return "unknown"

    return None


class AdGuardHomeFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a AdGuard Home config flow."""

    VERSION = 1

    _hassio_discovery: dict[str, Any] | None = None

    async def _show_setup_form(
        self, errors: dict[str, str] | None = None
    ) -> ConfigFlowResult:
        """Show the setup form to the user."""
        return self.async_show_form(
            step_id="user",
            data_schema=probatio.Schema(
                {
                    probatio.Required(CONF_HOST): str,
                    probatio.Required(CONF_PORT, default=3000): probatio.Coerce(int),
                    probatio.Optional(CONF_USERNAME): str,
                    probatio.Optional(probatio.Secret(CONF_PASSWORD)): str,
                    probatio.Required(CONF_SSL, default=True): bool,
                    probatio.Required(CONF_VERIFY_SSL, default=True): bool,
                }
            ),
            errors=errors or {},
        )

    async def _show_hassio_form(
        self, errors: dict[str, str] | None = None
    ) -> ConfigFlowResult:
        """Show the Hass.io confirmation form to the user."""
        assert self._hassio_discovery
        return self.async_show_form(
            step_id="hassio_confirm",
            description_placeholders={"addon": self._hassio_discovery["addon"]},
            errors=errors or {},
        )

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initiated by the user."""
        if user_input is None:
            return await self._show_setup_form(user_input)

        self._async_abort_entries_match(
            {CONF_HOST: user_input[CONF_HOST], CONF_PORT: user_input[CONF_PORT]}
        )

        if error := await _async_validate_connection(
            self.hass,
            host=user_input[CONF_HOST],
            port=user_input[CONF_PORT],
            ssl=user_input[CONF_SSL],
            verify_ssl=user_input[CONF_VERIFY_SSL],
            username=user_input.get(CONF_USERNAME),
            password=user_input.get(CONF_PASSWORD),
        ):
            return await self._show_setup_form({"base": error})

        return self.async_create_entry(
            title=user_input[CONF_HOST],
            data={
                CONF_HOST: user_input[CONF_HOST],
                CONF_PASSWORD: user_input.get(CONF_PASSWORD),
                CONF_PORT: user_input[CONF_PORT],
                CONF_SSL: user_input[CONF_SSL],
                CONF_USERNAME: user_input.get(CONF_USERNAME),
                CONF_VERIFY_SSL: user_input[CONF_VERIFY_SSL],
            },
        )

    @override
    async def async_step_hassio(
        self, discovery_info: HassioServiceInfo
    ) -> ConfigFlowResult:
        """Prepare configuration for a Hass.io AdGuard Home app.

        This flow is triggered by the discovery component.
        """
        await self._async_handle_discovery_without_unique_id()

        self._hassio_discovery = discovery_info.config
        return await self.async_step_hassio_confirm()

    async def async_step_hassio_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm Supervisor discovery."""
        if user_input is None:
            return await self._show_hassio_form()

        assert self._hassio_discovery
        if error := await _async_validate_connection(
            self.hass,
            host=self._hassio_discovery[CONF_HOST],
            port=self._hassio_discovery[CONF_PORT],
            ssl=False,
            verify_ssl=True,
        ):
            return await self._show_hassio_form({"base": error})

        return self.async_create_entry(
            title=self._hassio_discovery["addon"],
            data={
                CONF_HOST: self._hassio_discovery[CONF_HOST],
                CONF_PORT: self._hassio_discovery[CONF_PORT],
                CONF_PASSWORD: None,
                CONF_SSL: False,
                CONF_USERNAME: None,
                CONF_VERIFY_SSL: True,
            },
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle a request to authenticate with AdGuard Home again."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for new credentials for AdGuard Home."""
        reauth_entry = self._get_reauth_entry()
        errors: dict[str, str] = {}

        if user_input is not None:
            if error := await _async_validate_connection(
                self.hass,
                host=reauth_entry.data[CONF_HOST],
                port=reauth_entry.data[CONF_PORT],
                ssl=reauth_entry.data[CONF_SSL],
                verify_ssl=reauth_entry.data[CONF_VERIFY_SSL],
                username=user_input[CONF_USERNAME],
                password=user_input[CONF_PASSWORD],
            ):
                errors["base"] = error
            else:
                return self.async_update_reload_and_abort(
                    reauth_entry, data_updates=user_input
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=probatio.Schema(
                {
                    probatio.Required(
                        CONF_USERNAME, default=reauth_entry.data[CONF_USERNAME] or ""
                    ): str,
                    probatio.Required(probatio.Secret(CONF_PASSWORD)): str,
                }
            ),
            errors=errors,
        )
