"""Config flow to configure the Fumis integration."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from fumis import (
    Fumis,
    FumisAuthenticationError,
    FumisConnectionError,
    FumisInfo,
    FumisStoveOfflineError,
)
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_MAC, CONF_PIN
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo

from .const import DOMAIN, LOGGER


class FumisFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a Fumis config flow."""

    _discovered_mac: str

    async def async_step_dhcp(
        self, discovery_info: DhcpServiceInfo
    ) -> ConfigFlowResult:
        """Handle DHCP discovery of a Fumis WiRCU module."""
        mac = discovery_info.macaddress.replace(":", "").replace("-", "").upper()

        await self.async_set_unique_id(format_mac(mac))
        self._abort_if_unique_id_configured()

        self._discovered_mac = mac
        return await self.async_step_dhcp_confirm()

    async def async_step_dhcp_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle DHCP discovery confirmation."""
        errors: dict[str, str] = {}

        if user_input is not None:
            errors, info = await self._validate_input(
                self._discovered_mac, user_input[CONF_PIN]
            )
            if info:
                return self.async_create_entry(
                    title=info.controller.model_name or "Fumis",
                    data={
                        CONF_MAC: self._discovered_mac,
                        CONF_PIN: user_input[CONF_PIN],
                    },
                )

        return self.async_show_form(
            step_id="dhcp_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_PIN): TextSelector(
                        TextSelectorConfig(type=TextSelectorType.PASSWORD)
                    ),
                }
            ),
            errors=errors,
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initiated by the user."""
        errors: dict[str, str] = {}

        if user_input is not None:
            mac = user_input[CONF_MAC].replace(":", "").replace("-", "").upper()
            errors, info = await self._validate_input(mac, user_input[CONF_PIN])
            if info:
                await self.async_set_unique_id(format_mac(mac), raise_on_progress=False)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=info.controller.model_name or "Fumis",
                    data={
                        CONF_MAC: mac,
                        CONF_PIN: user_input[CONF_PIN],
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                vol.Schema(
                    {
                        vol.Required(CONF_MAC): TextSelector(
                            TextSelectorConfig(autocomplete="off")
                        ),
                        vol.Required(CONF_PIN): TextSelector(
                            TextSelectorConfig(type=TextSelectorType.PASSWORD)
                        ),
                    }
                ),
                user_input,
            ),
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration of a Fumis stove."""
        errors: dict[str, str] = {}
        reconfigure_entry = self._get_reconfigure_entry()

        if user_input is not None:
            errors, _ = await self._validate_input(
                reconfigure_entry.data[CONF_MAC], user_input[CONF_PIN]
            )
            if not errors:
                return self.async_update_reload_and_abort(
                    reconfigure_entry,
                    data_updates={CONF_PIN: user_input[CONF_PIN]},
                )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_PIN): TextSelector(
                        TextSelectorConfig(type=TextSelectorType.PASSWORD)
                    ),
                }
            ),
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle re-authentication of a Fumis stove."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle re-authentication confirmation."""
        errors: dict[str, str] = {}

        if user_input is not None:
            reauth_entry = self._get_reauth_entry()
            errors, _ = await self._validate_input(
                reauth_entry.data[CONF_MAC], user_input[CONF_PIN]
            )
            if not errors:
                return self.async_update_reload_and_abort(
                    reauth_entry,
                    data_updates={CONF_PIN: user_input[CONF_PIN]},
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_PIN): TextSelector(
                        TextSelectorConfig(type=TextSelectorType.PASSWORD)
                    ),
                }
            ),
            errors=errors,
        )

    async def _validate_input(
        self, mac: str, pin: str
    ) -> tuple[dict[str, str], FumisInfo | None]:
        """Validate credentials, returning errors and info."""
        errors: dict[str, str] = {}
        fumis = Fumis(
            mac=mac,
            password=pin,
            session=async_get_clientsession(self.hass),
        )
        try:
            info = await fumis.update_info()
        except FumisAuthenticationError:
            errors[CONF_PIN] = "invalid_auth"
        except FumisStoveOfflineError:
            errors["base"] = "device_offline"
        except FumisConnectionError:
            errors["base"] = "cannot_connect"
        except Exception:  # noqa: BLE001
            LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            return errors, info
        return errors, None
