"""Config flow for System Bridge integration."""

import asyncio
from collections.abc import Mapping
import logging
from typing import Any, override

import probatio
from systembridgeconnector.exceptions import (
    AuthenticationException,
    BadRequestException,
    ConnectionClosedException,
    ConnectionErrorException,
)
from systembridgeconnector.http_client import HTTPClient
from systembridgeconnector.keys import is_client_key
from systembridgeconnector.models.keys import KeyClient
from systembridgeconnector.models.modules import GetData, Module
from systembridgeconnector.version import Version
from systembridgeconnector.websocket_client import WebSocketClient
from yarl import URL

from homeassistant.config_entries import (
    SOURCE_REAUTH,
    ConfigEntryState,
    ConfigFlow,
    ConfigFlowResult,
)
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv, instance_id
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from .const import DATA_WAIT_TIMEOUT, DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_AUTHENTICATE_DATA_SCHEMA = probatio.Schema(
    {probatio.Required(probatio.Secret(CONF_TOKEN)): cv.string}
)
STEP_USER_DATA_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_HOST): cv.string,
        probatio.Required(CONF_PORT, default=9170): cv.string,
        probatio.Required(probatio.Secret(CONF_TOKEN)): cv.string,
    }
)
STEP_RECONFIGURE_DATA_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_HOST): cv.string,
        probatio.Required(CONF_PORT): cv.string,
    }
)


async def async_get_key_client(hass: HomeAssistant) -> KeyClient:
    """Return this Home Assistant as a System Bridge client.

    The instance ID stays the same, so pairing or exchanging again replaces
    this Home Assistant's key rather than adding another.
    """
    return KeyClient(
        id=await instance_id.async_get(hass),
        name=hass.config.location_name,
        kind="home-assistant",
    )


def _pairing_code(text: str) -> str:
    """Return the pairing code from what was entered, the code or its link."""
    return URL(text).query.get("pair") or text


async def _async_pair(hass: HomeAssistant, data: dict[str, Any], code: str) -> str:
    """Trade a pairing code from System Bridge for this Home Assistant's key."""
    http_client = HTTPClient(
        data[CONF_HOST],
        data[CONF_PORT],
        "",
        session=async_get_clientsession(hass),
    )
    try:
        async with asyncio.timeout(DATA_WAIT_TIMEOUT):
            return await http_client.pair(code, await async_get_key_client(hass))
    except (AuthenticationException, BadRequestException) as exception:
        raise InvalidPairingCode from exception
    except (ConnectionErrorException, TimeoutError) as exception:
        raise CannotConnect from exception


async def _validate_input(
    hass: HomeAssistant,
    data: dict[str, Any],
    *,
    paired_keys: dict[str, str] | None = None,
) -> dict[str, str]:
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    With paired_keys, the token field takes a key, or a pairing code that is
    traded for one. Each key is kept against its code, as a code works once and
    a retry after a failed connection needs the same key. Without paired_keys,
    the stored key or old token is used as it is, and setup swaps an old token
    later.
    """
    session = async_get_clientsession(hass)
    version = Version(data[CONF_HOST], data[CONF_PORT], "", session=session)
    try:
        async with asyncio.timeout(DATA_WAIT_TIMEOUT):
            supported = await version.check_supported()
    except (ConnectionErrorException, TimeoutError) as exception:
        raise CannotConnect from exception
    # An older System Bridge turns the connector's sign-in away, so it would
    # otherwise look like a wrong key or pairing code
    if not supported:
        raise UnsupportedVersion

    key = data[CONF_TOKEN].strip()
    if paired_keys is not None and not is_client_key(key):
        code = _pairing_code(key)
        if code not in paired_keys:
            paired_keys[code] = await _async_pair(hass, data, code)
        key = paired_keys[code]

    websocket_client = WebSocketClient(
        data[CONF_HOST],
        data[CONF_PORT],
        key,
        session=session,
    )

    try:
        async with asyncio.timeout(DATA_WAIT_TIMEOUT):
            await websocket_client.connect()
            modules_data = await websocket_client.get_data(
                GetData(modules=[Module.SYSTEM])
            )
    except AuthenticationException as exception:
        _LOGGER.warning(
            "Authentication error when connecting to %s: %s",
            data[CONF_HOST],
            exception,
        )
        raise InvalidAuth from exception
    except (
        ConnectionClosedException,
        ConnectionErrorException,
    ) as exception:
        _LOGGER.warning(
            "Connection error when connecting to %s: %s", data[CONF_HOST], exception
        )
        raise CannotConnect from exception
    except TimeoutError as exception:
        _LOGGER.warning("Timed out connecting to %s: %s", data[CONF_HOST], exception)
        raise CannotConnect from exception
    except ValueError as exception:
        raise CannotConnect from exception

    _LOGGER.debug("Got modules data: %s", modules_data)
    if modules_data is None or modules_data.system is None:
        raise CannotConnect

    _LOGGER.debug("Got System data: %s", modules_data.system)

    return {
        "hostname": data[CONF_HOST],
        "uuid": modules_data.system.uuid,
        CONF_TOKEN: key,
    }


async def _async_get_info(
    hass: HomeAssistant,
    user_input: dict[str, Any],
    *,
    paired_keys: dict[str, str] | None = None,
) -> tuple[dict[str, str], dict[str, str] | None]:
    errors = {}

    try:
        info = await _validate_input(hass, user_input, paired_keys=paired_keys)
    except CannotConnect:
        errors["base"] = "cannot_connect"
    except InvalidAuth:
        errors["base"] = "invalid_auth"
    except InvalidPairingCode:
        errors["base"] = "invalid_pairing_code"
    except UnsupportedVersion:
        errors["base"] = "unsupported_version"
    except Exception:
        _LOGGER.exception("Unexpected exception")
        errors["base"] = "unknown"
    else:
        return errors, info

    return errors, None


class SystemBridgeConfigFlow(
    ConfigFlow,
    domain=DOMAIN,
):
    """Handle a config flow for System Bridge."""

    VERSION = 1
    MINOR_VERSION = 3

    _name: str

    def __init__(self) -> None:
        """Initialize flow."""
        self._input: dict[str, Any] = {}
        self._paired_keys: dict[str, str] = {}

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(
                step_id="user",
                data_schema=STEP_USER_DATA_SCHEMA,
            )

        errors, info = await _async_get_info(
            self.hass, user_input, paired_keys=self._paired_keys
        )
        if not errors and info is not None:
            # Check if already configured
            await self.async_set_unique_id(info["uuid"], raise_on_progress=False)
            # Pairing again replaces the key System Bridge holds for this
            # client, so the existing entry needs the new one
            self._abort_if_unique_id_configured(
                updates={
                    CONF_HOST: info["hostname"],
                    CONF_PORT: user_input[CONF_PORT],
                    CONF_TOKEN: info[CONF_TOKEN],
                }
            )

            return self.async_create_entry(
                title=info["hostname"],
                data={**user_input, CONF_TOKEN: info[CONF_TOKEN]},
            )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )

    async def async_step_authenticate(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle getting the api-key for authentication."""
        errors: dict[str, str] = {}

        if user_input is not None:
            user_input = {**self._input, **user_input}
            errors, info = await _async_get_info(
                self.hass, user_input, paired_keys=self._paired_keys
            )
            if not errors and info is not None:
                user_input[CONF_TOKEN] = info[CONF_TOKEN]
                await self.async_set_unique_id(info["uuid"])

                if self.source == SOURCE_REAUTH:
                    self._abort_if_unique_id_mismatch()
                    return self.async_update_reload_and_abort(
                        self._get_reauth_entry(), data=user_input
                    )

                self._abort_if_unique_id_configured(
                    updates={
                        CONF_HOST: info["hostname"],
                        CONF_PORT: user_input[CONF_PORT],
                        CONF_TOKEN: info[CONF_TOKEN],
                    }
                )

                return self.async_create_entry(title=info["hostname"], data=user_input)

        return self.async_show_form(
            step_id="authenticate",
            data_schema=STEP_AUTHENTICATE_DATA_SCHEMA,
            description_placeholders={
                "name": self._name,
            },
            errors=errors,
        )

    @override
    async def async_step_zeroconf(
        self, discovery_info: ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Handle zeroconf discovery."""
        properties = discovery_info.properties
        host = properties.get("ip")
        uuid = properties.get("uuid")

        if host is None or uuid is None:
            return self.async_abort(reason="unknown")

        # Check if already configured
        entry = await self.async_set_unique_id(uuid)
        updates = {CONF_HOST: host}
        if (port := properties.get("port")) is not None:
            updates[CONF_PORT] = port
        # The host announces itself on startup and wake. A changed host or
        # port reloads the entry instead
        if (
            entry is not None
            and entry.state is ConfigEntryState.LOADED
            and entry.data == {**entry.data, **updates}
        ):
            entry.runtime_data.async_reconnect_now()
        self._abort_if_unique_id_configured(updates=updates)

        self._name = host
        self._input = {
            CONF_HOST: host,
            CONF_PORT: port,
        }

        return await self.async_step_authenticate()

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration of the host and port."""
        reconfigure_entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}

        if user_input is not None:
            # The stored token may still be the old one, which setup swaps
            # once it connects, so it's never a pairing code here
            errors, info = await _async_get_info(
                self.hass, {**reconfigure_entry.data, **user_input}
            )
            if not errors and info is not None:
                await self.async_set_unique_id(info["uuid"])
                self._abort_if_unique_id_mismatch()
                return self.async_update_reload_and_abort(
                    reconfigure_entry, data_updates=user_input
                )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                STEP_RECONFIGURE_DATA_SCHEMA,
                user_input or reconfigure_entry.data,
            ),
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Perform reauth upon an API authentication error."""
        self._name = entry_data[CONF_HOST]
        self._input = {
            CONF_HOST: entry_data[CONF_HOST],
            CONF_PORT: entry_data[CONF_PORT],
        }
        return await self.async_step_authenticate()


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""


class InvalidPairingCode(HomeAssistantError):
    """Error to indicate the pairing code is wrong, used or expired."""


class UnsupportedVersion(HomeAssistantError):
    """Error to indicate the System Bridge version isn't supported."""
