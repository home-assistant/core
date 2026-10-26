"""Config flow for BUSY Bar."""

from typing import Any, override

from busylib import AsyncBusyBar
from busylib.exceptions import BusyBarAPIError, BusyBarError
from busylib.transports import AiohttpTransport
import probatio

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_API_KEY, CONF_HOST, CONF_TOKEN
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from .const import DOMAIN

USER_SCHEMA = probatio.Schema({probatio.Required(CONF_HOST): str})
KEY_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_API_KEY): TextSelector(
            TextSelectorConfig(type=TextSelectorType.PASSWORD)
        )
    }
)


class BusyConfigFlow(ConfigFlow, domain=DOMAIN):
    """Pair a discovered or manually addressed bar."""

    VERSION = 1
    _host: str
    _name = "BUSY Bar"

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for the bar's local address without scanning the network."""
        if user_input is not None:
            self._host = user_input[CONF_HOST]
            return await self._async_pair("user")
        return self.async_show_form(step_id="user", data_schema=USER_SCHEMA)

    @override
    async def async_step_zeroconf(
        self, discovery_info: ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Update an existing address or request discovery confirmation."""
        self._host = discovery_info.host
        self._name = discovery_info.properties.get("name") or self._name
        await self.async_set_unique_id(
            discovery_info.name.split(".")[0].removeprefix("busybar-")
        )
        self._abort_if_unique_id_configured(updates={CONF_HOST: self._host})
        self.context["title_placeholders"] = {"name": self._name}
        return await self.async_step_zeroconf_confirm()

    async def async_step_zeroconf_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm the discovered device before issuing a token."""
        if user_input is not None:
            return await self._async_pair("zeroconf_confirm")
        return self.async_show_form(
            step_id="zeroconf_confirm", description_placeholders={"name": self._name}
        )

    async def async_step_key(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for the API key and allow retries after refusal."""
        if user_input is not None:
            return await self._async_pair("key", user_input[CONF_API_KEY])
        return self.async_show_form(step_id="key", data_schema=KEY_SCHEMA)

    async def _async_pair(
        self, step_id: str, api_key: str | None = None
    ) -> ConfigFlowResult:
        """Check access and identity before issuing a token."""
        errors: dict[str, str] = {}
        try:
            async with AsyncBusyBar(
                self._host,
                token=api_key,
                transport=AiohttpTransport(async_get_clientsession(self.hass)),
                timeout=10,
            ) as client:
                mode = (await client.access()).mode
                if mode == "disabled":
                    return self.async_abort(reason="http_api_disabled")
                if mode == "key" and api_key is None:
                    return await self.async_step_key()
                device = await client.status_device()
                device_id = (device.usb_mac or "").replace(":", "").lower()
                await self.async_set_unique_id(device_id)
                self._abort_if_unique_id_configured()
                issued = await client.access_token_mint(
                    f"Home Assistant {self.hass.config.location_name}"
                )
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
            data_schema=(
                USER_SCHEMA
                if step_id == "user"
                else KEY_SCHEMA
                if step_id == "key"
                else None
            ),
            errors=errors,
            description_placeholders={"name": self._name},
        )
