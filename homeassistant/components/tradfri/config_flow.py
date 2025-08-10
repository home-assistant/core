"""Config flow for Tradfri."""

from __future__ import annotations

import asyncio
from typing import Any, cast
from uuid import uuid4

from pytradfri import Gateway, RequestError
from pytradfri.api.aiocoap_api import APIFactory
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers.service_info.zeroconf import (
    ATTR_PROPERTIES_ID,
    ZeroconfServiceInfo,
)

from .const import CONF_GATEWAY_ID, CONF_IDENTITY, CONF_KEY, DOMAIN

KEY_SECURITY_CODE = "security_code"


class AuthError(Exception):
    """Exception if authentication occurs."""

    def __init__(self, code: str) -> None:
        """Initialize exception."""
        super().__init__()
        self.code = code


class FlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a config flow."""

    VERSION = 2

    def __init__(self) -> None:
        """Initialize flow."""
        self._host: str | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""
        return await self.async_step_auth()

    async def async_step_auth(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the authentication with a gateway."""
        errors: dict[str, str] = {}

        if user_input is not None:
            host = cast(str, user_input.get(CONF_HOST, self._host))
            try:
                auth = await authenticate(
                    self.hass, host, user_input[KEY_SECURITY_CODE]
                )

                return await self._entry_from_data(auth)

            except AuthError as err:
                errors["base"] = err.code
        else:
            user_input = {}

        fields = {}

        if self._host is None:
            fields[vol.Required(CONF_HOST, default=user_input.get(CONF_HOST))] = str

        fields[
            vol.Required(KEY_SECURITY_CODE, default=user_input.get(KEY_SECURITY_CODE))
        ] = str

        return self.async_show_form(
            step_id="auth", data_schema=vol.Schema(fields), errors=errors
        )

    async def async_step_homekit(
        self, discovery_info: ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Handle homekit discovery."""
        await self.async_set_unique_id(discovery_info.properties[ATTR_PROPERTIES_ID])
        self._abort_if_unique_id_configured({CONF_HOST: discovery_info.host})

        host = discovery_info.host

        for entry in self._async_current_entries():
            if entry.data.get(CONF_HOST) != host:
                continue

            # Backwards compat, we update old entries
            if not entry.unique_id:
                self.hass.config_entries.async_update_entry(
                    entry,
                    unique_id=discovery_info.properties[ATTR_PROPERTIES_ID],
                )

            return self.async_abort(reason="already_configured")

        self._host = host
        return await self.async_step_auth()

    async def _entry_from_data(self, data: dict[str, Any]) -> ConfigFlowResult:
        """Create an entry from data."""
        host = data[CONF_HOST]
        gateway_id = data[CONF_GATEWAY_ID]

        same_hub_entries = [
            entry.entry_id
            for entry in self._async_current_entries()
            if entry.data.get(CONF_GATEWAY_ID) == gateway_id
            or entry.data.get(CONF_HOST) == host
        ]

        if same_hub_entries:
            await asyncio.wait(
                [
                    asyncio.create_task(self.hass.config_entries.async_remove(entry_id))
                    for entry_id in same_hub_entries
                ]
            )

        return self.async_create_entry(title=host, data=data)


async def authenticate(
    hass: HomeAssistant, host: str, security_code: str
) -> dict[str, str | bool]:
    """Authenticate with a Tradfri hub."""

    identity = uuid4().hex

    api_factory = await APIFactory.init(host, psk_id=identity)

    try:
        async with asyncio.timeout(5):
            key = await api_factory.generate_psk(security_code)
    except RequestError as err:
        raise AuthError("invalid_security_code") from err
    except TimeoutError as err:
        raise AuthError("timeout") from err
    finally:
        await api_factory.shutdown()
    if key is None:
        raise AuthError("cannot_authenticate")
    return await get_gateway_info(hass, host, identity, key)


async def get_gateway_info(
    hass: HomeAssistant, host: str, identity: str, key: str
) -> dict[str, str | bool]:
    """Return info for the gateway."""

    try:
        factory = await APIFactory.init(host, psk_id=identity, psk=key)

        api = factory.request
        gateway = Gateway()
        gateway_info_result = await api(gateway.get_gateway_info())

        await factory.shutdown()
    except (OSError, RequestError) as err:
        # We're also catching OSError as PyTradfri doesn't catch that one yet
        # Upstream PR: https://github.com/ggravlingen/pytradfri/pull/189
        raise AuthError("cannot_connect") from err

    return {
        CONF_HOST: host,
        CONF_IDENTITY: identity,
        CONF_KEY: key,
        CONF_GATEWAY_ID: gateway_info_result.id,
    }
