"""Config flow for BSB-Lan integration."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from bsblan import BSBLAN, BSBLANAuthError, BSBLANConfig, BSBLANError
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_USERNAME
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from .const import CONF_PASSKEY, DEFAULT_PORT, DOMAIN


class BSBLANFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a BSBLAN config flow."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize BSBLan flow."""
        self.host: str = ""
        self.port: int = DEFAULT_PORT
        self.mac: str | None = None
        self.passkey: str | None = None
        self.username: str | None = None
        self.password: str | None = None
        self._auth_required = True

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initiated by the user."""
        if user_input is None:
            return self._show_setup_form()

        self.host = user_input[CONF_HOST]
        self.port = user_input[CONF_PORT]
        self.passkey = user_input.get(CONF_PASSKEY)
        self.username = user_input.get(CONF_USERNAME)
        self.password = user_input.get(CONF_PASSWORD)

        return await self._validate_and_create(user_input)

    async def async_step_zeroconf(
        self, discovery_info: ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Handle Zeroconf discovery."""

        self.host = str(discovery_info.ip_address)
        self.port = discovery_info.port or DEFAULT_PORT

        # Get MAC from properties
        self.mac = discovery_info.properties.get("mac")

        # If MAC was found in zeroconf, use it immediately
        if self.mac:
            await self.async_set_unique_id(format_mac(self.mac))
            self._abort_if_unique_id_configured(
                updates={
                    CONF_HOST: self.host,
                    CONF_PORT: self.port,
                }
            )
        else:
            # MAC not available from zeroconf - check for existing host/port first
            self._async_abort_entries_match(
                {CONF_HOST: self.host, CONF_PORT: self.port}
            )

            # Try to get device info without authentication to minimize discovery popup
            config = BSBLANConfig(host=self.host, port=self.port)
            session = async_get_clientsession(self.hass)
            bsblan = BSBLAN(config, session)
            try:
                device = await bsblan.device()
            except BSBLANError:
                # Device requires authentication - proceed to discovery confirm
                self.mac = None
            else:
                self.mac = device.MAC

                # Got MAC without auth - set unique ID and check for existing device
                await self.async_set_unique_id(format_mac(self.mac))
                self._abort_if_unique_id_configured(
                    updates={
                        CONF_HOST: self.host,
                        CONF_PORT: self.port,
                    }
                )
                # No auth needed, so we can proceed to a confirmation step without fields
                self._auth_required = False

        # Proceed to get credentials
        self.context["title_placeholders"] = {"name": f"BSBLAN {self.host}"}
        return await self.async_step_discovery_confirm()

    async def async_step_discovery_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle getting credentials for discovered device."""
        if user_input is None:
            data_schema = vol.Schema(
                {
                    vol.Optional(CONF_PASSKEY): str,
                    vol.Optional(CONF_USERNAME): str,
                    vol.Optional(CONF_PASSWORD): str,
                }
            )
            if not self._auth_required:
                data_schema = vol.Schema({})

            return self.async_show_form(
                step_id="discovery_confirm",
                data_schema=data_schema,
                description_placeholders={"host": str(self.host)},
            )

        if not self._auth_required:
            return self._async_create_entry()

        self.passkey = user_input.get(CONF_PASSKEY)
        self.username = user_input.get(CONF_USERNAME)
        self.password = user_input.get(CONF_PASSWORD)

        return await self._validate_and_create(user_input, is_discovery=True)

    async def _validate_and_create(
        self, user_input: dict[str, Any], is_discovery: bool = False
    ) -> ConfigFlowResult:
        """Validate device connection and create entry."""
        try:
            await self._get_bsblan_info()
        except BSBLANAuthError:
            if is_discovery:
                return self.async_show_form(
                    step_id="discovery_confirm",
                    data_schema=vol.Schema(
                        {
                            vol.Optional(CONF_PASSKEY): str,
                            vol.Optional(CONF_USERNAME): str,
                            vol.Optional(CONF_PASSWORD): str,
                        }
                    ),
                    errors={"base": "invalid_auth"},
                    description_placeholders={"host": str(self.host)},
                )
            return self._show_setup_form({"base": "invalid_auth"}, user_input)
        except BSBLANError:
            if is_discovery:
                return self.async_show_form(
                    step_id="discovery_confirm",
                    data_schema=vol.Schema(
                        {
                            vol.Optional(CONF_PASSKEY): str,
                            vol.Optional(CONF_USERNAME): str,
                            vol.Optional(CONF_PASSWORD): str,
                        }
                    ),
                    errors={"base": "cannot_connect"},
                    description_placeholders={"host": str(self.host)},
                )
            return self._show_setup_form({"base": "cannot_connect"})

        return self._async_create_entry()

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle reauth flow."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reauth confirmation flow."""
        existing_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        assert existing_entry

        if user_input is None:
            # Preserve existing values as defaults
            return self.async_show_form(
                step_id="reauth_confirm",
                data_schema=vol.Schema(
                    {
                        vol.Optional(
                            CONF_PASSKEY,
                            default=existing_entry.data.get(
                                CONF_PASSKEY, vol.UNDEFINED
                            ),
                        ): str,
                        vol.Optional(
                            CONF_USERNAME,
                            default=existing_entry.data.get(
                                CONF_USERNAME, vol.UNDEFINED
                            ),
                        ): str,
                        vol.Optional(
                            CONF_PASSWORD,
                            default=vol.UNDEFINED,
                        ): str,
                    }
                ),
            )

        # Combine existing data with the user's new input for validation.
        # This correctly handles adding, changing, and clearing credentials.
        config_data = existing_entry.data.copy()
        config_data.update(user_input)

        self.host = config_data[CONF_HOST]
        self.port = config_data[CONF_PORT]
        self.passkey = config_data.get(CONF_PASSKEY)
        self.username = config_data.get(CONF_USERNAME)
        self.password = config_data.get(CONF_PASSWORD)

        try:
            await self._get_bsblan_info(raise_on_progress=False, is_reauth=True)
        except BSBLANAuthError:
            return self.async_show_form(
                step_id="reauth_confirm",
                data_schema=vol.Schema(
                    {
                        vol.Optional(
                            CONF_PASSKEY,
                            default=user_input.get(CONF_PASSKEY, vol.UNDEFINED),
                        ): str,
                        vol.Optional(
                            CONF_USERNAME,
                            default=user_input.get(CONF_USERNAME, vol.UNDEFINED),
                        ): str,
                        vol.Optional(
                            CONF_PASSWORD,
                            default=vol.UNDEFINED,
                        ): str,
                    }
                ),
                errors={"base": "invalid_auth"},
            )
        except BSBLANError:
            return self.async_show_form(
                step_id="reauth_confirm",
                data_schema=vol.Schema(
                    {
                        vol.Optional(
                            CONF_PASSKEY,
                            default=user_input.get(CONF_PASSKEY, vol.UNDEFINED),
                        ): str,
                        vol.Optional(
                            CONF_USERNAME,
                            default=user_input.get(CONF_USERNAME, vol.UNDEFINED),
                        ): str,
                        vol.Optional(
                            CONF_PASSWORD,
                            default=vol.UNDEFINED,
                        ): str,
                    }
                ),
                errors={"base": "cannot_connect"},
            )

        # Update only the fields that were provided by the user
        return self.async_update_reload_and_abort(
            existing_entry, data_updates=user_input, reason="reauth_successful"
        )

    @callback
    def _show_setup_form(
        self, errors: dict | None = None, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show the setup form to the user."""
        # Preserve user input if provided, otherwise use defaults
        defaults = user_input or {}

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_HOST, default=defaults.get(CONF_HOST, vol.UNDEFINED)
                    ): str,
                    vol.Optional(
                        CONF_PORT, default=defaults.get(CONF_PORT, DEFAULT_PORT)
                    ): int,
                    vol.Optional(
                        CONF_PASSKEY, default=defaults.get(CONF_PASSKEY, vol.UNDEFINED)
                    ): str,
                    vol.Optional(
                        CONF_USERNAME,
                        default=defaults.get(CONF_USERNAME, vol.UNDEFINED),
                    ): str,
                    vol.Optional(
                        CONF_PASSWORD,
                        default=defaults.get(CONF_PASSWORD, vol.UNDEFINED),
                    ): str,
                }
            ),
            errors=errors or {},
        )

    @callback
    def _async_create_entry(self) -> ConfigFlowResult:
        """Create the config entry."""
        return self.async_create_entry(
            title=format_mac(self.mac),
            data={
                CONF_HOST: self.host,
                CONF_PORT: self.port,
                CONF_PASSKEY: self.passkey,
                CONF_USERNAME: self.username,
                CONF_PASSWORD: self.password,
            },
        )

    async def _get_bsblan_info(
        self,
        raise_on_progress: bool = True,
        is_reauth: bool = False,
    ) -> None:
        """Get device information from a BSBLAN device."""
        config = BSBLANConfig(
            host=self.host,
            passkey=self.passkey,
            port=self.port,
            username=self.username,
            password=self.password,
        )
        session = async_get_clientsession(self.hass)
        bsblan = BSBLAN(config, session)
        device = await bsblan.device()
        retrieved_mac = device.MAC

        # Handle unique ID assignment based on whether MAC was available from zeroconf
        if not self.mac:
            # MAC wasn't available from zeroconf, now we have it from API
            self.mac = retrieved_mac
            await self.async_set_unique_id(
                format_mac(self.mac), raise_on_progress=raise_on_progress
            )

        # Skip unique_id configuration check during reauth to prevent "already_configured" abort
        if not is_reauth:
            # Always allow updating host/port for both user and discovery flows
            # This ensures connectivity is maintained when devices change IP addresses
            self._abort_if_unique_id_configured(
                updates={
                    CONF_HOST: self.host,
                    CONF_PORT: self.port,
                }
            )
