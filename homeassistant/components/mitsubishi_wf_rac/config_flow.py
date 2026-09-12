"""Config flow WF-RAC."""

from collections.abc import Callable
from functools import partial
import logging
from typing import Any, override
from uuid import uuid4

from pywfrac import Repository, WfRacError
import voluptuous as vol

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

_LOGGER = logging.getLogger(__name__)


class WfRacConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow."""

    VERSION = 7
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL
    _discovery_info: dict[str, Any] = {}
    DOMAIN = DOMAIN

    def __init__(self) -> None:
        """Start a flow with no identifiers generated yet."""
        self._generated_operator_id: str | None = None
        self._generated_device_id: str | None = None

    @override
    def is_matching(self, other_flow: WfRacConfigFlow) -> bool:
        """Return True if two flows are attempting to configure the same device."""
        # Compare based on unique IDs if available, otherwise compare context data
        if self.unique_id and other_flow.unique_id:
            return self.unique_id == other_flow.unique_id
        # For flows without unique IDs, consider them non-matching
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
            # Is this hostname or IP address already configured?
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
            # A discovery announcement has been seen carrying a port the module
            # does not serve. The port is fixed in the firmware and not
            # user-settable, so rather than failing on a value the device
            # cannot have meant, try the one it always listens on. Only the
            # announced value is second-guessed - a port the user typed is
            # taken at face value.
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

        _LOGGER.debug("Registering with airco [%s]", data[CONF_AIRCO_ID])
        try:
            result = await repository.update_account_info(
                airco_id, hass.config.time_zone
            )
        except (WfRacError, KeyError, TypeError) as registration_failed:
            raise CannotConnect(
                reason=str(registration_failed)
            ) from registration_failed
        if not result:
            raise CannotConnect(reason="no answer to the registration request")
        # The answer comes from the module, so a missing key is a connection
        # problem to report, not an unexpected error to crash the flow on.
        code = result.get("result")
        if code is None:
            raise CannotConnect(reason="registration answered without a result code")
        if int(code) == 2:
            raise TooManyDevicesRegistered

        return data

    async def _async_fetch_operator_id(self) -> str:
        """Fetch UUID operator id if exists otherwise create it."""
        entry = self._find_entry_matching(CONF_OPERATOR_ID, bool)
        if entry:
            return str(entry.data[CONF_OPERATOR_ID])
        # Generated once per flow, not once per submission: the module keeps
        # four account slots, and a registration whose answer was lost has
        # still taken one. Retrying the form with a fresh id would take
        # another, and enough retries would leave no slot to set up with.
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
        data_schema: vol.Schema,
        user_input: dict[str, Any] | None = None,
        description_placeholders: dict[str, str] | None = None,
        allow_port_fallback: bool = False,
    ) -> ConfigFlowResult:
        """Create a new entry."""
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

                # The airco id is the unit's own identity, and the one
                # zeroconf keys on: the module announces itself as
                # <mac>.local and the airco id is that same MAC. Registering
                # it here is what lets a discovery recognise a manually added
                # entry later - and it aborts a unit reached at a second
                # address, which would otherwise become a second entry whose
                # entities collide with the first one's.
                await self.async_set_unique_id(info[CONF_AIRCO_ID].lower())
                self._abort_if_unique_id_configured()

                data_input = user_input.copy()
                # Form-only: it decides whether a duplicate host is accepted
                # while adding, and means nothing to a stored entry.
                data_input.pop(CONF_FORCE_UPDATE, None)

                # Named after the unit rather than asked for: config flows do
                # not collect entry names, and renaming is Home Assistant's
                # own. The last four characters of the airco id are enough to
                # tell two units apart and to match one against the label on
                # the module, while the whole id stays out of the device name
                # and the entity id that people paste into issue reports.
                return self.async_create_entry(
                    title=f"WF-RAC {info[CONF_AIRCO_ID][-4:]}",
                    data=data_input,
                )
            except KnownError as error:
                # Expected outcomes of user input, not faults: the user sees
                # them in the form, and a stack trace in the log would only
                # be noise.
                _LOGGER.debug("Create failed: %s", error)
                errors, placeholders = error.get_errors_and_placeholders(
                    data_schema.schema
                )
                description_placeholders.update(
                    {k: str(v) for k, v in placeholders.items()}
                )
            except AbortFlow:
                # How the helpers end a step. It is the flow working, not a
                # fault, and the broad clause below would turn it into an
                # "unexpected_error" form.
                raise
            except Exception:  # pylint: disable=broad-except
                # Intentionally broad: this is the outermost boundary of the config
                # flow step, so any bug here should show the user a graceful
                # "unexpected_error" instead of crashing the flow.
                _LOGGER.exception("Unexpected exception")
                errors[CONF_BASE] = "unexpected_error"

        # If there is no user input or there were errors, show the form again, including any errors
        # that were found with the input.
        return self.async_show_form(
            step_id=step_id,
            data_schema=data_schema,
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
        # A suggestion only pre-fills the form. Without a schema default the
        # key is simply absent when the field is cleared, and the port is read
        # with [] - so clearing it ended the flow in "unexpected_error".
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

        field = partial(self._field, user_input)
        data_schema = vol.Schema(
            {
                field(
                    CONF_PORT, vol.Optional, self._discovery_info[CONF_PORT]
                ): cv.port,
            }
        )

        return await self._async_create_common(
            step_id="discovery_confirm",
            data_schema=data_schema,
            user_input=user_input,
            description_placeholders=description_placeholders,
            allow_port_fallback=True,
        )

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle adding device manually."""

        field = partial(self._field, user_input)
        data_schema = vol.Schema(
            {
                field(CONF_HOST, vol.Required): cv.string,
                field(CONF_PORT, vol.Optional, DEFAULT_PORT): cv.port,
                field(CONF_FORCE_UPDATE, vol.Optional, False): cv.boolean,
            }
        )

        return await self._async_create_common(
            step_id="user", data_schema=data_schema, user_input=user_input
        )

    @override
    async def async_step_zeroconf(
        self, discovery_info: ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Handle zeroconf discovery."""

        local_name = discovery_info.hostname.rstrip(".")
        node_name = local_name.removesuffix(".local")
        host = discovery_info.host
        port = discovery_info.port

        _LOGGER.debug(
            "zeroconf discovery: hostname=%r, host=%r, port=%r",
            discovery_info.hostname,
            discovery_info.host,
            discovery_info.port,
        )

        # Lower case on both sides: this id comes from the announced hostname
        # while every other path takes it from the airconId the unit reports,
        # and a difference in case would leave discovery unable to recognise
        # an entry it had matched on before.
        await self.async_set_unique_id(node_name.lower())
        # The address only. A module that moved gets followed; its port is
        # what setup was configured with, and modules have been seen
        # announcing 5353 - the mDNS port itself - in the SRV record where the
        # API port belongs, which would take a working entry offline.
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

    Deliberately not a HomeAssistantError: none of these ever leaves the flow.
    Every one is caught here and turned into an entry in the [errors] dict
    that async_show_form renders from strings.json, so they carry an
    error_name rather than a translation key.

    [error_name] is the value passed to [errors] in async_show_form, which should match a key
    under "error" in strings.json

    [applies_to_field] is the name of the field name that contains the error (for
    async_show_form); if the field doesn't exist in the form CONF_BASE will be used instead.
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
        # Errors will only be displayed to the user if the key is actually in the form (or
        # CONF_BASE for a general error), so we'll check the schema (seems weird there
        # isn't a more efficient way to do this...)
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
    """Error to indicate there is an duplicate hostname."""

    error_name = "host_already_configured"
    applies_to_field = CONF_HOST


class TooManyDevicesRegistered(KnownError):
    """Error to indicate that there are too many devices registered."""

    error_name = "too_many_devices_registered"
    applies_to_field = CONF_BASE
