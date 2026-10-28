"""Config flow for the Daikin platform."""

import asyncio
import logging
from typing import Any, override
from uuid import uuid4

from aiohttp import ClientError, web_exceptions
import probatio
from pydaikin.daikin_base import Appliance
from pydaikin.discovery import Discovery
from pydaikin.exceptions import DaikinException
from pydaikin.factory import DaikinFactory

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_API_KEY, CONF_HOST, CONF_PASSWORD, CONF_UUID
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo
from homeassistant.util.ssl import client_context_no_verify

from .const import DOMAIN, KEY_MAC, TIMEOUT_SEC

_LOGGER = logging.getLogger(__name__)

RECONFIGURE_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_HOST): str,
        probatio.Optional(probatio.Secret(CONF_API_KEY)): str,
        probatio.Optional(probatio.Secret(CONF_PASSWORD)): str,
    }
)


class FlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a config flow."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the Daikin config flow."""
        self.host: str | None = None

    @property
    def schema(self) -> probatio.Schema:
        """Return current schema."""
        return probatio.Schema(
            {
                probatio.Required(CONF_HOST, default=self.host): str,
                probatio.Optional(probatio.Secret(CONF_API_KEY)): str,
                probatio.Optional(probatio.Secret(CONF_PASSWORD)): str,
            }
        )

    async def _create_entry(
        self,
        host: str,
        mac: str,
        key: str | None = None,
        uuid: str | None = None,
        password: str | None = None,
    ) -> ConfigFlowResult:
        """Register new entry."""
        if not self.unique_id:
            await self.async_set_unique_id(mac)
        self._abort_if_unique_id_configured()

        return self.async_create_entry(
            title=host,
            data={
                CONF_HOST: host,
                KEY_MAC: mac,
                CONF_API_KEY: key,
                CONF_UUID: uuid,
                CONF_PASSWORD: password,
            },
        )

    async def _async_validate_device(
        self, host: str, key: str | None = None, password: str | None = None
    ) -> tuple[dict[str, Any], dict[str, str]]:
        """Connect to the device and return the entry data or errors."""
        # BRP07Cxx devices needs uuid together with key
        if key:
            uuid = str(uuid4())
        else:
            uuid = None
            key = None

        if not password:
            password = None

        try:
            async with asyncio.timeout(TIMEOUT_SEC):
                device: Appliance = await DaikinFactory(
                    host,
                    async_get_clientsession(self.hass),
                    key=key,
                    uuid=uuid,
                    password=password,
                    ssl_context=client_context_no_verify(),
                )
        except TimeoutError, ClientError:
            self.host = None
            return {}, {"base": "cannot_connect"}
        except web_exceptions.HTTPForbidden:
            return {}, {"base": "invalid_auth"}
        except DaikinException:
            return {}, {"base": "cannot_connect"}
        except Exception:
            _LOGGER.exception("Unexpected error creating device")
            return {}, {"base": "unknown"}

        return {
            CONF_HOST: host,
            KEY_MAC: device.mac,
            CONF_API_KEY: key,
            CONF_UUID: uuid,
            CONF_PASSWORD: password,
        }, {}

    async def _create_device(
        self, host: str, key: str | None = None, password: str | None = None
    ) -> ConfigFlowResult:
        """Create device."""
        data, errors = await self._async_validate_device(host, key, password)
        if errors:
            return self.async_show_form(
                step_id="user", data_schema=self.schema, errors=errors
            )
        return await self._create_entry(
            host,
            data[KEY_MAC],
            data[CONF_API_KEY],
            data[CONF_UUID],
            data[CONF_PASSWORD],
        )

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """User initiated config flow."""
        if user_input is None:
            return self.async_show_form(step_id="user", data_schema=self.schema)
        if user_input.get(CONF_API_KEY) and user_input.get(CONF_PASSWORD):
            self.host = user_input[CONF_HOST]
            return self.async_show_form(
                step_id="user",
                data_schema=self.schema,
                errors={"base": "api_password"},
            )
        return await self._create_device(
            user_input[CONF_HOST],
            user_input.get(CONF_API_KEY),
            user_input.get(CONF_PASSWORD),
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration of the Daikin device."""
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}

        if user_input is not None:
            if user_input.get(CONF_API_KEY) and user_input.get(CONF_PASSWORD):
                errors["base"] = "api_password"
            else:
                data, errors = await self._async_validate_device(
                    user_input[CONF_HOST],
                    user_input.get(CONF_API_KEY),
                    user_input.get(CONF_PASSWORD),
                )
                if not errors:
                    mac = data.pop(KEY_MAC)
                    if entry.unique_id == entry.data[CONF_HOST]:
                        # Host based unique IDs cannot identify the device, setup
                        # migrates them once the device reports its MAC
                        self._async_abort_entries_match({CONF_HOST: data[CONF_HOST]})
                    else:
                        await self.async_set_unique_id(mac)
                        self._abort_if_unique_id_mismatch()
                    return self.async_update_reload_and_abort(entry, data_updates=data)

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                RECONFIGURE_SCHEMA,
                {CONF_HOST: (user_input or entry.data)[CONF_HOST]},
            ),
            errors=errors,
        )

    @override
    async def async_step_zeroconf(
        self, discovery_info: ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Prepare configuration for a discovered Daikin device."""
        _LOGGER.debug("Zeroconf user_input: %s", discovery_info)
        devices = Discovery().poll(ip=discovery_info.host)
        if not devices:
            _LOGGER.debug(
                (
                    "Could not find MAC-address for %s, make sure the required UDP"
                    " ports are open (see integration documentation)"
                ),
                discovery_info.host,
            )
            return self.async_abort(reason="cannot_connect")
        await self.async_set_unique_id(next(iter(devices))[KEY_MAC])
        self._abort_if_unique_id_configured()
        self.host = discovery_info.host
        return await self.async_step_user()
