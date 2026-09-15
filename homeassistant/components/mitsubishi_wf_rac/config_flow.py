"""Config flow WF-RAC."""

from collections.abc import Callable
from functools import partial
import logging
from typing import Any, override
from uuid import uuid4

import probatio
from pywfrac import RESULT_CODES, Repository, WfRacError

from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.const import (
    CONF_BASE,
    CONF_DEVICE_ID,
    CONF_FORCE_UPDATE,
    CONF_HOST,
    CONF_PORT,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import AbortFlow
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from .const import (
    AC_CERT_FILENAME,
    CONF_AIRCO_ID,
    CONF_OPERATOR_ID,
    DEFAULT_PORT,
    DOMAIN,
)
from .coordinator import result_code

_LOGGER = logging.getLogger(__name__)


class WfRacConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow."""

    VERSION = 7
    DOMAIN = DOMAIN

    def __init__(self) -> None:
        """Start a flow with no identifiers generated yet."""
        self._discovery_info: dict[str, Any] = {}
        self._generated_operator_id: str | None = None
        self._generated_device_id: str | None = None

    @override
    def is_matching(self, other_flow: WfRacConfigFlow) -> bool:
        """Return True if two flows are attempting to configure the same device."""
        if self.unique_id and other_flow.unique_id:
            return self.unique_id == other_flow.unique_id
        return False

    def _find_entry_matching(
        self, key: str, matches: Callable[[Any], bool]
    ) -> config_entries.ConfigEntry | None:
        """Returns the first entry where matches(entry.data[key]) returns True."""
        for entry in self._async_current_entries():
            if key in entry.data and matches(entry.data[key]):
                return entry
        return None

    async def _async_register_airco(
        self,
        hass: HomeAssistant,
        data: dict[str, Any],
        allow_port_fallback: bool = False,
    ) -> dict[str, Any]:
        """Validate the user input allows us to connect, and register with the airco device.

        allow_port_fallback belongs to discovery only: a port the module
        announced may be wrong, a port a person typed is their decision.
        """
        if len(data[CONF_HOST]) < 3:
            raise InvalidHost

        if not data.get(CONF_FORCE_UPDATE):
            existing_entry = self._find_entry_matching(
                CONF_HOST, lambda h: h == data[CONF_HOST]
            )
            if existing_entry:
                raise HostAlreadyConfigured(error_name=existing_entry.title)

        repository = Repository(
            async_get_clientsession(hass),
            data[CONF_HOST],
            data[CONF_PORT],
            data[CONF_OPERATOR_ID],
            data[CONF_DEVICE_ID],
            cert_path=hass.config.path(AC_CERT_FILENAME),
        )

        try:
            airco_id = await repository.get_airco_id()
        except (WfRacError, KeyError, TypeError) as query_failed:
            # Announcements have been seen carrying a port the module does
            # not serve, and the port is fixed in the firmware - so try that
            # one. Only an announced value is second-guessed.
            if not allow_port_fallback or data[CONF_PORT] == DEFAULT_PORT:
                raise CannotConnect(reason=str(query_failed)) from query_failed
            _LOGGER.warning(
                "No answer on announced port %s, retrying on %s. Please report "
                "this with the discovery details - the announced port is "
                "supposed to be %s on every firmware branch",
                data[CONF_PORT],
                DEFAULT_PORT,
                DEFAULT_PORT,
            )
            repository = Repository(
                async_get_clientsession(hass),
                data[CONF_HOST],
                DEFAULT_PORT,
                data[CONF_OPERATOR_ID],
                data[CONF_DEVICE_ID],
                cert_path=hass.config.path(AC_CERT_FILENAME),
            )
            try:
                airco_id = await repository.get_airco_id()
            except (WfRacError, KeyError, TypeError) as retry_failed:
                raise CannotConnect(reason=str(retry_failed)) from retry_failed
            data[CONF_PORT] = DEFAULT_PORT

        data[CONF_AIRCO_ID] = airco_id
        if not airco_id:
            raise CannotConnect(reason="unknown reason")

        # The airco id is what zeroconf keys on (the module announces itself
        # as <mac>.local), so setting it here lets a discovery recognise a
        # hand-added entry and catches a unit reached at a second address.
        #
        # Before registering, not after: registering takes one of the module's
        # four account slots, and only the manufacturer's app frees one.
        await self.async_set_unique_id(airco_id.lower())
        self._abort_if_unique_id_configured()

        _LOGGER.debug("Registering with airco [%s]", data[CONF_AIRCO_ID])
        try:
            result = await repository.update_account_info(
                airco_id, hass.config.time_zone
            )
        except (WfRacError, KeyError, TypeError) as registration_failed:
            raise CannotConnect(
                reason=str(registration_failed)
            ) from registration_failed
        # By here the account slot is spent, so an unreadable result code
        # belongs in the form as a connection problem, not as a crash.
        code = result_code(result)
        if code is None:
            raise CannotConnect(reason="registration answered without a result code")
        if code == 2:
            raise TooManyDevicesRegistered
        # Every other code the library knows says the registration did not
        # happen, so the form says so rather than storing an entry that cannot
        # poll.
        if code != 0 and code in RESULT_CODES:
            raise CannotConnect(reason=RESULT_CODES[code])
        if code != 0:
            # Not refused: the handler of the firmware we can read maps its
            # return value onto 0/1/2/11/12 and nothing else, so this is a
            # branch we have never seen. Taking it for a failure would leave a
            # unit that answers it unusable, so it is logged and let through -
            # and the log line is the evidence we do not have yet.
            _LOGGER.warning(
                "Airco [%s] answered the registration with result %s, which is "
                "not a code this integration knows. Setup continues. Please "
                "report this together with the module's firmware version",
                data[CONF_AIRCO_ID],
                code,
            )

        return data

    async def _async_fetch_operator_id(self) -> str:
        """Fetch UUID operator id if exists otherwise create it."""
        entry = self._find_entry_matching(CONF_OPERATOR_ID, bool)
        if entry:
            return str(entry.data[CONF_OPERATOR_ID])
        # Once per flow, not per submission: a registration whose answer was
        # lost has still taken one of the four slots.
        if self._generated_operator_id is None:
            self._generated_operator_id = f"hassio-{str(uuid4())[7:]}"
        return self._generated_operator_id

    async def _async_fetch_device_id(self) -> str:
        """Fetch unique device id if exists otherwise create it."""
        entry = self._find_entry_matching(CONF_DEVICE_ID, bool)
        if entry:
            return str(entry.data[CONF_DEVICE_ID])
        if self._generated_device_id is None:
            self._generated_device_id = f"homeassistant-device-{uuid4().hex[21:]}"
        return self._generated_device_id

    async def _async_create_common(
        self,
        step_id: str,
        build_schema: Callable[[], probatio.Schema],
        user_input: dict[str, Any] | None = None,
        description_placeholders: dict[str, str] | None = None,
        allow_port_fallback: bool = False,
    ) -> ConfigFlowResult:
        """Create a new entry.

        The schema is built twice: a submission can leave the values it was
        checked against behind, and a form shown again has to suggest those
        rather than the ones that did not work.
        """
        data_schema = build_schema()
        errors: dict[str, str] = {}
        description_placeholders = description_placeholders or {}

        if user_input:
            description_placeholders["error_name"] = ""
            try:
                user_input[CONF_OPERATOR_ID] = await self._async_fetch_operator_id()
                user_input[CONF_DEVICE_ID] = await self._async_fetch_device_id()

                info = await self._async_register_airco(
                    self.hass, user_input, allow_port_fallback=allow_port_fallback
                )

                data_input = user_input.copy()
                # Form-only: it means nothing to a stored entry.
                data_input.pop(CONF_FORCE_UPDATE, None)

                # Enough to tell two units apart, and it matches the label on
                # the module.
                return self.async_create_entry(
                    title=f"WF-RAC {info[CONF_AIRCO_ID][-4:]}",
                    data=data_input,
                )
            except KnownError as error:
                # Expected outcomes of user input: shown in the form, not
                # logged with a stack trace.
                _LOGGER.debug("Create failed: %s", error)
                errors, placeholders = error.get_errors_and_placeholders(
                    data_schema.schema
                )
                description_placeholders.update(
                    {k: str(v) for k, v in placeholders.items()}
                )
            except AbortFlow:
                # How the helpers end a step - the clause below would turn
                # it into an "unexpected_error" form.
                raise
            except Exception:  # pylint: disable=broad-except
                # The outermost boundary of the step: a bug here shows an
                # "unexpected_error" form instead of crashing the flow.
                _LOGGER.exception("Unexpected exception")
                errors[CONF_BASE] = "unexpected_error"

        return self.async_show_form(
            step_id=step_id,
            data_schema=build_schema(),
            errors=errors,
            description_placeholders=description_placeholders,
        )

    @staticmethod
    def _field(
        user_input: dict[str, Any] | None,
        name: str,
        which: Callable[..., Any],
        default: Any = None,
    ) -> Any:
        """Helper for creating schema fields."""
        value = user_input.get(name, default) if user_input else default
        description = None
        if value is not None:
            description = {"suggested_value": value}
        if default is None:
            return which(name, description=description)
        # A suggestion only pre-fills: a cleared field leaves the key out of
        # user_input altogether, and the schema default keeps it present.
        return which(name, description=description, default=default)

    async def async_step_discovery_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle adding device discovered by zeroconf."""

        description_placeholders = {
            "id": self._discovery_info[CONF_AIRCO_ID],
            "host": self._discovery_info[CONF_HOST],
            "port": self._discovery_info[CONF_PORT],
        }

        if user_input:
            user_input[CONF_HOST] = self._discovery_info[CONF_HOST]
            user_input.setdefault(CONF_PORT, self._discovery_info[CONF_PORT])

        def build_schema() -> probatio.Schema:
            # Both halves of the field follow the port the flow is working
            # with: after a fallback, clearing the field has to land on the
            # port that answered rather than back on the announced one.
            port = (user_input or self._discovery_info)[CONF_PORT]
            field = partial(self._field, user_input)
            return probatio.Schema(
                {
                    field(CONF_PORT, probatio.Optional, port): cv.port,
                }
            )

        return await self._async_create_common(
            step_id="discovery_confirm",
            build_schema=build_schema,
            user_input=user_input,
            description_placeholders=description_placeholders,
            # A port corrected in the form is a decision, not an announcement.
            allow_port_fallback=not user_input
            or user_input[CONF_PORT] == self._discovery_info[CONF_PORT],
        )

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle adding device manually."""

        def build_schema() -> probatio.Schema:
            field = partial(self._field, user_input)
            return probatio.Schema(
                {
                    field(CONF_HOST, probatio.Required): cv.string,
                    field(CONF_PORT, probatio.Optional, DEFAULT_PORT): cv.port,
                    field(CONF_FORCE_UPDATE, probatio.Optional, False): cv.boolean,
                }
            )

        return await self._async_create_common(
            step_id="user", build_schema=build_schema, user_input=user_input
        )

    @override
    async def async_step_zeroconf(
        self, discovery_info: ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Handle zeroconf discovery."""

        # Lower case before anything is cut off it: DNS is case-insensitive,
        # and an announcement shouting .LOCAL. would otherwise keep the suffix
        # and never match the unit that is already configured.
        local_name = discovery_info.hostname.rstrip(".").lower()
        node_name = local_name.removesuffix(".local")
        host = discovery_info.host
        # An announcement without a port is still this module: the port is
        # fixed in the firmware, and a form field with nothing behind it
        # cannot be filled in or cleared.
        port = discovery_info.port or DEFAULT_PORT

        _LOGGER.debug(
            "zeroconf discovery: hostname=%r, host=%r, port=%r",
            discovery_info.hostname,
            discovery_info.host,
            discovery_info.port,
        )

        # One case on both sides: this id comes from the hostname and every
        # other path from the airconId the unit reports.
        await self.async_set_unique_id(node_name)
        # The address only, so a module that moved gets followed: modules have
        # been seen announcing 5353 where the API port belongs.
        self._abort_if_unique_id_configured(updates={CONF_HOST: host})

        info = {CONF_HOST: host, CONF_PORT: port}

        existing_entry = self._find_entry_matching(CONF_HOST, lambda h: h == host)
        if existing_entry:
            _LOGGER.debug("already configured!")
            return self.async_abort(reason="already_configured")

        info[CONF_AIRCO_ID] = node_name
        self._discovery_info = info

        return await self.async_step_discovery_confirm()


class KnownError(Exception):
    """Base class for errors known to this config flow.

    Deliberately not a HomeAssistantError: none of these leaves the flow, so
    error_name is a key under "error" in strings.json rather than a
    translation key, and applies_to_field falls back to CONF_BASE.
    """

    error_name = "unknown_error"
    applies_to_field = CONF_BASE

    def __init__(self, *args: object, **kwargs: str) -> None:
        """Keep the placeholders the message needs alongside the error."""
        super().__init__(*args)
        self._extra_info = kwargs

    def get_errors_and_placeholders(
        self, schema: Any
    ) -> tuple[dict[str, str], dict[str, str]]:
        """Return dicts of errors and description_placeholders, for adding to async_show_form."""
        key = self.applies_to_field
        # Only a key that is in the form reaches the user, so check it.
        if key not in {k.schema for k in schema}:
            key = CONF_BASE
        return ({key: self.error_name}, self._extra_info or {})


class CannotConnect(KnownError):
    """Error to indicate we cannot connect."""

    error_name = "cannot_connect"


class InvalidHost(KnownError):
    """Error to indicate there is an invalid hostname."""

    error_name = "invalid_host"
    applies_to_field = CONF_HOST


class HostAlreadyConfigured(KnownError):
    """Error to indicate there is a duplicate hostname."""

    error_name = "host_already_configured"
    applies_to_field = CONF_HOST


class TooManyDevicesRegistered(KnownError):
    """Error to indicate that there are too many devices registered."""

    error_name = "too_many_devices_registered"
    applies_to_field = CONF_BASE
