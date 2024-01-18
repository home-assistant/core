"""Config flow for the Bang & Olufsen integration."""
from __future__ import annotations

from ipaddress import AddressValueError, IPv4Address
from typing import Any, TypedDict

from aiohttp.client_exceptions import ClientConnectorError
from mozart_api.exceptions import ApiException
from mozart_api.mozart_client import MozartClient
import voluptuous as vol

from homeassistant.components.zeroconf import ZeroconfServiceInfo
from homeassistant.config_entries import ConfigFlow
from homeassistant.const import CONF_HOST, CONF_MODEL
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.selector import SelectSelector, SelectSelectorConfig

from .const import (
    ATTR_FRIENDLY_NAME,
    ATTR_ITEM_NUMBER,
    ATTR_SERIAL_NUMBER,
    ATTR_TYPE_NUMBER,
    COMPATIBLE_MODELS,
    DEFAULT_MODEL,
    DOMAIN,
)


class EntryData(TypedDict, total=False):
    """TypedDict for config_entry data."""

    host: str
    jid: str
    model: str
    name: str


class BangOlufsenConfigFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a config flow."""

    _beolink_jid = ""
    _client: MozartClient
    _host = ""
    _model = ""
    _name = ""
    _serial_number = ""

    def __init__(self) -> None:
        """Init the config flow."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        data_schema = vol.Schema(
            {
                vol.Required(CONF_HOST): str,
                vol.Required(CONF_MODEL, default=DEFAULT_MODEL): SelectSelector(
                    SelectSelectorConfig(options=COMPATIBLE_MODELS)
                ),
            }
        )

        if user_input is not None:
            self._host = user_input[CONF_HOST]
            self._model = user_input[CONF_MODEL]

            # Check if the IP address is a valid address.
            try:
                IPv4Address(self._host)
            except AddressValueError:
                return self.async_show_form(
                    step_id="user",
                    data_schema=data_schema,
                    errors={"base": "value_error"},
                )

            self._client = MozartClient(self._host)

            # Try to get information from Beolink self method.
            async with self._client:
                try:
                    beolink_self = await self._client.get_beolink_self(
                        _request_timeout=3
                    )

                except (
                    ApiException,
                    ClientConnectorError,
                    TimeoutError,
                ) as error:
                    return self.async_show_form(
                        step_id="user",
                        data_schema=data_schema,
                        errors={
                            "base": {
                                ApiException: "api_exception",
                                ClientConnectorError: "client_connector_error",
                                TimeoutError: "timeout_error",
                            }[type(error)]
                        },
                    )

            self._beolink_jid = beolink_self.jid
            self._serial_number = beolink_self.jid.split(".")[2].split("@")[0]

            return await self._create_entry()

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
        )

    async def async_step_zeroconf(
        self, discovery_info: ZeroconfServiceInfo
    ) -> FlowResult:
        """Handle discovery using Zeroconf."""

        # Check if the discovered device is a Mozart device
        if ATTR_FRIENDLY_NAME not in discovery_info.properties:
            return self.async_abort(reason="not_mozart_device")

        # Ensure that an IPv4 address is received
        self._host = discovery_info.host
        try:
            IPv4Address(self._host)
        except AddressValueError:
            return self.async_abort(reason="ipv6_address")

        self._model = discovery_info.hostname[:-16].replace("-", " ")
        self._serial_number = discovery_info.properties[ATTR_SERIAL_NUMBER]
        self._beolink_jid = f"{discovery_info.properties[ATTR_TYPE_NUMBER]}.{discovery_info.properties[ATTR_ITEM_NUMBER]}.{self._serial_number}@products.bang-olufsen.com"

        return await self._create_entry()

    async def _create_entry(self) -> FlowResult:
        """Create the config entry for a discovered or manually configured Bang & Olufsen device."""
        await self.async_set_unique_id(self._serial_number)
        self._abort_if_unique_id_configured(updates={CONF_HOST: self._host})

        # Ensure that created entities have a unique and easily identifiable id and not a "friendly name"
        self._name = f"{self._model}-{self._serial_number}"

        return self.async_create_entry(
            title=self._name,
            data=EntryData(
                host=self._host,
                jid=self._beolink_jid,
                model=self._model,
                name=self._name,
            ),
        )
