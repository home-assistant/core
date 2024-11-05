"""Config flow for Plugwise integration."""

from __future__ import annotations

from typing import Any, Self

from plugwise import Smile
from plugwise.exceptions import (
    ConnectionFailedError,
    InvalidAuthentication,
    InvalidSetupError,
    InvalidXMLError,
    ResponseError,
    UnsupportedDeviceError,
)
import voluptuous as vol

from homeassistant.components.zeroconf import ZeroconfServiceInfo
from homeassistant.config_entries import SOURCE_USER, ConfigFlow, ConfigFlowResult
from homeassistant.const import (
    ATTR_CONFIGURATION_URL,
    CONF_BASE,
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    DEFAULT_PORT,
    DEFAULT_USERNAME,
    DOMAIN,
    FLOW_SMILE,
    FLOW_STRETCH,
    SMILE,
    STRETCH,
    STRETCH_USERNAME,
    ZEROCONF_MAP,
)


def base_schema(discovery_info: ZeroconfServiceInfo | None) -> vol.Schema:
    """Generate base schema for gateways."""
    schema = vol.Schema({vol.Required(CONF_PASSWORD): str})

    if not discovery_info:
        schema = schema.extend(
            {
                vol.Required(CONF_HOST): str,
                vol.Optional(CONF_PORT, default=DEFAULT_PORT): int,
                vol.Required(CONF_USERNAME, default=SMILE): vol.In(
                    {SMILE: FLOW_SMILE, STRETCH: FLOW_STRETCH}
                ),
            }
        )

    return schema


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> Smile:
    """Validate whether the user input allows us to connect to the gateway.

    Data has the keys from base_schema() with values provided by the user.
    """
    websession = async_get_clientsession(hass, verify_ssl=False)
    api = Smile(
        host=data[CONF_HOST],
        password=data[CONF_PASSWORD],
        port=data[CONF_PORT],
        username=data[CONF_USERNAME],
        websession=websession,
    )
    await api.connect()
    return api


class PlugwiseConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Plugwise Smile."""

    VERSION = 1

    discovery_info: ZeroconfServiceInfo | None = None
    product: str = "Unknown Smile"
    _username: str = DEFAULT_USERNAME

    async def async_step_zeroconf(
        self, discovery_info: ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Prepare configuration for a discovered Plugwise Smile."""
        self.discovery_info = discovery_info
        _properties = discovery_info.properties

        unique_id = discovery_info.hostname.split(".")[0].split("-")[0]
        if config_entry := await self.async_set_unique_id(unique_id):
            try:
                await validate_input(
                    self.hass,
                    {
                        CONF_HOST: discovery_info.host,
                        CONF_PORT: discovery_info.port,
                        CONF_USERNAME: config_entry.data[CONF_USERNAME],
                        CONF_PASSWORD: config_entry.data[CONF_PASSWORD],
                    },
                )
            except Exception:  # noqa: BLE001
                self._abort_if_unique_id_configured()
            else:
                self._abort_if_unique_id_configured(
                    {
                        CONF_HOST: discovery_info.host,
                        CONF_PORT: discovery_info.port,
                    }
                )

        if DEFAULT_USERNAME not in unique_id:
            self._username = STRETCH_USERNAME
        self.product = _product = _properties.get("product", "Unknown Smile")
        _version = _properties.get("version", "n/a")
        _name = f"{ZEROCONF_MAP.get(_product, _product)} v{_version}"

        # This is an Anna, but we already have config entries.
        # Assuming that the user has already configured Adam, aborting discovery.
        if self._async_current_entries() and _product == "smile_thermo":
            return self.async_abort(reason="anna_with_adam")

        # If we have discovered an Adam or Anna, both might be on the network.
        # In that case, we need to cancel the Anna flow, as the Adam should
        # be added.
        if self.hass.config_entries.flow.async_has_matching_flow(self):
            return self.async_abort(reason="anna_with_adam")

        self.context.update(
            {
                "title_placeholders": {CONF_NAME: _name},
                ATTR_CONFIGURATION_URL: (
                    f"http://{discovery_info.host}:{discovery_info.port}"
                ),
            }
        )
        return await self.async_step_user()

    def is_matching(self, other_flow: Self) -> bool:
        """Return True if other_flow is matching this flow."""
        # This is an Anna, and there is already an Adam flow in progress
        if self.product == "smile_thermo" and other_flow.product == "smile_open_therm":
            return True

        # This is an Adam, and there is already an Anna flow in progress
        if self.product == "smile_open_therm" and other_flow.product == "smile_thermo":
            self.hass.config_entries.flow.async_abort(other_flow.flow_id)

        return False

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step when using network/gateway setups."""
        errors: dict[str, str] = {}

        if user_input is not None:
            if self.discovery_info:
                user_input[CONF_HOST] = self.discovery_info.host
                user_input[CONF_PORT] = self.discovery_info.port
                user_input[CONF_USERNAME] = self._username

            try:
                api = await validate_input(self.hass, user_input)
            except ConnectionFailedError:
                errors[CONF_BASE] = "cannot_connect"
            except InvalidAuthentication:
                errors[CONF_BASE] = "invalid_auth"
            except InvalidSetupError:
                errors[CONF_BASE] = "invalid_setup"
            except (InvalidXMLError, ResponseError):
                errors[CONF_BASE] = "response_error"
            except UnsupportedDeviceError:
                errors[CONF_BASE] = "unsupported"
            except Exception:  # noqa: BLE001
                errors[CONF_BASE] = "unknown"
            else:
                await self.async_set_unique_id(
                    api.smile_hostname or api.gateway_id, raise_on_progress=False
                )
                self._abort_if_unique_id_configured()

                return self.async_create_entry(title=api.smile_name, data=user_input)

        return self.async_show_form(
            step_id=SOURCE_USER,
            data_schema=base_schema(self.discovery_info),
            errors=errors,
        )
