"""Config flow for the WattWächter Plus integration."""

from collections.abc import Mapping
import logging
from typing import Any, override

from aio_wattwaechter import (
    Wattwaechter,
    WattwaechterAuthenticationError,
    WattwaechterConnectionError,
)
from aio_wattwaechter.models import SystemInfo
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import (
    CONF_DEVICE_ID,
    CONF_HOST,
    CONF_MAC,
    CONF_MODEL,
    CONF_TOKEN,
)
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from .const import CONF_FW_VERSION, DOMAIN

_LOGGER = logging.getLogger(__name__)


class WattwaechterConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for WattWächter Plus."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._host: str = ""
        self._device_id: str = ""
        self._model: str | None = None
        self._fw_version: str | None = None
        self._mac: str = ""
        self._device_name: str | None = None

    async def _async_test_connection(
        self, host: str, token: str | None = None
    ) -> tuple[dict[str, str], SystemInfo | None, str | None]:
        """Test connection and fetch system info plus device name."""
        session = async_get_clientsession(self.hass)
        client = Wattwaechter(host, token=token, session=session)
        try:
            system_info = await client.system_info()
        except WattwaechterAuthenticationError:
            return {"base": "invalid_auth"}, None, None
        except WattwaechterConnectionError:
            return {"base": "cannot_connect"}, None, None
        try:
            settings = await client.settings()
        except WattwaechterConnectionError, WattwaechterAuthenticationError:
            device_name = None
        else:
            device_name = settings.device_name
        return {}, system_info, device_name

    def _create_entry(self, token: str | None = None) -> ConfigFlowResult:
        """Create a config entry with the collected device info."""
        title = self._device_name or f"WattWächter {self._device_id[-4:]}"
        return self.async_create_entry(
            title=title,
            data={
                CONF_HOST: self._host,
                CONF_TOKEN: token,
                CONF_DEVICE_ID: self._device_id,
                CONF_MODEL: self._model,
                CONF_FW_VERSION: self._fw_version,
                CONF_MAC: self._mac,
            },
        )

    @override
    async def async_step_zeroconf(
        self, discovery_info: ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Handle zeroconf discovery."""
        _LOGGER.debug("Zeroconf discovery: %s", discovery_info)

        self._host = str(discovery_info.host)

        properties = discovery_info.properties
        device_id_raw = properties.get("id", "")
        self._model = properties.get("model")
        self._fw_version = properties.get("ver")
        self._mac = properties.get("mac", "")

        self._device_id = device_id_raw.removeprefix("WWP-")

        await self.async_set_unique_id(self._device_id)
        self._abort_if_unique_id_configured(updates={CONF_HOST: self._host})

        errors, _, device_name = await self._async_test_connection(self._host)
        if errors:
            if errors["base"] == "invalid_auth":
                self.context["title_placeholders"] = {
                    "name": f"WattWächter {self._device_id[-4:]}"
                }
                return await self.async_step_auth()
            return self.async_abort(reason="cannot_connect")

        self._device_name = device_name
        self.context["title_placeholders"] = {
            "name": self._device_name or f"WattWächter {self._device_id[-4:]}"
        }
        return await self.async_step_zeroconf_confirm()

    async def async_step_zeroconf_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm zeroconf discovery."""
        if user_input is None:
            self._set_confirm_only()
            return self.async_show_form(
                step_id="zeroconf_confirm",
                description_placeholders={
                    "model": self._model or "WattWächter Plus",
                    "firmware": self._fw_version or "unknown",
                    "host": self._host,
                    "device_id": self._device_id,
                },
            )

        return self._create_entry()

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle manual configuration."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self._host = user_input[CONF_HOST]

            errors, system_info, device_name = await self._async_test_connection(
                self._host
            )

            if errors.get("base") == "invalid_auth":
                return await self.async_step_auth()

            if not errors:
                assert system_info is not None
                self._device_id = system_info.get_value("esp", "esp_id") or ""
                self._fw_version = system_info.get_value("esp", "os_version")
                self._mac = system_info.get_value("wifi", "mac_address") or ""
                self._model = "WW-Plus"
                self._device_name = device_name

                await self.async_set_unique_id(self._device_id, raise_on_progress=False)
                self._abort_if_unique_id_configured(updates={CONF_HOST: self._host})

                return self._create_entry()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST): str,
                }
            ),
            errors=errors,
        )

    async def async_step_auth(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle token authentication."""
        errors: dict[str, str] = {}

        if user_input is not None:
            token = user_input[CONF_TOKEN]

            errors, system_info, device_name = await self._async_test_connection(
                self._host, token
            )

            if not errors:
                assert system_info is not None
                # For user flow, populate device info from system_info
                if not self._device_id:
                    self._device_id = system_info.get_value("esp", "esp_id") or ""
                    self._fw_version = system_info.get_value("esp", "os_version")
                    self._mac = system_info.get_value("wifi", "mac_address") or ""
                    self._model = "WW-Plus"

                self._device_name = device_name

                if self.unique_id is None:
                    await self.async_set_unique_id(
                        self._device_id, raise_on_progress=False
                    )
                    self._abort_if_unique_id_configured(updates={CONF_HOST: self._host})

                return self._create_entry(token)

        return self.async_show_form(
            step_id="auth",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_TOKEN): str,
                }
            ),
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle reauthentication when the stored token is no longer valid."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm reauthentication with a new token."""
        reauth_entry = self._get_reauth_entry()
        errors: dict[str, str] = {}

        if user_input is not None:
            errors, system_info, _ = await self._async_test_connection(
                reauth_entry.data[CONF_HOST], user_input[CONF_TOKEN]
            )
            if not errors:
                assert system_info is not None
                await self.async_set_unique_id(system_info.get_value("esp", "esp_id"))
                self._abort_if_unique_id_mismatch(reason="wrong_device")
                return self.async_update_reload_and_abort(
                    reauth_entry, data_updates={CONF_TOKEN: user_input[CONF_TOKEN]}
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_TOKEN): str,
                }
            ),
            description_placeholders={"host": reauth_entry.data[CONF_HOST]},
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration of the host and token."""
        reconfigure_entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}

        if user_input is not None:
            # Normalize a cleared token field to None, matching how token-less
            # devices are stored everywhere else in the integration.
            token = user_input.get(CONF_TOKEN) or None
            errors, system_info, _ = await self._async_test_connection(
                user_input[CONF_HOST], token
            )
            if not errors:
                assert system_info is not None
                await self.async_set_unique_id(system_info.get_value("esp", "esp_id"))
                self._abort_if_unique_id_mismatch(reason="wrong_device")
                return self.async_update_reload_and_abort(
                    reconfigure_entry,
                    data_updates={CONF_HOST: user_input[CONF_HOST], CONF_TOKEN: token},
                )

        schema = vol.Schema(
            {
                vol.Required(CONF_HOST): str,
                vol.Optional(CONF_TOKEN): TextSelector(
                    TextSelectorConfig(type=TextSelectorType.PASSWORD)
                ),
            }
        )
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                schema, user_input or reconfigure_entry.data
            ),
            errors=errors,
        )
