"""Schema-based configuration and options flows for Visonic panels."""

from collections.abc import Mapping
import re
from typing import TYPE_CHECKING, Any, Final, cast, override
import uuid

import probatio
from yarl import URL

from homeassistant.config_entries import (
    SOURCE_REAUTH,
    SOURCE_RECONFIGURE,
    ConfigFlow,
    ConfigFlowResult,
)
from homeassistant.const import (
    CONF_CODE,
    CONF_DEVICE,
    CONF_EMAIL,
    CONF_EXTERNAL_URL,
    CONF_HOST,
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    CONF_TYPE,
)
from homeassistant.core import callback
from homeassistant.data_entry_flow import AbortFlow
from homeassistant.helpers import config_validation as cv, selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.schema_config_entry_flow import (
    SchemaCommonFlowHandler,
    SchemaConfigFlowHandler,
    SchemaFlowError,
    SchemaFlowFormStep,
    SchemaFlowStep,
    SchemaOptionsFlowHandler,
)
from homeassistant.util.network import is_host_valid

from .connection_test import ConnectionTest
from .const import (
    CONF_ARM_CODE_AUTO,
    CONF_CLOUD_APP_ID,
    CONF_INSTANT_ARM_AWAY,
    CONF_INSTANT_ARM_HOME,
    CONF_PANEL_NUMBER,
    CONF_PANEL_SERIAL,
    CONFIG_EMAIL_INVALID,
    CONFIG_FLOW_ALREADY_CONFIGURED,
    CONFIG_FLOW_ALREADY_IN_PROGRESS,
    CONFIG_INVALID_DEVICE_TYPE,
    CONFIG_PANEL_MISMATCH,
    CONFIG_PANEL_NOT_REGISTERED,
    CONFIG_PANEL_NUMBER_IN_USE,
    CONFIG_SETTINGS_INVALID,
    CONFIG_SETTINGS_MISSING,
    DOMAIN,
    FORM_CLOUD,
    FORM_CONNECTION,
    FORM_DEVICE,
    FORM_DEVICE_NO_PANEL,
    FORM_ETHERNET,
    FORM_PANEL_ARMING,
    FORM_POWERLINK,
    FORM_SELECT_PANEL,
    FORM_SERIAL,
    VISONIC_UNIQUE_NAME,
)
from .exceptions import VisonicException
from .identity import (
    connection_identity,
    normalize_serial_path,
    resolved_connection_identity,
)
from .schemas import (
    ALARM_OPTIONS_SCHEMA,
    CLOUD_ALARM_OPTIONS_SCHEMA,
    CLOUD_PANEL_SCHEMA,
    CLOUD_SCHEMA,
    CONNECTION_OPTIONS_SCHEMA,
    CONNECTION_SCHEMA,
    DEVICE_NO_PANEL_SCHEMA,
    DEVICE_SCHEMA,
    ETHERNET_SCHEMA,
    POWERLINK_SCHEMA,
    SERIAL_SCHEMA,
)
from .visonic_types import DeviceType

VISONIC_CONFIG_VERSION = 1

MAP_DEVICE_TO_CONFIG_STEP = {
    DeviceType.ETHERNET: FORM_ETHERNET,
    DeviceType.SERIAL: FORM_SERIAL,
    DeviceType.CLOUD: FORM_CLOUD,
}
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

ENTRY_ID: Final = "entry_id"


def _normalize_cloud_server(value: str) -> str:
    """Accept a hostname or root HTTPS URL and retain any explicit port."""
    server = value.strip()
    try:
        url = URL(cv.url_no_path(server if "://" in server else f"https://{server}"))
    except (probatio.Invalid, ValueError) as err:
        raise SchemaFlowError(CONFIG_SETTINGS_INVALID) from err
    if (
        url.scheme != "https"
        or url.raw_host is None
        or "." not in url.raw_host
        or not is_host_valid(url.raw_host)
        or "@" in server
        or "?" in server
        or "#" in server
    ):
        raise SchemaFlowError(CONFIG_SETTINGS_INVALID)
    return url.raw_authority


async def _device_suggested_values(handler: SchemaCommonFlowHandler) -> dict[str, Any]:
    """Display the stored connection type using the selector's labels."""
    values = dict(handler.options)
    if CONF_TYPE in values:
        values[CONF_TYPE] = DeviceType(values[CONF_TYPE]).title()
    return values


async def _validate_device(
    handler: SchemaCommonFlowHandler, user_input: dict[str, Any]
) -> dict[str, Any]:
    """Normalize the connection type and reserve the panel naming number."""
    flow = cast(VisonicConfigFlow, handler.parent_handler)
    device_type = DeviceType.from_title(user_input[CONF_TYPE])
    flow.connection_match = None
    flow.panel_number = user_input.get(
        CONF_PANEL_NUMBER, handler.options.get(CONF_PANEL_NUMBER)
    )
    flow.async_check_panel_number()
    if flow.source == SOURCE_RECONFIGURE and device_type != handler.options[CONF_TYPE]:
        # User has changed the device type during reconfigure
        legacy_number = handler.options.get(CONF_PANEL_NUMBER)
        handler.options.clear()
        if legacy_number is not None:
            handler.options[CONF_PANEL_NUMBER] = legacy_number
    return user_input | {CONF_TYPE: device_type}


async def _validate_connection(
    handler: SchemaCommonFlowHandler, user_input: dict[str, Any]
) -> dict[str, Any]:
    """Validate connection settings and check the selected endpoint."""
    flow = cast(VisonicConfigFlow, handler.parent_handler)
    device_type = DeviceType(handler.options[CONF_TYPE])
    # Check to ensure that the needed parameters (keys) are in user_input
    #  Make sure that the values are formatted correctly
    match device_type:
        case DeviceType.ETHERNET:
            if not user_input[CONF_HOST]:
                raise SchemaFlowError(CONFIG_SETTINGS_MISSING)
            identity = connection_identity(user_input | {CONF_TYPE: device_type})
            if TYPE_CHECKING:
                assert identity is not None
            user_input[CONF_HOST] = identity[1]
        case DeviceType.SERIAL:
            if not user_input[CONF_DEVICE]:
                raise SchemaFlowError(CONFIG_SETTINGS_MISSING)
            user_input[CONF_DEVICE] = normalize_serial_path(user_input[CONF_DEVICE])
        case DeviceType.CLOUD:  # pragma: no branch
            if not all(
                user_input[key]
                for key in (CONF_EXTERNAL_URL, CONF_EMAIL, CONF_PASSWORD)
            ):
                raise SchemaFlowError(CONFIG_SETTINGS_MISSING)
            if not _EMAIL_RE.fullmatch(user_input[CONF_EMAIL].strip()):
                raise SchemaFlowError(CONFIG_EMAIL_INVALID)
            user_input[CONF_EXTERNAL_URL] = _normalize_cloud_server(
                user_input[CONF_EXTERNAL_URL]
            )
            user_input[CONF_EMAIL] = user_input[CONF_EMAIL].strip()
            user_input[CONF_CLOUD_APP_ID] = handler.options.get(
                CONF_CLOUD_APP_ID
            ) or str(uuid.uuid4())
            user_input[CONF_PANEL_SERIAL] = (
                user_input.get(CONF_PANEL_SERIAL, "").strip().upper()
            )
            if flow.source == SOURCE_REAUTH:
                user_input[CONF_PANEL_SERIAL] = handler.options.get(
                    CONF_PANEL_SERIAL, ""
                )

    proposed = user_input | {CONF_TYPE: device_type}
    await flow.async_check_connection_match(proposed)
    check_connection = True
    if flow.source == SOURCE_RECONFIGURE and device_type != DeviceType.CLOUD:
        saved = flow._get_reconfigure_entry().data  # noqa: SLF001
        saved_identity = await flow.hass.async_add_executor_job(
            resolved_connection_identity, saved
        )
        # User has changed the connection details as part of reconfigure
        check_connection = saved_identity != flow.connection_match
    flow.connection_tester.session = async_get_clientsession(flow.hass)
    if check_connection and (
        error := await flow.connection_tester.test_connection(device_type, user_input)
    ):
        flow.connection_match = None
        raise SchemaFlowError(error)
    if device_type == DeviceType.CLOUD and not flow.panel_choices:
        raise SchemaFlowError(CONFIG_PANEL_NOT_REGISTERED)
    await flow.async_check_connection_match(user_input | {CONF_TYPE: device_type})
    if device_type == DeviceType.CLOUD and user_input.get(CONF_PANEL_SERIAL):
        await flow.async_set_panel_identity(user_input[CONF_PANEL_SERIAL])
    return user_input


async def _panel_schema(handler: SchemaCommonFlowHandler) -> probatio.Schema:
    """Display serials registered to the authenticated cloud account."""
    flow = cast(VisonicConfigFlow, handler.parent_handler)
    return probatio.Schema(
        {
            probatio.Required(CONF_PANEL_SERIAL): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[
                        selector.SelectOptionDict(value=serial, label=label)
                        for serial, label in flow.panel_choices.items()
                    ],
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            ),
            **CLOUD_PANEL_SCHEMA.schema,
        }
    )


async def _panel_suggested_values(handler: SchemaCommonFlowHandler) -> dict[str, Any]:
    """Prefill panel settings and select the only available panel."""
    flow = cast(VisonicConfigFlow, handler.parent_handler)
    values: dict[str, Any] = {
        key: handler.options[key] for key in (CONF_CODE,) if key in handler.options
    }
    serial = ""
    if flow.source in (SOURCE_RECONFIGURE, SOURCE_REAUTH):
        entry = flow.hass.config_entries.async_get_known_entry(flow.context[ENTRY_ID])
        serial = entry.data.get(CONF_PANEL_SERIAL, "").upper()
    if serial in flow.panel_choices:
        values[CONF_PANEL_SERIAL] = serial
    elif len(flow.panel_choices) == 1:
        values[CONF_PANEL_SERIAL] = next(iter(flow.panel_choices))
    return values


async def _validate_panel(
    handler: SchemaCommonFlowHandler, user_input: dict[str, Any]
) -> dict[str, Any]:
    """Validate access to the selected panel before completing setup."""
    flow = cast(VisonicConfigFlow, handler.parent_handler)
    data = dict(handler.options) | user_input
    if flow.source == SOURCE_RECONFIGURE:
        saved_serial = flow._get_reconfigure_entry().data.get(CONF_PANEL_SERIAL)  # noqa: SLF001
        if saved_serial and (
            data[CONF_PANEL_SERIAL].strip().upper() != saved_serial.strip().upper()
        ):
            raise SchemaFlowError(CONFIG_PANEL_MISMATCH)
    await flow.async_check_connection_match(data)
    if error := await flow.connection_tester.test_connection(DeviceType.CLOUD, data):
        flow.connection_match = None
        raise SchemaFlowError(error)
    await flow.async_check_connection_match(data)
    await flow.async_set_panel_identity(data[CONF_PANEL_SERIAL])
    return user_input


async def _validate_powerlink(
    handler: SchemaCommonFlowHandler, user_input: dict[str, Any]
) -> dict[str, Any]:
    """Recheck duplicates after waiting for Powerlink settings."""
    flow = cast(VisonicConfigFlow, handler.parent_handler)
    await flow.async_check_connection_match(handler.options | user_input)
    return user_input


async def _connection_step(data: dict[str, Any]) -> str:
    """Choose the selected connection form."""
    return MAP_DEVICE_TO_CONFIG_STEP[DeviceType(data[CONF_TYPE])]


# Build the config flow
CONFIG_FLOW: Mapping[str, SchemaFlowStep] = {
    "user": SchemaFlowFormStep(next_step=FORM_DEVICE),
    FORM_DEVICE: SchemaFlowFormStep(
        DEVICE_SCHEMA,
        validate_user_input=_validate_device,
        next_step=_connection_step,
        suggested_values=_device_suggested_values,
    ),
    FORM_DEVICE_NO_PANEL: SchemaFlowFormStep(
        DEVICE_NO_PANEL_SCHEMA,
        validate_user_input=_validate_device,
        next_step=_connection_step,
        suggested_values=_device_suggested_values,
    ),
    FORM_ETHERNET: SchemaFlowFormStep(
        ETHERNET_SCHEMA,
        validate_user_input=_validate_connection,
        next_step=FORM_POWERLINK,
    ),
    FORM_SERIAL: SchemaFlowFormStep(
        SERIAL_SCHEMA,
        validate_user_input=_validate_connection,
        next_step=FORM_POWERLINK,
    ),
    FORM_CLOUD: SchemaFlowFormStep(
        CLOUD_SCHEMA,
        validate_user_input=_validate_connection,
        next_step=FORM_SELECT_PANEL,
    ),
    FORM_SELECT_PANEL: SchemaFlowFormStep(
        _panel_schema,
        validate_user_input=_validate_panel,
        suggested_values=_panel_suggested_values,
    ),
    FORM_POWERLINK: SchemaFlowFormStep(
        POWERLINK_SCHEMA, validate_user_input=_validate_powerlink
    ),
}


async def _connection_options_schema(
    handler: SchemaCommonFlowHandler,
) -> probatio.Schema | None:
    """Skip direct-connection options for cloud panels."""
    flow = cast(SchemaOptionsFlowHandler, handler.parent_handler)
    try:
        device_type = DeviceType(flow.config_entry.data[CONF_TYPE])
    except (KeyError, ValueError) as err:
        raise AbortFlow(CONFIG_INVALID_DEVICE_TYPE) from err
    if device_type == DeviceType.CLOUD:
        return None
    return CONNECTION_OPTIONS_SCHEMA


async def _alarm_options_schema(handler: SchemaCommonFlowHandler) -> probatio.Schema:
    """Offer only the arming settings applicable to each connection type."""
    flow = cast(SchemaOptionsFlowHandler, handler.parent_handler)
    if flow.config_entry.data[CONF_TYPE] == DeviceType.CLOUD:
        return CLOUD_ALARM_OPTIONS_SCHEMA
    return ALARM_OPTIONS_SCHEMA


# Build the options flow
OPTIONS_FLOW: Mapping[str, SchemaFlowStep] = {
    "init": SchemaFlowFormStep(next_step=FORM_CONNECTION),
    FORM_CONNECTION: SchemaFlowFormStep(
        _connection_options_schema, next_step=FORM_PANEL_ARMING
    ),
    FORM_PANEL_ARMING: SchemaFlowFormStep(_alarm_options_schema),
}


class VisonicConfigFlow(SchemaConfigFlowHandler, domain=DOMAIN):
    """Handle Visonic setup and changes to connection settings."""

    VERSION = VISONIC_CONFIG_VERSION
    config_flow = CONFIG_FLOW
    options_flow = OPTIONS_FLOW

    def __init__(self) -> None:
        """Initialize connection testing."""
        super().__init__()
        self.connection_tester = ConnectionTest()
        self.connection_match: tuple[str, ...] | None = None
        self.panel_number: int | None = None

    @property
    def panel_choices(self) -> dict[str, str]:
        """Keep reauthentication on the entry's selected panel."""
        panels = self.connection_tester.panels
        if self.source == SOURCE_REAUTH and (
            serial := self._get_reauth_entry().data.get(CONF_PANEL_SERIAL)
        ):
            return (
                {serial.upper(): panels[serial.upper()]}
                if serial.upper() in panels
                else {}
            )
        return panels

    @callback
    def async_check_panel_number(self) -> None:
        """Reserve a user-selected naming number independently of panel identity."""
        if self.panel_number is None:
            return
        if any(
            entry.entry_id != self.context.get(ENTRY_ID)
            and entry.data.get(CONF_PANEL_NUMBER) == self.panel_number
            for entry in self._async_current_entries()
        ) or self.hass.config_entries.flow.async_has_matching_flow(self):
            self.panel_number = None
            raise SchemaFlowError(CONFIG_PANEL_NUMBER_IN_USE)

    @callback
    @override
    def async_config_entry_title(self, options: Mapping[str, Any]) -> str:
        """Name the panel and its connection type."""
        device_type = DeviceType(options[CONF_TYPE])
        connection = (
            "Visonic Cloud" if device_type == DeviceType.CLOUD else device_type.title()
        )
        return (
            f"{VISONIC_UNIQUE_NAME} - Panel {options[CONF_PANEL_NUMBER]} ({connection})"
        )

    @callback
    @override
    def is_matching(self, other_flow: ConfigFlow) -> bool:
        """Match concurrent flows using their reserved endpoints or cloud serials."""
        return isinstance(other_flow, VisonicConfigFlow) and (
            (
                self.connection_match is not None
                and self.connection_match == other_flow.connection_match
            )
            or (
                self.panel_number is not None
                and self.panel_number == other_flow.panel_number
            )
        )

    async def async_check_connection_match(self, data: Mapping[str, Any]) -> None:
        """Reject configured or reserved connections, excluding the edited entry."""
        self.connection_match = await self.hass.async_add_executor_job(
            resolved_connection_identity, data
        )
        if self.connection_match is None:
            return
        for entry in self._async_current_entries():
            if entry.entry_id == self.context.get(ENTRY_ID):
                continue
            other_identity = await self.hass.async_add_executor_job(
                resolved_connection_identity, entry.data
            )
            if other_identity == self.connection_match:
                raise AbortFlow(CONFIG_FLOW_ALREADY_CONFIGURED)
        if self.hass.config_entries.flow.async_has_matching_flow(self):
            raise AbortFlow(CONFIG_FLOW_ALREADY_IN_PROGRESS)

    async def async_set_panel_identity(self, serial: str) -> None:
        """Assign a cloud hardware identity only to newly created entries."""
        if self.source not in (SOURCE_REAUTH, SOURCE_RECONFIGURE):
            await self.async_set_unique_id(serial)
            self._abort_if_unique_id_configured()

    @callback
    @override
    def async_create_entry(
        self, data: Mapping[str, Any], **kwargs: Any
    ) -> ConfigFlowResult:
        """Keep connection settings in data and behavioral settings in options."""
        if self.panel_number is not None and any(
            entry.entry_id != self.context.get(ENTRY_ID)
            and entry.data.get(CONF_PANEL_NUMBER) == self.panel_number
            for entry in self._async_current_entries()
        ):
            raise AbortFlow(CONFIG_FLOW_ALREADY_CONFIGURED)
        connection_data = dict(data)
        connection_data.pop(CONF_SCAN_INTERVAL, None)
        connection_data = CONNECTION_SCHEMA(connection_data)
        if self.source == SOURCE_REAUTH:
            entry = self._get_reauth_entry()
            if entry.update_listeners:
                unchanged = entry.data == connection_data
                result = self.async_update_and_abort(entry, data=connection_data)
                if unchanged:
                    self.hass.config_entries.async_schedule_reload(entry.entry_id)
                return result
            return self.async_update_reload_and_abort(entry, data=connection_data)
        if self.source == SOURCE_RECONFIGURE:
            entry = self._get_reconfigure_entry()
            options = dict(entry.options)
            if connection_data[CONF_TYPE] == DeviceType.CLOUD:
                for key in (
                    CONF_ARM_CODE_AUTO,
                    CONF_INSTANT_ARM_HOME,
                    CONF_INSTANT_ARM_AWAY,
                ):
                    options.pop(key, None)
            update = (
                self.async_update_and_abort
                if entry.update_listeners
                else self.async_update_reload_and_abort
            )
            return update(
                entry,
                data=connection_data,
                options=options,
                title=self.async_config_entry_title(connection_data),
            )
        if connection_data[CONF_TYPE] == DeviceType.CLOUD:
            options = CLOUD_ALARM_OPTIONS_SCHEMA({})
        else:
            options = ALARM_OPTIONS_SCHEMA({}) | CONNECTION_OPTIONS_SCHEMA({})
        # The schema helper normally stores all collected values in entry.options.
        return ConfigFlow.async_create_entry(
            self,
            title=self.async_config_entry_title(connection_data),
            data=connection_data,
            options=options,
            **kwargs,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Reuse the cloud form while retaining the existing entry identity."""
        entry = self._get_reauth_entry()
        if entry.data[CONF_TYPE] != DeviceType.CLOUD:
            return self.async_abort(reason=CONFIG_INVALID_DEVICE_TYPE)
        self._common_handler.options.update(entry.data)
        return await self._common_handler.async_step(FORM_CLOUD)

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Update connection settings while retaining device and entity identities."""
        self._common_handler.options.update(self._get_reconfigure_entry().data)
        return await self._common_handler.async_step(FORM_DEVICE_NO_PANEL)

    async def async_step_import(
        self, import_config: dict[str, Any]
    ) -> ConfigFlowResult:
        """Reject unsupported YAML imports."""
        raise VisonicException("Import not supported", code=600)
