"""Config flow for BUSY Bar."""

from typing import Any, override

from busylib import AsyncBusyBar
from busylib.exceptions import BusyBarAPIError, BusyBarError
from busylib.transports import AiohttpTransport
import probatio

from homeassistant.config_entries import SOURCE_USER, ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_API_KEY, CONF_HOST, CONF_TOKEN
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import TextSelector, TextSelectorType
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from .const import DOMAIN

USER_SCHEMA = probatio.Schema({probatio.Required(CONF_HOST): str})
KEY_SCHEMA = probatio.Schema(
    {probatio.Required(CONF_API_KEY): TextSelector({"type": TextSelectorType.PASSWORD})}
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
        async with AsyncBusyBar(
            self._host,
            token=api_key,
            transport=AiohttpTransport(async_get_clientsession(self.hass)),
            timeout=10,
        ) as client:
            try:
                mode = (await client.access()).mode
            except (BusyBarError, ValueError) as err:
                return self._async_show_pair_form(step_id, _pair_error(err))
            if mode == "disabled":
                return self.async_abort(reason="http_api_disabled")
            if mode == "key" and api_key is None:
                return await self.async_step_key()
            if self.source == SOURCE_USER:
                try:
                    device = await client.status_device()
                except (BusyBarError, ValueError) as err:
                    return self._async_show_pair_form(step_id, _pair_error(err))
                await self.async_set_unique_id(
                    (device.usb_mac or "").replace(":", "").lower(),
                    raise_on_progress=False,
                )
            self._abort_if_unique_id_configured()
            try:
                issued = await client.access_token_mint(
                    f"Home Assistant {self.hass.config.location_name}"
                )
            except (BusyBarError, ValueError) as err:
                return self._async_show_pair_form(step_id, _pair_error(err))
        return self.async_create_entry(
            title=self._name, data={CONF_HOST: self._host, CONF_TOKEN: issued.token}
        )

    def _async_show_pair_form(self, step_id: str, error: str) -> ConfigFlowResult:
        """Show the step's form again with a pairing error."""
        return self.async_show_form(
            step_id=step_id,
            data_schema={"user": USER_SCHEMA, "key": KEY_SCHEMA}.get(step_id),
            errors={"base": error},
            description_placeholders={"name": self._name},
        )


def _pair_error(err: Exception) -> str:
    """Tell a refused key from a bar that cannot be reached."""
    if isinstance(err, BusyBarAPIError) and err.status_code in (401, 403):
        return "invalid_auth"
    return "cannot_connect"
