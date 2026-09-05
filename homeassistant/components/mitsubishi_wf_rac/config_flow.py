"""Config flow WF-RAC."""

from collections.abc import Callable
from functools import partial
import logging
from typing import Any, override
from uuid import uuid4

from pywfrac import Repository, WfRacError
import voluptuous as vol

from homeassistant import config_entries, exceptions
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.const import (
    CONF_BASE,
    CONF_DEVICE_ID,
    CONF_FORCE_UPDATE,
    CONF_HOST,
    CONF_NAME,
    CONF_PORT,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import section
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from . import MitsubishiWfRacConfigEntry
from .const import (
    AC_CERT_FILENAME,
    CONF_AIRCO_ID,
    CONF_AVAILABILITY_RETRY_LIMIT,
    CONF_INDOOR_OFFSET,
    CONF_OPERATOR_ID,
    CONF_OUTDOOR_OFFSET,
    CONF_TARGET_OFFSET,
    CONF_TARGET_OFFSET_COOL,
    CONF_TARGET_OFFSET_HEAT,
    DEFAULT_PORT,
    DOMAIN,
)
from .coordinator import AVAILABILITY_FAILURE_LIMIT_MIN

_LOGGER = logging.getLogger(__name__)

# Form-only keys: sections group the fields in the dialog, they are not
# options themselves and never reach entry.options - see async_step_init.
SECTION_SETPOINT_OFFSETS = "setpoint_offsets"
SECTION_SENSOR_OFFSETS = "sensor_offsets"


class WfRacConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow."""

    VERSION = 5
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL
    _discovery_info: dict[str, Any] = {}
    DOMAIN = DOMAIN

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

    def _find_entry_matching_option(
        self, key: str, matches: Callable[[Any], bool]
    ) -> config_entries.ConfigEntry | None:
        """Returns the first entry where matches(entry.options[key]) returns True."""
        for entry in self._async_current_entries():
            if key in entry.options and matches(entry.options[key]):
                return entry
        return None

    async def _async_register_airco(
        self,
        hass: HomeAssistant,
        data: dict[str, Any],
        exclude_entry_id: str | None = None,
        allow_port_fallback: bool = False,
    ) -> dict[str, Any]:
        """Validate the user input allows us to connect, and register with the airco device.

        allow_port_fallback belongs to discovery only: a port the module
        announced may be wrong (#290), a port a person typed is their decision.
        """
        if len(data[CONF_HOST]) < 3:
            raise InvalidHost

        if len(data[CONF_NAME]) < 3:
            raise InvalidName

        if not data.get(CONF_FORCE_UPDATE):
            # Is this hostname or IP address already configured on a *different*
            # entry? During reconfigure, the entry being edited already owns
            # this host among its own options, so it must not flag itself.
            existing_entry = self._find_entry_matching_option(
                CONF_HOST, lambda h: h == data[CONF_HOST]
            )
            if existing_entry and existing_entry.entry_id != exclude_entry_id:
                raise HostAlreadyConfigured(error_name=existing_entry.data[CONF_NAME])

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
            # does not serve (#290). The port is fixed in the firmware and not
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

        _LOGGER.info(
            "Trying to register OperatorId[%s] on Airco[%s]",
            data[CONF_OPERATOR_ID],
            data[CONF_AIRCO_ID],
        )
        result = await repository.update_account_info(airco_id, hass.config.time_zone)
        if not result:
            raise CannotConnect(reason="no answer to the registration request")
        if int(result["result"]) == 2:
            raise TooManyDevicesRegistered

        return data

    async def _async_fetch_operator_id(self) -> str:
        """Fetch UUID operator id if exists otherwise create it."""
        entry = self._find_entry_matching(CONF_OPERATOR_ID, bool)
        if entry:
            return str(entry.data[CONF_OPERATOR_ID])
        return f"hassio-{str(uuid4())[7:]}"

    async def _async_fetch_device_id(self) -> str:
        """Fetch unique device id if exists otherwise create it."""
        entry = self._find_entry_matching(CONF_DEVICE_ID, bool)
        if entry:
            return str(entry.data[CONF_DEVICE_ID])
        return f"homeassistant-device-{uuid4().hex[21:]}"

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

                data_input = user_input.copy()
                options_input = {
                    CONF_HOST: user_input[CONF_HOST],
                    CONF_AVAILABILITY_RETRY_LIMIT: AVAILABILITY_FAILURE_LIMIT_MIN,
                }
                data_input.pop(CONF_HOST)

                return self.async_create_entry(
                    title=info[CONF_NAME],
                    data=data_input,
                    options=options_input,
                )
            except KnownError as error:
                _LOGGER.exception("create failed")
                errors, placeholders = error.get_errors_and_placeholders(
                    data_schema.schema
                )
                errors.update(errors)
                description_placeholders.update(
                    {k: str(v) for k, v in placeholders.items()}
                )
            except Exception:  # noqa: BLE001  # pylint: disable=broad-except
                # Intentionally broad: this is the outermost boundary of the config
                # flow step, so any bug here should show the user a graceful
                # "unexpected_error" instead of crashing the flow.
                _LOGGER.error("Unexpected exception")
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
        return which(name, description=description)

    async def async_step_discovery_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle adding device discovered by zeroconf."""

        description_placeholders = {
            "id": self._discovery_info[CONF_NAME],
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
                    CONF_NAME, vol.Required, f"Airco {self._discovery_info[CONF_NAME]}"
                ): str,
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
    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: MitsubishiWfRacConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Create the options flow."""
        return WfRacOptionsFlowHandler()

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle adding device manually."""

        field = partial(self._field, user_input)
        data_schema = vol.Schema(
            {
                field(CONF_NAME, vol.Required, "Airco unknown"): cv.string,
                field(CONF_HOST, vol.Required): cv.string,
                field(CONF_PORT, vol.Optional, DEFAULT_PORT): cv.port,
                field(CONF_FORCE_UPDATE, vol.Optional, False): cv.boolean,
            }
        )

        return await self._async_create_common(
            step_id="user", data_schema=data_schema, user_input=user_input
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle changing an existing entry's connection details (host/port/name)."""
        reconfigure_entry = self._get_reconfigure_entry()
        current = {
            CONF_NAME: reconfigure_entry.data[CONF_NAME],
            CONF_HOST: reconfigure_entry.options[CONF_HOST],
            CONF_PORT: reconfigure_entry.data[CONF_PORT],
        }

        field = partial(self._field, user_input or current)
        data_schema = vol.Schema(
            {
                field(CONF_NAME, vol.Required): cv.string,
                field(CONF_HOST, vol.Required): cv.string,
                field(CONF_PORT, vol.Optional, DEFAULT_PORT): cv.port,
            }
        )

        errors: dict[str, str] = {}
        description_placeholders: dict[str, str] = {}

        if user_input:
            try:
                data = dict(user_input)
                data[CONF_OPERATOR_ID] = reconfigure_entry.data[CONF_OPERATOR_ID]
                data[CONF_DEVICE_ID] = reconfigure_entry.data[CONF_DEVICE_ID]

                info = await self._async_register_airco(
                    self.hass, data, exclude_entry_id=reconfigure_entry.entry_id
                )

                new_data = {**reconfigure_entry.data, **data}
                new_options = {
                    **reconfigure_entry.options,
                    CONF_HOST: new_data.pop(CONF_HOST),
                }

                return self.async_update_reload_and_abort(
                    reconfigure_entry,
                    title=info[CONF_NAME],
                    data=new_data,
                    options=new_options,
                )
            except KnownError as error:
                errors, placeholders = error.get_errors_and_placeholders(
                    data_schema.schema
                )
                description_placeholders.update(
                    {k: str(v) for k, v in placeholders.items()}
                )
            except Exception:  # pylint: disable=broad-except
                # Same outermost boundary as _async_create_common: a bug here
                # should surface as "unexpected_error", not crash the flow.
                _LOGGER.exception("Unexpected exception")
                errors[CONF_BASE] = "unexpected_error"

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=data_schema,
            errors=errors,
            description_placeholders=description_placeholders,
        )

    @override
    async def async_step_zeroconf(
        self, discovery_info: ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Handle zeroconf discovery."""

        local_name = discovery_info.hostname.rstrip(".")
        node_name = local_name[: -len(".local")]
        host = discovery_info.host
        port = discovery_info.port

        _LOGGER.debug(
            "zeroconf discovery: hostname=%r, host=%r, port=%r",
            discovery_info.hostname,
            discovery_info.host,
            discovery_info.port,
        )

        info = {CONF_HOST: host, CONF_PORT: port}

        await self.async_set_unique_id(node_name)
        self._abort_if_unique_id_configured(updates=info)

        existing_entry = self._find_entry_matching_option(
            CONF_HOST, lambda h: h == host
        )
        if existing_entry:
            _LOGGER.debug("already configured!")
            return self.async_abort(reason="already_configured")

        info[CONF_NAME] = node_name
        self._discovery_info = info

        return await self.async_step_discovery_confirm()


class WfRacOptionsFlowHandler(config_entries.OptionsFlowWithReload):
    """Base class for options handling.

    OptionsFlowWithReload rather than OptionsFlow: every option here is read
    once while the device is built (see create_device_from_entry), so a change
    only takes effect after a reload. Letting the flow do that itself is what
    replaced the entry update listener - HA deprecated combining a listener
    with the config flow's own reloading methods (async_update_reload_and_abort
    and _abort_if_unique_id_configured), which this flow uses, because the two
    reload the entry twice and race each other.
    """

    def _rendered_option_keys(self) -> set[str]:
        """The option keys this form shows for the current configuration.

        Deliberately derived from the saved options - the same input the
        schema is built from - rather than recorded while building it: the
        save path needs to know what the form could not have collected, and
        answering that from state carried between the two halves is one
        forgotten assignment away from silently dropping settings.
        """
        return {
            CONF_AVAILABILITY_RETRY_LIMIT,
            CONF_TARGET_OFFSET,
            CONF_TARGET_OFFSET_COOL,
            CONF_TARGET_OFFSET_HEAT,
            CONF_INDOOR_OFFSET,
            CONF_OUTDOOR_OFFSET,
        }

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            # Sections hand their fields back nested under the section key,
            # while everything that reads an option reads it flat off
            # entry.options - so the shape is flattened straight back out and
            # the stored options stay exactly what they have always been.
            data: dict[str, Any] = {}
            for key, value in user_input.items():
                if isinstance(value, dict):
                    data.update(value)
                else:
                    data[key] = value
            # A field the form did not show cannot be collected from it, and
            # async_create_entry replaces the options wholesale rather than
            # merging - so an unrendered value has to be carried over by hand
            # or it is dropped. A field that was shown and left empty is
            # meant to be empty and is not carried over.
            for key, value in self.config_entry.options.items():
                if key not in self._rendered_option_keys():
                    data.setdefault(key, value)
            # Host moved to the reconfigure flow (validated against the
            # device) - keep the entry's existing value, since this form no
            # longer collects it.
            data[CONF_HOST] = self.config_entry.options[CONF_HOST]
            return self.async_create_entry(title="", data=data)

        options = self.config_entry.options
        offset_range_validator = vol.All(
            vol.Coerce(float), vol.Range(min=-5.0, max=5.0)
        )
        setpoint_fields: dict[Any, Any] = {
            vol.Optional(
                CONF_TARGET_OFFSET,
                default=options.get(CONF_TARGET_OFFSET, 0.0),
            ): offset_range_validator,
        }
        # target_offset_cool/heat are optional per-mode overrides that must
        # stay "unset" (None) unless the user explicitly fills them in - a
        # default= here would coerce a blank field to 0.0 and defeat the
        # fallback-to-target_offset resolution in climate.py. suggested_value
        # (not default=) pre-fills the displayed value without forcing one
        # when absent.
        setpoint_fields.update(
            {
                vol.Optional(
                    key,
                    description={"suggested_value": options.get(key)},
                ): vol.Any(None, offset_range_validator)
                for key in (CONF_TARGET_OFFSET_COOL, CONF_TARGET_OFFSET_HEAT)
            }
        )

        sensor_fields: dict[Any, Any] = {
            vol.Optional(
                key,
                default=options.get(key, 0.0),
            ): vol.All(vol.Coerce(float), vol.Range(min=-15.0, max=15.0))
            for key in (CONF_INDOOR_OFFSET, CONF_OUTDOOR_OFFSET)
        }

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    # Floor, not a free number: values below the minimum were
                    # the reason this option kept needing correcting in
                    # migrations. Raising it stays available for weak links.
                    vol.Required(
                        CONF_AVAILABILITY_RETRY_LIMIT,
                        default=options.get(
                            CONF_AVAILABILITY_RETRY_LIMIT,
                            AVAILABILITY_FAILURE_LIMIT_MIN,
                        ),
                    ): vol.All(
                        vol.Coerce(int), vol.Range(min=AVAILABILITY_FAILURE_LIMIT_MIN)
                    ),
                    vol.Required(SECTION_SETPOINT_OFFSETS): section(
                        vol.Schema(setpoint_fields), {"collapsed": False}
                    ),
                    vol.Required(SECTION_SENSOR_OFFSETS): section(
                        vol.Schema(sensor_fields), {"collapsed": True}
                    ),
                },
            ),
        )


# pylint: disable=too-few-public-methods


class KnownError(exceptions.HomeAssistantError):
    """Base class for errors known to this config flow.

    [error_name] is the value passed to [errors] in async_show_form, which should match a key
    under "errors" in strings.json

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


class InvalidName(KnownError):
    """Error to indicate there is an invalid hostname."""

    error_name = "name_invalid"
    applies_to_field = CONF_NAME


class TooManyDevicesRegistered(KnownError):
    """Error to indicate that there are too many devices registered."""

    error_name = "too_many_devices_registered"
    applies_to_field = CONF_BASE
