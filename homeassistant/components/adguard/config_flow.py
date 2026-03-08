"""Config flow to configure the AdGuard Home integration."""

from __future__ import annotations

from typing import Any

from adguardhome import AdGuardHome, AdGuardHomeConnectionError
import voluptuous as vol
from yarl import URL

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PATH,
    CONF_PORT,
    CONF_SSL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.service_info.hassio import HassioServiceInfo

from .const import DEFAULT_BASE_PATH, DEFAULT_PORT, DOMAIN


def _parse_address(address: str) -> tuple[str, int, str, bool]:
    """Parse user provided address into host, port, path, and TLS mode."""
    normalized_address = address.strip()
    has_scheme = "://" in normalized_address

    if not has_scheme:
        normalized_address = f"http://{normalized_address}"

    url = URL(normalized_address)

    if (
        url.scheme not in {"http", "https"}
        or not url.host
        or url.user
        or url.password
        or url.query
        or url.fragment
    ):
        raise ValueError

    tls = url.scheme == "https"
    if has_scheme:
        port = url.explicit_port or (443 if tls else 80)
    else:
        port = url.explicit_port or DEFAULT_PORT

    path = DEFAULT_BASE_PATH if url.path in {"", "/"} else url.path

    return (
        url.host,
        port,
        path,
        tls,
    )


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
            description_placeholders={
                "example_host": "adguard.local",
                "example_host_port": "adguard.local:3000",
                "example_ip_port": "192.168.1.10:3000",
                "example_url": "https://adguard.example.com",
                "default_port": str(DEFAULT_PORT),
            },
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST): str,
                    vol.Optional(CONF_USERNAME): str,
                    vol.Optional(CONF_PASSWORD): str,
                    vol.Required(CONF_VERIFY_SSL, default=True): bool,
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

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initiated by the user."""
        if user_input is None:
            return await self._show_setup_form()

        errors = {}

        try:
            host, port, base_path, use_tls = _parse_address(user_input[CONF_HOST])
        except ValueError:
            errors["base"] = "invalid_url"
            return await self._show_setup_form(errors)

        self._async_abort_entries_match(
            {
                CONF_HOST: host,
                CONF_PORT: port,
            }
        )

        session = async_get_clientsession(self.hass, user_input[CONF_VERIFY_SSL])

        username: str | None = user_input.get(CONF_USERNAME)
        password: str | None = user_input.get(CONF_PASSWORD)
        adguard = AdGuardHome(
            host,
            base_path=base_path,
            port=port,
            username=username,
            password=password,
            tls=use_tls,
            verify_ssl=user_input[CONF_VERIFY_SSL],
            session=session,
        )

        try:
            await adguard.version()
        except AdGuardHomeConnectionError:
            errors["base"] = "cannot_connect"
            return await self._show_setup_form(errors)

        return self.async_create_entry(
            title=host,
            data={
                CONF_HOST: host,
                CONF_PASSWORD: user_input.get(CONF_PASSWORD),
                CONF_PATH: base_path,
                CONF_PORT: port,
                CONF_SSL: use_tls,
                CONF_USERNAME: user_input.get(CONF_USERNAME),
                CONF_VERIFY_SSL: user_input[CONF_VERIFY_SSL],
            },
        )

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

        errors = {}

        session = async_get_clientsession(self.hass, False)

        assert self._hassio_discovery
        adguard = AdGuardHome(
            self._hassio_discovery[CONF_HOST],
            port=self._hassio_discovery[CONF_PORT],
            tls=False,
            session=session,
        )

        try:
            await adguard.version()
        except AdGuardHomeConnectionError:
            errors["base"] = "cannot_connect"
            return await self._show_hassio_form(errors)

        return self.async_create_entry(
            title=self._hassio_discovery["addon"],
            data={
                CONF_HOST: self._hassio_discovery[CONF_HOST],
                CONF_PATH: DEFAULT_BASE_PATH,
                CONF_PORT: self._hassio_discovery[CONF_PORT],
                CONF_PASSWORD: None,
                CONF_SSL: False,
                CONF_USERNAME: None,
                CONF_VERIFY_SSL: True,
            },
        )
