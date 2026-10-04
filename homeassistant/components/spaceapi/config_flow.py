"""Config flow for SpaceAPI."""

from typing import Any, override

import probatio

from homeassistant import data_entry_flow
from homeassistant.config_entries import (
    SOURCE_RECONFIGURE,
    ConfigFlow,
    ConfigFlowResult,
)
from homeassistant.const import (
    CONF_ADDRESS,
    CONF_EMAIL,
    CONF_ENTITY_ID,
    CONF_LOCATION,
    CONF_SENSORS,
    CONF_STATE,
    CONF_URL,
)
from homeassistant.helpers.selector import (
    BooleanSelector,
    EntitySelector,
    EntitySelectorConfig,
    ObjectSelector,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from . import (
    CONF_API_VERSION,
    CONF_CACHE,
    CONF_CAM,
    CONF_CONTACT,
    CONF_FEEDS,
    CONF_ICON_CLOSED,
    CONF_ICON_OPEN,
    CONF_ISSUE_REPORT_CHANNELS,
    CONF_LOGO,
    CONF_PROJECTS,
    CONF_RADIO_SHOW,
    CONF_SPACE,
    CONF_SPACEFED,
    CONF_STREAM,
    CONFIG_SCHEMA,
    DOMAIN,
    ISSUE_REPORT_CHANNELS,
    SPACEAPI_VERSION,
    SPACEAPI_VERSION_15,
)

CONF_CONTACT_DETAILS = "contact_details"
CONF_OPTIONAL = "optional"
CONF_SENSOR_HUMIDITY = "sensor_humidity"
CONF_SENSOR_TEMPERATURE = "sensor_temperature"
CONF_STATE_ENTITY_ID = "state_entity_id"
CONF_CUSTOM_SENSORS = "custom_sensors"
CONF_CONFIRM_REMOVAL = "confirm_removal"

_VERSION_OPTIONS = [SPACEAPI_VERSION, SPACEAPI_VERSION_15]
_REMOVED_ROOT_FIELDS = (
    CONF_ISSUE_REPORT_CHANNELS,
    CONF_CACHE,
    CONF_STREAM,
    CONF_RADIO_SHOW,
)

_OPTIONAL_FIELDS = {
    CONF_ADDRESS: TextSelector(),
    CONF_ICON_OPEN: TextSelector(TextSelectorConfig(type=TextSelectorType.URL)),
    CONF_ICON_CLOSED: TextSelector(TextSelectorConfig(type=TextSelectorType.URL)),
    CONF_CONTACT_DETAILS: ObjectSelector(),
    CONF_SENSOR_TEMPERATURE: EntitySelector(
        EntitySelectorConfig(domain="sensor", multiple=True)
    ),
    CONF_SENSOR_HUMIDITY: EntitySelector(
        EntitySelectorConfig(domain="sensor", multiple=True)
    ),
    CONF_SPACEFED: ObjectSelector(),
    CONF_CAM: TextSelector(
        TextSelectorConfig(type=TextSelectorType.URL, multiple=True)
    ),
    CONF_STREAM: ObjectSelector(),
    CONF_FEEDS: ObjectSelector(),
    CONF_CACHE: ObjectSelector(),
    CONF_PROJECTS: TextSelector(
        TextSelectorConfig(type=TextSelectorType.URL, multiple=True)
    ),
    CONF_RADIO_SHOW: ObjectSelector({"multiple": True}),
}

_V15_OPTIONAL_FIELDS = {
    key: value
    for key, value in _OPTIONAL_FIELDS.items()
    if key not in (CONF_STREAM, CONF_CACHE, CONF_RADIO_SHOW)
}


def _version_schema(default: str) -> probatio.Schema:
    """Create the SpaceAPI version selection schema."""
    return probatio.Schema(
        {
            probatio.Required(CONF_API_VERSION, default=default): SelectSelector(
                SelectSelectorConfig(
                    options=_VERSION_OPTIONS, mode=SelectSelectorMode.DROPDOWN
                )
            )
        }
    )


def _form_schema(
    version: str, defaults: dict[str, Any] | None = None
) -> probatio.Schema:
    """Create the version-specific configuration schema."""
    defaults = defaults or {}
    schema: dict[Any, Any] = {
        probatio.Required(
            CONF_SPACE, default=defaults.get(CONF_SPACE, "")
        ): TextSelector(),
        probatio.Required(CONF_URL, default=defaults.get(CONF_URL, "")): TextSelector(
            TextSelectorConfig(type=TextSelectorType.URL)
        ),
        probatio.Required(CONF_LOGO, default=defaults.get(CONF_LOGO, "")): TextSelector(
            TextSelectorConfig(type=TextSelectorType.URL)
        ),
        probatio.Required(
            CONF_STATE_ENTITY_ID,
            default=defaults.get(CONF_STATE_ENTITY_ID, ""),
        ): EntitySelector(EntitySelectorConfig(domain="binary_sensor")),
    }
    email_field = (
        probatio.Required(CONF_EMAIL, default=defaults.get(CONF_EMAIL, ""))
        if version == SPACEAPI_VERSION_15
        else probatio.Optional(CONF_EMAIL, default=defaults[CONF_EMAIL])
        if CONF_EMAIL in defaults
        else probatio.Optional(CONF_EMAIL)
    )
    schema[email_field] = TextSelector(TextSelectorConfig(type=TextSelectorType.EMAIL))

    if version == SPACEAPI_VERSION:
        schema[
            probatio.Required(
                CONF_ISSUE_REPORT_CHANNELS,
                default=defaults.get(CONF_ISSUE_REPORT_CHANNELS, [CONF_EMAIL]),
            )
        ] = SelectSelector(
            SelectSelectorConfig(
                options=ISSUE_REPORT_CHANNELS,
                multiple=True,
                mode=SelectSelectorMode.LIST,
            )
        )

    optional_fields = dict(
        _OPTIONAL_FIELDS if version == SPACEAPI_VERSION else _V15_OPTIONAL_FIELDS
    )
    optional_defaults = defaults.get(CONF_OPTIONAL, {})
    if custom_sensors := optional_defaults.get(CONF_CUSTOM_SENSORS):
        optional_fields[CONF_CUSTOM_SENSORS] = ObjectSelector(
            {
                "fields": {
                    key: {
                        "label": key,
                        "selector": EntitySelector(
                            EntitySelectorConfig(domain="sensor", multiple=True)
                        ),
                    }
                    for key in custom_sensors
                }
            }
        )
    section_schema: dict[Any, Any] = {}
    for key, selector in optional_fields.items():
        if key in optional_defaults:
            field = probatio.Optional(key, default=optional_defaults[key])
        else:
            field = probatio.Optional(key)
        section_schema[field] = selector

    schema[probatio.Required(CONF_OPTIONAL)] = data_entry_flow.section(
        probatio.Schema(section_schema),
        data_entry_flow.SectionConfig(collapsed=True),
    )
    return probatio.Schema(schema)


def _form_defaults(data: dict[str, Any]) -> dict[str, Any]:
    """Convert stored SpaceAPI configuration to form defaults."""
    contact = data.get(CONF_CONTACT, {})
    state = data.get(CONF_STATE, {})
    sensors = data.get(CONF_SENSORS, {})
    optional: dict[str, Any] = {}

    if address := data.get(CONF_LOCATION, {}).get(CONF_ADDRESS):
        optional[CONF_ADDRESS] = address
    for key in (CONF_ICON_OPEN, CONF_ICON_CLOSED):
        if key in state:
            optional[key] = state[key]
    contact_details = {
        key: value for key, value in contact.items() if key != CONF_EMAIL
    }
    if contact_details:
        optional[CONF_CONTACT_DETAILS] = contact_details
    for field, sensor_type in (
        (CONF_SENSOR_TEMPERATURE, "temperature"),
        (CONF_SENSOR_HUMIDITY, "humidity"),
    ):
        if sensor_type in sensors:
            optional[field] = sensors[sensor_type]
    custom_sensors = {
        key: value
        for key, value in sensors.items()
        if key not in ("temperature", "humidity")
    }
    if custom_sensors:
        optional[CONF_CUSTOM_SENSORS] = custom_sensors

    for key in (
        CONF_SPACEFED,
        CONF_CAM,
        CONF_STREAM,
        CONF_FEEDS,
        CONF_CACHE,
        CONF_PROJECTS,
        CONF_RADIO_SHOW,
    ):
        if key in data:
            optional[key] = data[key]

    defaults: dict[str, Any] = {
        CONF_SPACE: data.get(CONF_SPACE, ""),
        CONF_URL: data.get(CONF_URL, ""),
        CONF_LOGO: data.get(CONF_LOGO, ""),
        CONF_EMAIL: contact.get(CONF_EMAIL, ""),
        CONF_STATE_ENTITY_ID: state.get(CONF_ENTITY_ID, ""),
        CONF_ISSUE_REPORT_CHANNELS: data.get(CONF_ISSUE_REPORT_CHANNELS, [CONF_EMAIL]),
        CONF_OPTIONAL: optional,
    }
    return defaults


def _unsupported_v15_items(data: dict[str, Any]) -> list[str]:
    """Return configured paths that are not supported by SpaceAPI v15."""
    unsupported = [key for key in _REMOVED_ROOT_FIELDS if key in data]
    contact = data.get(CONF_CONTACT, {})
    unsupported.extend(
        f"{CONF_CONTACT}.{key}" for key in ("jabber", "google") if key in contact
    )
    spacefed = data.get(CONF_SPACEFED)
    if isinstance(spacefed, dict) and "spacephone" in spacefed:
        unsupported.append(f"{CONF_SPACEFED}.spacephone")
    return unsupported


def _remove_unsupported_v15_items(data: dict[str, Any]) -> dict[str, Any]:
    """Remove fields that were removed from SpaceAPI v14 and v15."""
    data = dict(data)
    for key in _REMOVED_ROOT_FIELDS:
        data.pop(key, None)

    contact = dict(data[CONF_CONTACT])
    contact.pop("jabber", None)
    contact.pop("google", None)
    data[CONF_CONTACT] = contact

    if spacefed := data.get(CONF_SPACEFED):
        spacefed = dict(spacefed)
        spacefed.pop("spacephone", None)
        if spacefed:
            data[CONF_SPACEFED] = spacefed
        else:
            data.pop(CONF_SPACEFED)

    return data


def _build_config(
    version: str, user_input: dict[str, Any], existing: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Build stored SpaceAPI data from form input."""
    existing = existing or {}
    optional = user_input[CONF_OPTIONAL]
    contact = {
        **existing.get(CONF_CONTACT, {}),
        **optional.get(CONF_CONTACT_DETAILS, {}),
    }
    if CONF_EMAIL in user_input:
        contact[CONF_EMAIL] = user_input[CONF_EMAIL]
    state = {
        CONF_ENTITY_ID: user_input[CONF_STATE_ENTITY_ID],
        **{
            key: optional[key]
            for key in (CONF_ICON_OPEN, CONF_ICON_CLOSED)
            if optional.get(key)
        },
    }
    data: dict[str, Any] = {
        CONF_API_VERSION: version,
        CONF_SPACE: user_input[CONF_SPACE],
        CONF_URL: user_input[CONF_URL],
        CONF_LOGO: user_input[CONF_LOGO],
        CONF_CONTACT: contact,
        CONF_STATE: state,
    }
    if version == SPACEAPI_VERSION:
        data[CONF_ISSUE_REPORT_CHANNELS] = user_input[CONF_ISSUE_REPORT_CHANNELS]
    elif CONF_ISSUE_REPORT_CHANNELS in existing:
        data[CONF_ISSUE_REPORT_CHANNELS] = existing[CONF_ISSUE_REPORT_CHANNELS]

    if address := optional.get(CONF_ADDRESS):
        data[CONF_LOCATION] = {CONF_ADDRESS: address}
    elif existing.get(CONF_LOCATION):
        data[CONF_LOCATION] = {
            key: value
            for key, value in existing[CONF_LOCATION].items()
            if key != CONF_ADDRESS
        }

    sensors = {
        **optional.get(CONF_CUSTOM_SENSORS, {}),
        **{
            sensor_type: optional[sensor_field]
            for sensor_type, sensor_field in (
                ("temperature", CONF_SENSOR_TEMPERATURE),
                ("humidity", CONF_SENSOR_HUMIDITY),
            )
            if optional.get(sensor_field)
        },
    }
    if sensors:
        data[CONF_SENSORS] = sensors

    for key in (
        CONF_SPACEFED,
        CONF_CAM,
        CONF_STREAM,
        CONF_FEEDS,
        CONF_CACHE,
        CONF_PROJECTS,
        CONF_RADIO_SHOW,
    ):
        if value := optional.get(key):
            data[key] = value
        elif (
            key in existing
            and version == SPACEAPI_VERSION_15
            and key
            in (
                CONF_STREAM,
                CONF_CACHE,
                CONF_RADIO_SHOW,
            )
        ):
            data[key] = existing[key]

    return data


class SpaceAPIConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a SpaceAPI config flow."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the flow."""
        self._version = SPACEAPI_VERSION
        self._entry_data: dict[str, Any] | None = None
        self._pending_data: dict[str, Any] | None = None
        self._pending_unsupported: list[str] = []

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle initial version selection."""
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()

        if user_input is not None:
            self._version = user_input[CONF_API_VERSION]
            return await self.async_step_configure()

        return self.async_show_form(
            step_id="user", data_schema=_version_schema(SPACEAPI_VERSION)
        )

    async def async_step_configure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Configure required and optional SpaceAPI fields."""
        if user_input is not None:
            existing = self._entry_data or {}
            data = _build_config(self._version, user_input, existing)
            unsupported = (
                _unsupported_v15_items(data)
                if self._version == SPACEAPI_VERSION_15
                else []
            )
            if unsupported:
                self._pending_data = data
                self._pending_unsupported = unsupported
                return await self.async_step_confirm_v15()
            return self._finish(data)

        defaults = _form_defaults(self._entry_data) if self._entry_data else None
        return self.async_show_form(
            step_id="configure",
            data_schema=_form_schema(self._version, defaults),
        )

    async def async_step_confirm_v15(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Require confirmation before removing v15-unsupported values."""
        if user_input is not None:
            if not user_input[CONF_CONFIRM_REMOVAL]:
                return self.async_show_form(
                    step_id="confirm_v15",
                    data_schema=_confirmation_schema(),
                    errors={"base": "confirmation_required"},
                    description_placeholders={
                        "unsupported_items": ", ".join(self._pending_unsupported)
                    },
                )
            assert self._pending_data is not None
            return self._finish(_remove_unsupported_v15_items(self._pending_data))

        return self.async_show_form(
            step_id="confirm_v15",
            data_schema=_confirmation_schema(),
            description_placeholders={
                "unsupported_items": ", ".join(self._pending_unsupported)
            },
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle config entry reconfiguration."""
        entry = self._get_reconfigure_entry()
        self._entry_data = dict(entry.data)
        await self.async_set_unique_id(entry.unique_id)

        if user_input is not None:
            self._version = user_input[CONF_API_VERSION]
            return await self.async_step_configure()

        return self.async_show_form(
            step_id=SOURCE_RECONFIGURE,
            data_schema=_version_schema(
                self._entry_data.get(CONF_API_VERSION, SPACEAPI_VERSION)
            ),
        )

    async def async_step_import(self, import_data: dict[str, Any]) -> ConfigFlowResult:
        """Import existing YAML configuration as SpaceAPI v13."""
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()

        import_data = {**import_data, CONF_API_VERSION: SPACEAPI_VERSION}
        data = CONFIG_SCHEMA({DOMAIN: import_data})[DOMAIN]
        return self.async_create_entry(title="SpaceAPI", data=data)

    def _finish(self, data: dict[str, Any]) -> ConfigFlowResult:
        """Create or update the config entry."""
        try:
            data = CONFIG_SCHEMA({DOMAIN: data})[DOMAIN]
        except probatio.Invalid:
            return self.async_show_form(
                step_id="configure",
                data_schema=_form_schema(self._version, _form_defaults(data)),
                errors={"base": "invalid_config"},
            )
        if (
            self._version == SPACEAPI_VERSION_15
            and (spacefed := data.get(CONF_SPACEFED))
            and not {"spacenet", "spacesaml"} <= spacefed.keys()
        ):
            return self.async_show_form(
                step_id="configure",
                data_schema=_form_schema(self._version, _form_defaults(data)),
                errors={"base": "spacefed_required"},
            )
        if self.source == SOURCE_RECONFIGURE:
            return self.async_update_reload_and_abort(
                self._get_reconfigure_entry(), data=data
            )
        return self.async_create_entry(title="SpaceAPI", data=data)


def _confirmation_schema() -> probatio.Schema:
    """Create the confirmation schema for removed v15 fields."""
    return probatio.Schema(
        {
            probatio.Required(CONF_CONFIRM_REMOVAL, default=False): BooleanSelector(),
        }
    )
