"""Config flow for OpenEVSE integration."""

from typing import Any

from openevsehttp.__main__ import OpenEVSE
from openevsehttp.exceptions import AuthenticationError
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.service_info import zeroconf

from .const import CONF_ID, DOMAIN


class OpenEVSEConfigFlow(ConfigFlow, domain=DOMAIN):
    """OpenEVSE config flow."""

    VERSION = 1
    MINOR_VERSION = 1

    def __init__(self) -> None:
        """Set up the instance."""
        self.discovery_info: dict[str, Any] = {}

    async def check_status(
        self, host: str, user: str = "", password: str = ""
    ) -> dict[str, str]:
        """Check if we can connect to the OpenEVSE charger."""

        charger = OpenEVSE(host=host, user=user, pwd=password)
        try:
            await charger.test_and_get()
        except TimeoutError:
            return {CONF_HOST: "cannot_connect"}
        except AuthenticationError:
            return {"base": "invalid_auth"}
        else:
            return {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""

        errors: dict[str, str] = {}
        if user_input is not None:
            self._async_abort_entries_match({CONF_HOST: user_input[CONF_HOST]})
            errors = await self.check_status(
                user_input[CONF_HOST],
                user_input[CONF_USERNAME],
                user_input[CONF_PASSWORD],
            )

            if not errors:
                return self.async_create_entry(
                    title=f"OpenEVSE {user_input[CONF_HOST]}",
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=_get_schema(user_input, {}),
            errors=errors,
        )

    async def async_step_import(self, data: dict[str, str]) -> ConfigFlowResult:
        """Handle the initial step."""

        self._async_abort_entries_match({CONF_HOST: data[CONF_HOST]})

        if await self.check_status(data[CONF_HOST]):
            return self.async_abort(reason="unavailable_host")

        return self.async_create_entry(
            title=f"OpenEVSE {data[CONF_HOST]}",
            data=data,
        )

    async def async_step_zeroconf(
        self, discovery_info: zeroconf.ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Handle zeroconf discovery."""
        self._async_abort_entries_match({CONF_HOST: discovery_info.host})

        await self.async_set_unique_id(discovery_info.properties[CONF_ID])
        self._abort_if_unique_id_configured(updates={CONF_HOST: discovery_info.host})

        host = discovery_info.host
        name = f"OpenEVSE {discovery_info.name.split('.')[0]}"
        self.discovery_info.update(
            {
                CONF_HOST: host,
                CONF_NAME: name,
            }
        )
        self.context.update({"title_placeholders": {CONF_NAME: name}})
        return await self.async_step_discovery_confirm()

    async def async_step_discovery_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm discovery."""
        data_schema = vol.Schema({})
        errors = await self.check_status(self.discovery_info[CONF_HOST])

        if errors:
            data_schema = _get_schema(user_input, self.discovery_info)

        if user_input is None:
            return self.async_show_form(
                step_id="discovery_confirm",
                data_schema=data_schema,
                errors=errors,
                description_placeholders={"name": self.discovery_info[CONF_NAME]},
            )

        return self.async_create_entry(
            title=self.discovery_info[CONF_NAME],
            data={CONF_HOST: self.discovery_info[CONF_HOST]},
        )


def _get_schema(
    user_input: dict[str, Any] | None,
    default_dict: dict[str, Any],
) -> vol.Schema:
    """Get a schema using the default_dict as a backup."""
    if user_input is None:
        user_input = {}

    def _get_default(key: str, fallback_default: Any = None) -> Any | None:
        """Get default value for key."""
        return user_input.get(key, default_dict.get(key, fallback_default))

    return vol.Schema(
        {
            vol.Required(CONF_HOST, default=_get_default(CONF_HOST)): cv.string,
            vol.Optional(
                CONF_USERNAME, default=_get_default(CONF_USERNAME, "")
            ): cv.string,
            vol.Optional(
                CONF_PASSWORD, default=_get_default(CONF_PASSWORD, "")
            ): cv.string,
        },
    )
