"""Config flow for OpenEVSE integration."""

from typing import Any

from openevsehttp.__main__ import OpenEVSE
from openevsehttp.exceptions import AuthenticationError, MissingSerial
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.service_info import zeroconf

from .const import CONF_ID, CONF_SERIAL, DOMAIN

USER_SCHEMA = vol.Schema({vol.Required(CONF_HOST): cv.string})

AUTH_SCHEMA = vol.Schema(
    {vol.Required(CONF_USERNAME): cv.string, vol.Required(CONF_PASSWORD): cv.string}
)


class OpenEVSEConfigFlow(ConfigFlow, domain=DOMAIN):
    """OpenEVSE config flow."""

    VERSION = 1
    MINOR_VERSION = 1

    def __init__(self) -> None:
        """Set up the instance."""
        self.discovery_info: dict[str, Any] = {}
        self._host: str | None = None

    async def check_status(
        self, host: str, user: str | None = None, password: str | None = None
    ) -> tuple[dict[str, str], str | None]:
        """Check if we can connect to the OpenEVSE charger."""

        charger = OpenEVSE(host, user, password)
        try:
            result = await charger.test_and_get()
        except TimeoutError:
            return {"base": "cannot_connect"}, None
        except AuthenticationError:
            return {"base": "invalid_auth"}, None
        except MissingSerial:
            return {}, None
        return {}, result.get(CONF_SERIAL)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""

        errors: dict[str, str] = {}
        if user_input is not None:
            self._async_abort_entries_match({CONF_HOST: user_input[CONF_HOST]})
            errors, serial = await self.check_status(user_input[CONF_HOST])

            if not errors:
                if serial is not None:
                    await self.async_set_unique_id(serial, raise_on_progress=False)
                    self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=f"OpenEVSE {user_input[CONF_HOST]}",
                    data=user_input,
                )
            if errors["base"] == "invalid_auth":
                self._host = user_input[CONF_HOST]
                return await self.async_step_auth()

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(USER_SCHEMA, user_input),
            errors=errors,
        )

    async def async_step_import(self, data: dict[str, str]) -> ConfigFlowResult:
        """Handle the initial step."""

        self._async_abort_entries_match({CONF_HOST: data[CONF_HOST]})
        errors, serial = await self.check_status(data[CONF_HOST])

        if not errors:
            if serial is not None:
                await self.async_set_unique_id(serial)
                self._abort_if_unique_id_configured()
        else:
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
        self.context.update({"title_placeholders": {"name": name}})
        return await self.async_step_discovery_confirm()

    async def async_step_discovery_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm discovery."""
        errors, _ = await self.check_status(self.discovery_info[CONF_HOST])
        if errors:
            if errors["base"] == "invalid_auth":
                return await self.async_step_auth()
            return self.async_abort(reason="unavailable_host")

        if user_input is None:
            self._set_confirm_only()
            return self.async_show_form(
                step_id="discovery_confirm",
                description_placeholders={"name": self.discovery_info[CONF_NAME]},
            )

        return self.async_create_entry(
            title=self.discovery_info[CONF_NAME],
            data={CONF_HOST: self.discovery_info[CONF_HOST]},
        )

    async def async_step_auth(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the authentication step."""

        errors: dict[str, str] = {}
        if user_input is not None:
            host = self._host or self.discovery_info[CONF_HOST]
            errors, serial = await self.check_status(
                host,
                user_input[CONF_USERNAME],
                user_input[CONF_PASSWORD],
            )

            if not errors:
                if self.unique_id is None and serial is not None:
                    await self.async_set_unique_id(serial)
                    self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=f"OpenEVSE {host}",
                    data={
                        CONF_HOST: host,
                        CONF_USERNAME: user_input[CONF_USERNAME],
                        CONF_PASSWORD: user_input[CONF_PASSWORD],
                    },
                )

        return self.async_show_form(
            step_id="auth",
            data_schema=self.add_suggested_values_to_schema(AUTH_SCHEMA, user_input),
            errors=errors,
        )
