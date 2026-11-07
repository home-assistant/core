"""Config flow to configure the LG Soundbar integration."""

from typing import Any, override

from aiotemescal import (
    MSG_MAC_INFO_DEV,
    MSG_PRODUCT_INFO,
    MSG_SPK_LIST_VIEW_INFO,
    TemescalClient,
    TemescalConnectionError,
    TemescalTimeoutError,
)
import probatio

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from .const import DEFAULT_PORT, DOMAIN

DATA_SCHEMA = {
    probatio.Required(CONF_HOST): str,
}


async def _async_get_data(client: TemescalClient, msg: str) -> dict[str, Any]:
    """Return the data the device answers with, empty if it does not answer."""
    try:
        response = await client.request(msg)
    except TemescalTimeoutError:
        return {}
    return response.get("data") or {}


async def async_get_details(host: str, port: int) -> dict[str, str]:
    """Return the name and, if the device reports one, the uuid of a soundbar.

    Nothing is returned when the device does not report its name.
    """
    async with TemescalClient(host, port) as client:
        speaker = await _async_get_data(client, MSG_SPK_LIST_VIEW_INFO)
        if "s_user_name" not in speaker:
            return {}
        details = {"name": speaker["s_user_name"]}
        # Not every model reports its uuid in MAC_INFO_DEV
        for msg in (MSG_MAC_INFO_DEV, MSG_PRODUCT_INFO):
            if uuid := (await _async_get_data(client, msg)).get("s_uuid"):
                details["uuid"] = uuid
                break
    return details


class LGSoundbarConfigFlow(ConfigFlow, domain=DOMAIN):
    """LG Soundbar config flow."""

    VERSION = 1

    _host: str
    _port: int
    _name: str

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initiated by the user."""
        if user_input is None:
            return self._show_form()

        errors = {}
        try:
            details = await async_get_details(user_input[CONF_HOST], DEFAULT_PORT)
        except TemescalConnectionError:
            errors["base"] = "cannot_connect"
        else:
            if details:
                info = {
                    CONF_HOST: user_input[CONF_HOST],
                    CONF_PORT: DEFAULT_PORT,
                }
                if "uuid" in details:
                    await self.async_set_unique_id(details["uuid"])
                    self._abort_if_unique_id_configured()
                else:
                    self._async_abort_entries_match(info)
                return self.async_create_entry(title=details["name"], data=info)
            errors["base"] = "no_data"

        return self._show_form(errors)

    @override
    async def async_step_zeroconf(
        self, discovery_info: ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Handle a soundbar announcing itself over mDNS."""
        self._host = discovery_info.host
        self._port = discovery_info.port or DEFAULT_PORT
        self._async_abort_entries_match({CONF_HOST: self._host})

        try:
            details = await async_get_details(self._host, self._port)
        except TemescalConnectionError:
            return self.async_abort(reason="cannot_connect")
        if not details:
            return self.async_abort(reason="no_data")
        # The uuid of the announcement differs from the one the device reports,
        # which identifies entries set up by hand
        if "uuid" not in details:
            return self.async_abort(reason="not_supported")

        await self.async_set_unique_id(details["uuid"])
        self._abort_if_unique_id_configured(updates={CONF_HOST: self._host})
        self._name = details["name"]
        self.context["title_placeholders"] = {"name": self._name}
        return await self.async_step_zeroconf_confirm()

    async def async_step_zeroconf_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm the setup of a discovered soundbar."""
        if user_input is None:
            return self.async_show_form(
                step_id="zeroconf_confirm",
                description_placeholders={"name": self._name},
            )
        return self.async_create_entry(
            title=self._name,
            data={CONF_HOST: self._host, CONF_PORT: self._port},
        )

    def _show_form(self, errors: dict[str, str] | None = None) -> ConfigFlowResult:
        """Show the form to the user."""
        return self.async_show_form(
            step_id="user",
            data_schema=probatio.Schema(DATA_SCHEMA),
            errors=errors or {},
        )
