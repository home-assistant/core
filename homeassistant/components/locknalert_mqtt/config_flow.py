"""Config flow for LocknAlert."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from .bridge_api import (
    LocknAlertBridgeApi,
    LocknAlertCannotConnect,
    LocknAlertInvalidAuth,
    LocknAlertInvalidResponse,
    LocknAlertPairingRequired,
)
from .const import (
    CONF_API_PORT,
    CONF_BRIDGE_SERIAL,
    CONF_LocknAlertMQTT,
    CONF_PAIRING_TOKEN,
    CONF_PREFIX,
    CONF_TLS_REQUIRED,
    CONF_VERIFY_SSL,
    DEFAULT_API_PORT,
    DEFAULT_TOPIC_PREFIX,
    DOMAIN,
)


class LocknAlertConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle LocknAlert setup flow."""

    VERSION = 1

    _host: str
    _api_port: int
    _bridge_serial: str | None = None
    _discovery: dict[str, Any] | None = None
    _reauth_entry_id: str | None = None

    def _confirm_schema(self) -> vol.Schema:
        """Build schema for the discovered bridge confirmation step."""
        return vol.Schema(
            {
                vol.Required(CONF_BRIDGE_SERIAL, default=self._bridge_serial or ""): str,
                vol.Optional(CONF_PAIRING_TOKEN): str,
                vol.Optional(CONF_VERIFY_SSL, default=False): bool,
            }
        )

    @staticmethod
    def _user_schema() -> vol.Schema:
        """Build schema for the manual setup step."""
        return vol.Schema(
            {
                vol.Required(CONF_HOST): str,
                vol.Optional(CONF_API_PORT, default=DEFAULT_API_PORT): int,
                vol.Required(CONF_BRIDGE_SERIAL): str,
                vol.Optional(CONF_PAIRING_TOKEN): str,
                vol.Optional(CONF_VERIFY_SSL, default=False): bool,
            }
        )

    async def async_step_zeroconf(self, discovery_info: ZeroconfServiceInfo) -> ConfigFlowResult:
        """Handle mDNS discovery."""
        self._host = discovery_info.host
        self._api_port = int(discovery_info.properties.get("api_port", DEFAULT_API_PORT))
        self._bridge_serial = (
            str(
                discovery_info.properties.get("bridge_serial", "")
            )
            or None
        )
        self._discovery = dict(discovery_info.properties)

        if self._bridge_serial:
            await self.async_set_unique_id(self._bridge_serial)
            self._abort_if_unique_id_configured(updates={CONF_HOST: self._host, CONF_PORT: self._api_port})

        self.context["title_placeholders"] = {"name": discovery_info.name}
        return await self.async_step_confirm()

    async def async_step_confirm(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            return await self._async_finish_setup(user_input, errors)
        return self.async_show_form(
            step_id="confirm",
            data_schema=self._confirm_schema(),
            errors=errors,
            description_placeholders={
                "host": getattr(self, "_host", ""),
                "bridge_serial": self._bridge_serial or "unknown",
            },
        )

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Manual fallback step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            self._host = user_input[CONF_HOST]
            self._api_port = user_input[CONF_API_PORT]
            return await self._async_finish_setup(user_input, errors)

        return self.async_show_form(step_id="user", data_schema=self._user_schema(), errors=errors)

    async def async_step_reauth(self, entry_data: dict[str, Any]) -> ConfigFlowResult:
        """Handle re-authentication flow."""
        self._host = str(entry_data[CONF_HOST])
        self._api_port = int(entry_data.get(CONF_PORT, DEFAULT_API_PORT))
        self._bridge_serial = str(entry_data.get(CONF_BRIDGE_SERIAL, "")) or None
        self._reauth_entry_id = self.context.get("entry_id")
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm re-authentication details and refresh stored credentials."""
        errors: dict[str, str] = {}
        if user_input is not None:
            return await self._async_finish_reauth(user_input, errors)

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_PAIRING_TOKEN): str,
                    vol.Optional(CONF_VERIFY_SSL, default=False): bool,
                }
            ),
            errors=errors,
            description_placeholders={
                "host": getattr(self, "_host", ""),
                "bridge_serial": self._bridge_serial or "unknown",
            },
        )

    async def _async_finish_setup(
        self, user_input: dict[str, Any], errors: dict[str, str]
    ) -> ConfigFlowResult:
        """Validate bridge and create entry."""
        session = async_get_clientsession(self.hass)
        api = LocknAlertBridgeApi(
            host=self._host,
            port=self._api_port,
            verify_ssl=user_input.get(CONF_VERIFY_SSL, False),
        )

        try:
            info = await api.async_get_info(session)
            bridge_serial = str(info.get(CONF_BRIDGE_SERIAL) or "")
            if not bridge_serial:
                raise LocknAlertInvalidResponse("Missing bridge_serial")
            requested_serial = str(user_input[CONF_BRIDGE_SERIAL])
            if requested_serial != bridge_serial:
                errors["base"] = "serial_mismatch"

            await self.async_set_unique_id(str(bridge_serial))
            self._abort_if_unique_id_configured(
                updates={CONF_HOST: self._host, CONF_PORT: self._api_port}
            )

            if user_input.get(CONF_PAIRING_TOKEN):
                await api.async_pair(session, user_input[CONF_PAIRING_TOKEN])

            mqtt = await api.async_get_mqtt_bootstrap(session)
        except LocknAlertInvalidAuth:
            errors["base"] = "invalid_auth"
        except LocknAlertPairingRequired:
            errors["base"] = "pairing_required"
        except LocknAlertCannotConnect:
            errors["base"] = "cannot_connect"
        except LocknAlertInvalidResponse:
            errors["base"] = "invalid_bootstrap"

        if errors:
            step = "confirm" if self.source == "zeroconf" else "user"
            if step == "confirm":
                return self.async_show_form(
                    step_id="confirm",
                    data_schema=self._confirm_schema(),
                    errors=errors,
                    description_placeholders={
                        "host": getattr(self, "_host", ""),
                        "bridge_serial": self._bridge_serial or "unknown",
                    },
                )
            return self.async_show_form(step_id="user", data_schema=self._user_schema(), errors=errors)

        return self.async_create_entry(
            title=f"LocknAlert {bridge_serial}",
            data={
                CONF_HOST: self._host,
                CONF_PORT: self._api_port,
                CONF_VERIFY_SSL: user_input.get(CONF_VERIFY_SSL, False),
                CONF_BRIDGE_SERIAL: str(bridge_serial),
                CONF_LocknAlertMQTT: {
                    CONF_HOST: mqtt["host"],
                    CONF_PORT: mqtt["port"],
                    "username": mqtt["username"],
                    "password": mqtt["password"],
                    CONF_TLS_REQUIRED: mqtt.get("tls_required", True),
                    CONF_PREFIX: mqtt.get("topic_prefix", DEFAULT_TOPIC_PREFIX),
                },
            },
        )

    async def _async_finish_reauth(
        self, user_input: dict[str, Any], errors: dict[str, str]
    ) -> ConfigFlowResult:
        """Validate bridge credentials and update config entry during reauth."""
        session = async_get_clientsession(self.hass)
        api = LocknAlertBridgeApi(
            host=self._host,
            port=self._api_port,
            verify_ssl=user_input.get(CONF_VERIFY_SSL, False),
        )

        try:
            info = await api.async_get_info(session)
            bridge_serial = str(info.get(CONF_BRIDGE_SERIAL) or "")
            if self._bridge_serial and bridge_serial != self._bridge_serial:
                errors["base"] = "serial_mismatch"
                raise LocknAlertInvalidResponse("Bridge serial mismatch")

            if user_input.get(CONF_PAIRING_TOKEN):
                await api.async_pair(session, user_input[CONF_PAIRING_TOKEN])

            mqtt = await api.async_get_mqtt_bootstrap(session)
        except LocknAlertInvalidAuth:
            errors["base"] = "invalid_auth"
        except LocknAlertPairingRequired:
            errors["base"] = "pairing_required"
        except LocknAlertCannotConnect:
            errors["base"] = "cannot_connect"
        except LocknAlertInvalidResponse:
            errors["base"] = errors.get("base", "invalid_bootstrap")

        if errors:
            return self.async_show_form(
                step_id="reauth_confirm",
                data_schema=vol.Schema(
                    {
                        vol.Optional(CONF_PAIRING_TOKEN): str,
                        vol.Optional(CONF_VERIFY_SSL, default=False): bool,
                    }
                ),
                errors=errors,
                description_placeholders={
                    "host": getattr(self, "_host", ""),
                    "bridge_serial": self._bridge_serial or "unknown",
                },
            )

        if self._reauth_entry_id is not None:
            entry = self.hass.config_entries.async_get_entry(self._reauth_entry_id)
            if entry is not None:
                self.hass.config_entries.async_update_entry(
                    entry,
                    data={
                        **entry.data,
                        CONF_VERIFY_SSL: user_input.get(CONF_VERIFY_SSL, False),
                        CONF_LocknAlertMQTT: {
                            CONF_HOST: mqtt["host"],
                            CONF_PORT: mqtt["port"],
                            "username": mqtt["username"],
                            "password": mqtt["password"],
                            CONF_TLS_REQUIRED: mqtt.get("tls_required", True),
                            CONF_PREFIX: mqtt.get("topic_prefix", DEFAULT_TOPIC_PREFIX),
                        },
                    },
                )

        if self._reauth_entry_id is not None:
            await self.hass.config_entries.async_reload(self._reauth_entry_id)
        return self.async_abort(reason="reauth_successful")
