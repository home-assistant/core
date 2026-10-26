"""Config flow for BUSY Bar."""

from typing import override

from busylib.exceptions import BusyBarAPIError, BusyBarError
import probatio

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_TOKEN
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from . import async_create_client
from .const import DOMAIN

SCHEMAS = {
    "user": probatio.Schema({probatio.Required(CONF_HOST): str}),
    "key": probatio.Schema(
        {
            probatio.Required(CONF_PASSWORD): TextSelector(
                TextSelectorConfig(type=TextSelectorType.PASSWORD)
            )
        }
    ),
}


class BusyConfigFlow(ConfigFlow, domain=DOMAIN):
    """Pair a discovered or manually addressed bar."""

    VERSION = 1
    _host: str
    _name = "BUSY Bar"

    @override
    async def async_step_user(
        self, user_input: dict[str, object] | None = None
    ) -> ConfigFlowResult:
        """Ask for the bar's local address without scanning the network."""
        if user_input is not None:
            await self.async_set_unique_id(None)
            self._host = str(user_input[CONF_HOST])
            return await self._async_pair("user")
        return self.async_show_form(step_id="user", data_schema=SCHEMAS["user"])

    @override
    async def async_step_zeroconf(
        self, discovery_info: ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Update an existing address or request discovery confirmation."""
        self._host = discovery_info.host
        self._name = discovery_info.properties.get("name") or "BUSY Bar"
        await self.async_set_unique_id(
            discovery_info.name.split(".")[0].removeprefix("busybar-")
        )
        self._abort_if_unique_id_configured(updates={CONF_HOST: self._host})
        self.context["title_placeholders"] = {"name": self._name}
        return await self.async_step_zeroconf_confirm()

    async def async_step_zeroconf_confirm(
        self, user_input: dict[str, object] | None = None
    ) -> ConfigFlowResult:
        """Confirm the discovered device before issuing a token."""
        if user_input is not None:
            return await self._async_pair("zeroconf_confirm")
        return self.async_show_form(
            step_id="zeroconf_confirm", description_placeholders={"name": self._name}
        )

    async def async_step_key(
        self, user_input: dict[str, object] | None = None
    ) -> ConfigFlowResult:
        """Ask for the API key and allow retries after refusal."""
        if user_input is not None:
            return await self._async_pair("key", str(user_input[CONF_PASSWORD]))
        return self.async_show_form(step_id="key", data_schema=SCHEMAS["key"])

    async def _async_pair(
        self, step_id: str, password: str | None = None
    ) -> ConfigFlowResult:
        """Check access mode, issue a token and verify the stable identity."""
        errors: dict[str, str] = {}
        try:
            async with await async_create_client(
                self.hass, self._host, password
            ) as client:
                mode = (await client.access()).mode
                if mode == "disabled":
                    return self.async_abort(reason="http_api_disabled")
                if mode == "key" and password is None:
                    return await self.async_step_key()
                device = await client.status_device()
                device_id = (device.usb_mac or "").replace(":", "").lower()
                if not device_id:
                    return self.async_abort(reason="cannot_connect")
                if self.unique_id is not None and self.unique_id != device_id:
                    return self.async_abort(reason="wrong_device")
                await self.async_set_unique_id(device_id)
                self._abort_if_unique_id_configured()
                issued = await client.access_token_mint(
                    f"Home Assistant {self.hass.config.location_name}"
                )
                if not issued.token:
                    await client.access_tokens_revoke(issued.short_id)
                    return self.async_abort(reason="cannot_connect")
                token = issued.token
        except BusyBarAPIError as err:
            errors["base"] = (
                "invalid_auth" if err.status_code in (401, 403) else "cannot_connect"
            )
        except BusyBarError, ValueError:
            errors["base"] = "cannot_connect"
        else:
            return self.async_create_entry(
                title=self._name, data={CONF_HOST: self._host, CONF_TOKEN: token}
            )
        return self.async_show_form(
            step_id=step_id,
            data_schema=SCHEMAS.get(step_id),
            errors=errors,
            description_placeholders={"name": self._name},
        )
