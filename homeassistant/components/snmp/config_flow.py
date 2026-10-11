"""Config flow for SNMP."""

from collections.abc import Mapping
import logging
from typing import Any, override

import probatio
from pysnmp.error import PySnmpError
from pysnmp.hlapi.v3arch.asyncio import get_cmd
from pysnmp.proto import errind
from pysnmp.smi.error import WrongValueError

from homeassistant.config_entries import (
    SOURCE_REAUTH,
    SOURCE_RECONFIGURE,
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    ConfigSubentryFlow,
    SubentryFlowResult,
)
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_USERNAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import AbortFlow
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.selector import (
    SelectSelector,
    SelectSelectorConfig,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import (
    CONF_AUTH_KEY,
    CONF_AUTH_PROTOCOL,
    CONF_BASEOID,
    CONF_COMMUNITY,
    CONF_CONTEXT_NAME,
    CONF_INTERVAL_SECONDS,
    CONF_PRIV_KEY,
    CONF_PRIV_PROTOCOL,
    CONF_VERSION,
    DEFAULT_AUTH_PROTOCOL,
    DEFAULT_COMMUNITY,
    DEFAULT_INTERVAL_SECONDS,
    DEFAULT_PORT,
    DEFAULT_PRIV_PROTOCOL,
    DEFAULT_TIMEOUT,
    DEFAULT_VERSION,
    DEVICE_TRACKER_SUBENTRY_TITLE,
    DOMAIN,
    MAP_AUTH_PROTOCOLS,
    MAP_PRIV_PROTOCOLS,
    SNMP_VERSIONS,
    SUBENTRY_TYPE_DEVICE_TRACKER,
)
from .util import (
    async_create_request_cmd_args,
    async_create_transport_target,
    async_validate_oid,
    create_auth_data,
)

_LOGGER = logging.getLogger(__name__)

PASSWORD_SELECTOR = TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD))

SNMP_VERSION_SELECTOR = SelectSelector(
    SelectSelectorConfig(options=list(SNMP_VERSIONS), translation_key="version")
)
AUTH_PROTOCOL_SELECTOR = SelectSelector(
    SelectSelectorConfig(
        options=list(MAP_AUTH_PROTOCOLS), translation_key="auth_protocol"
    )
)
PRIV_PROTOCOL_SELECTOR = SelectSelector(
    SelectSelectorConfig(
        options=list(MAP_PRIV_PROTOCOLS), translation_key="priv_protocol"
    )
)

STEP_USER_DATA_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_HOST): str,
        probatio.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
        probatio.Optional(CONF_VERSION, default=DEFAULT_VERSION): SNMP_VERSION_SELECTOR,
    }
)

STEP_V1_V2C_DATA_SCHEMA = probatio.Schema(
    {
        probatio.Optional(CONF_COMMUNITY, default=DEFAULT_COMMUNITY): PASSWORD_SELECTOR,
    }
)

STEP_V3_DATA_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_USERNAME): str,
        probatio.Optional(CONF_AUTH_KEY): PASSWORD_SELECTOR,
        probatio.Optional(
            CONF_AUTH_PROTOCOL, default=DEFAULT_AUTH_PROTOCOL
        ): AUTH_PROTOCOL_SELECTOR,
        probatio.Optional(CONF_PRIV_KEY): PASSWORD_SELECTOR,
        probatio.Optional(
            CONF_PRIV_PROTOCOL, default=DEFAULT_PRIV_PROTOCOL
        ): PRIV_PROTOCOL_SELECTOR,
        probatio.Optional(CONF_CONTEXT_NAME): str,
    }
)

DEVICE_TRACKER_DATA_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_BASEOID): str,
        probatio.Optional(
            CONF_INTERVAL_SECONDS, default=DEFAULT_INTERVAL_SECONDS
        ): cv.positive_int,
    }
)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> None:
    """Validate the user input allows us to connect."""
    host = data[CONF_HOST]
    port = data.get(CONF_PORT, DEFAULT_PORT)
    version = data.get(CONF_VERSION, DEFAULT_VERSION)
    context_name = data.get(CONF_CONTEXT_NAME)

    try:
        target = await async_create_transport_target(host, port, DEFAULT_TIMEOUT)
    except PySnmpError as err:
        _LOGGER.warning("SNMP target creation failed: %s", err)
        raise CannotConnect from err

    try:
        auth_data = create_auth_data(data, version)
    except PySnmpError as err:
        raise InvalidAuth from err

    # Use sysDescr.0 to verify connectivity and authentication.
    # This OID is standard and responds to GET on almost all devices.
    test_oid = "1.3.6.1.2.1.1.1.0"
    request_args = await async_create_request_cmd_args(
        hass, auth_data, target, test_oid, context_name
    )

    try:
        err_indication, err_status, _, _ = await get_cmd(*request_args)
    except WrongValueError as err:
        # pysnmp raises WrongValueError when v3 credentials/keys match the wrong protocol
        raise UsmWrongDigests from err
    except PySnmpError as err:
        # Handle other pysnmp errors like StatusInformation/SerializationError
        raise CannotConnect from err

    if err_indication:
        if err_indication in (errind.requestTimedOut, errind.emptyResponse):
            raise SnmpTimeout from Exception(str(err_indication))
        if err_indication in (
            errind.wrongDigest,
            errind.decryptionError,
        ):
            raise UsmWrongDigests from Exception(str(err_indication))
        if err_indication in (
            errind.unknownCommunityName,
            errind.unknownUserName,
            errind.unknownSecurityName,
            errind.unsupportedSecurityLevel,
            errind.unsupportedSecurityModel,
            errind.unsupportedAuthProtocol,
            errind.unsupportedPrivProtocol,
            errind.authenticationFailure,
            errind.authenticationError,
        ):
            raise InvalidAuth from Exception(str(err_indication))
        raise CannotConnect from Exception(str(err_indication))

    if version == "3" and err_status:
        err_status_str = err_status.prettyPrint()
        if (
            "wrongdigests" in err_status_str.lower()
            or "decryptionerror" in err_status_str.lower()
        ):
            raise UsmWrongDigests from Exception(err_status_str)
        # A non-crypto err_status (e.g. VACM access denial on sysDescr.0) means
        # the agent answered, so the credentials themselves are accepted.
        _LOGGER.debug(
            "sysDescr.0 returned err_status %s, treating credentials as valid",
            err_status_str,
        )


class SnmpConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for an SNMP device."""

    VERSION = 1
    MINOR_VERSION = 1
    _user_data: dict[str, Any]

    @classmethod
    @callback
    @override
    def async_get_supported_subentry_types(
        cls, config_entry: ConfigEntry
    ) -> dict[str, type[ConfigSubentryFlow]]:
        """Return subentries supported by this handler."""
        return {SUBENTRY_TYPE_DEVICE_TRACKER: SnmpDeviceTrackerSubentryFlow}

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        if user_input is not None:
            self._user_data = user_input
            return await self._async_step_credentials()

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, last_step=False
        )

    async def async_step_v1_v2c(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle V1/V2c authentication."""
        return await self._async_step_credentials(user_input)

    async def async_step_v3(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle V3 authentication."""
        return await self._async_step_credentials(user_input)

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the reconfiguration of an existing device."""
        entry = self._get_reconfigure_entry()

        if user_input is not None:
            self._user_data = user_input
            return await self._async_step_credentials()

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_DATA_SCHEMA, entry.data
            ),
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle the credentials of a request which failed to authenticate."""
        self._user_data = dict(entry_data)
        return await self._async_step_credentials()

    async def _async_step_credentials(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for the credentials of the selected version, then store them."""
        is_v3 = self._user_data[CONF_VERSION] == "3"
        errors: dict[str, str] = {}

        if user_input is not None:
            if is_v3:
                errors = self._validate_v3_coherence(user_input)

            if not errors:
                data = {**self._user_data, **user_input}
                if result := await self._async_finish(data, errors):
                    return result

        return self.async_show_form(
            step_id="v3" if is_v3 else "v1_v2c",
            data_schema=self.add_suggested_values_to_schema(
                STEP_V3_DATA_SCHEMA if is_v3 else STEP_V1_V2C_DATA_SCHEMA, user_input
            ),
            errors=errors,
        )

    @staticmethod
    def _validate_v3_coherence(data: dict[str, Any]) -> dict[str, str]:
        """Return an error for every key and protocol which does not pair up.

        A protocol without its key is dropped by pysnmp, which silently builds a
        session with a lower security level than the user selected, and a key
        without a protocol is refused with a generic authentication error.
        """
        auth_key = data.get(CONF_AUTH_KEY) or None
        priv_key = data.get(CONF_PRIV_KEY) or None
        auth_proto: str = data.get(CONF_AUTH_PROTOCOL, DEFAULT_AUTH_PROTOCOL)
        priv_proto: str = data.get(CONF_PRIV_PROTOCOL, DEFAULT_PRIV_PROTOCOL)

        if priv_key and not auth_key:
            return {CONF_AUTH_KEY: "auth_key_required_for_priv"}
        if auth_key and auth_proto == DEFAULT_AUTH_PROTOCOL:
            return {CONF_AUTH_PROTOCOL: "auth_protocol_required_for_auth_key"}
        if auth_proto != DEFAULT_AUTH_PROTOCOL and not auth_key:
            return {CONF_AUTH_KEY: "auth_key_required_for_auth_protocol"}
        if priv_key and priv_proto == DEFAULT_PRIV_PROTOCOL:
            return {CONF_PRIV_PROTOCOL: "priv_protocol_required_for_priv_key"}
        if priv_proto != DEFAULT_PRIV_PROTOCOL and not priv_key:
            return {CONF_PRIV_KEY: "priv_key_required_for_priv_protocol"}
        return {}

    async def async_step_import(self, user_input: dict[str, Any]) -> ConfigFlowResult:
        """Import the YAML configuration as a device and a device tracker subentry."""
        # The legacy YAML schema had no way to specify SNMPv3 protocols, so a
        # configuration with v3 keys cannot be turned into a working v3 entry.
        if CONF_AUTH_KEY in user_input or CONF_PRIV_KEY in user_input:
            return self.async_abort(reason="credentials_required")

        # The legacy platform schema adds keys (platform, consider_home,
        # new_device_defaults) which are not part of a config entry.
        entry_data: dict[str, Any] = {
            CONF_HOST: user_input[CONF_HOST],
            CONF_PORT: user_input.get(CONF_PORT, DEFAULT_PORT),
            CONF_VERSION: user_input.get(CONF_VERSION, DEFAULT_VERSION),
            CONF_COMMUNITY: user_input.get(CONF_COMMUNITY, DEFAULT_COMMUNITY),
        }
        self._abort_if_already_configured(entry_data)

        tracker_data: dict[str, Any] = {CONF_BASEOID: user_input[CONF_BASEOID]}
        if interval := user_input.get(CONF_INTERVAL_SECONDS):
            tracker_data[CONF_INTERVAL_SECONDS] = interval

        return self.async_create_entry(
            title=entry_data[CONF_HOST],
            data=entry_data,
            subentries=[
                {
                    "subentry_type": SUBENTRY_TYPE_DEVICE_TRACKER,
                    "title": DEVICE_TRACKER_SUBENTRY_TITLE,
                    "unique_id": SUBENTRY_TYPE_DEVICE_TRACKER,
                    "data": tracker_data,
                }
            ],
        )

    @callback
    def _abort_if_already_configured(self, data: dict[str, Any]) -> None:
        """Abort when the same device is already configured.

        The context name is compared explicitly: two SNMPv3 devices on the same
        host and port can be addressed through different contexts. The entry
        being reconfigured or reauthenticated is not a duplicate of itself.
        """
        current_entry_id = self.context.get("entry_id")
        for entry in self._async_current_entries(include_ignore=False):
            if entry.entry_id == current_entry_id:
                continue
            if (
                entry.data.get(CONF_HOST) == data[CONF_HOST]
                and entry.data.get(CONF_PORT, DEFAULT_PORT)
                == data.get(CONF_PORT, DEFAULT_PORT)
                and entry.data.get(CONF_CONTEXT_NAME) == data.get(CONF_CONTEXT_NAME)
            ):
                raise AbortFlow("already_configured")

    async def _async_finish(
        self,
        data: dict[str, Any],
        errors: dict[str, str],
    ) -> ConfigFlowResult | None:
        """Validate the credentials and create or update the config entry."""
        self._abort_if_already_configured(data)

        try:
            await validate_input(self.hass, data)
        except SnmpTimeout:
            errors["base"] = "snmp_timeout"
        except CannotConnect:
            errors["base"] = "cannot_connect"
        except UsmWrongDigests:
            errors["base"] = "usm_wrong_digests"
        except InvalidAuth:
            errors["base"] = "invalid_auth"
        else:
            if self.source == SOURCE_RECONFIGURE:
                return self.async_update_and_abort(
                    self._get_reconfigure_entry(), title=data[CONF_HOST], data=data
                )
            if self.source == SOURCE_REAUTH:
                return self.async_update_and_abort(
                    self._get_reauth_entry(), title=data[CONF_HOST], data=data
                )
            return self.async_create_entry(title=data[CONF_HOST], data=data)
        return None


class SnmpDeviceTrackerSubentryFlow(ConfigSubentryFlow):
    """Handle the device tracker subentry of an SNMP device."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Add a device tracker to the SNMP device."""
        if self._get_entry().get_subentries_of_type(SUBENTRY_TYPE_DEVICE_TRACKER):
            return self.async_abort(reason="already_configured")

        errors: dict[str, str] = {}
        if user_input is not None:
            if await async_validate_oid(self.hass, user_input[CONF_BASEOID]):
                return self.async_create_entry(
                    title=DEVICE_TRACKER_SUBENTRY_TITLE,
                    data=user_input,
                    unique_id=SUBENTRY_TYPE_DEVICE_TRACKER,
                )
            errors[CONF_BASEOID] = "invalid_oid"

        return self.async_show_form(
            step_id="user",
            data_schema=DEVICE_TRACKER_DATA_SCHEMA,
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Change the device tracker of the SNMP device."""
        subentry = self._get_reconfigure_subentry()

        errors: dict[str, str] = {}
        if user_input is not None:
            if await async_validate_oid(self.hass, user_input[CONF_BASEOID]):
                return self.async_update_and_abort(
                    self._get_entry(), subentry, data=user_input
                )
            errors[CONF_BASEOID] = "invalid_oid"

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                DEVICE_TRACKER_DATA_SCHEMA, user_input or subentry.data
            ),
            errors=errors,
        )


class CannotConnect(Exception):
    """Error to indicate we cannot connect."""


class SnmpTimeout(CannotConnect):
    """Error to indicate query timed out."""


class InvalidAuth(Exception):
    """Error to indicate there is invalid auth."""


class UsmWrongDigests(InvalidAuth):
    """Error to indicate wrong authentication/privacy keys or digests."""
