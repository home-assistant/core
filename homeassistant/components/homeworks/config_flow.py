"""Lutron Homeworks Series 4 and 8 config flow."""

from __future__ import annotations

from functools import partial
import logging
from typing import Any

from pyhomeworks.pyhomeworks import Homeworks
import voluptuous as vol

from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN
from homeassistant.components.light import DOMAIN as LIGHT_DOMAIN
from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT
from homeassistant.core import (
    DOMAIN as HOMEASSISTANT_DOMAIN,
    HomeAssistant,
    async_get_hass,
    callback,
)
from homeassistant.data_entry_flow import AbortFlow
from homeassistant.helpers import (
    config_validation as cv,
    entity_registry as er,
    issue_registry as ir,
    selector,
)
from homeassistant.helpers.schema_config_entry_flow import (
    SchemaCommonFlowHandler,
    SchemaFlowError,
    SchemaFlowFormStep,
    SchemaFlowMenuStep,
    SchemaOptionsFlowHandler,
)
from homeassistant.helpers.selector import TextSelector
from homeassistant.util import slugify

from . import DEFAULT_FADE_RATE, calculate_unique_id
from .const import (
    CONF_ADDR,
    CONF_BUTTONS,
    CONF_CONTROLLER_ID,
    CONF_DIMMERS,
    CONF_INDEX,
    CONF_KEYPADS,
    CONF_LED,
    CONF_NUMBER,
    CONF_RATE,
    CONF_RELEASE_DELAY,
    DEFAULT_BUTTON_NAME,
    DEFAULT_KEYPAD_NAME,
    DEFAULT_LIGHT_NAME,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

CONTROLLER_EDIT = {
    vol.Required(CONF_HOST): selector.TextSelector(),
    vol.Required(CONF_PORT): selector.NumberSelector(
        selector.NumberSelectorConfig(
            min=1,
            max=65535,
            mode=selector.NumberSelectorMode.BOX,
        )
    ),
}

LIGHT_EDIT = {
    vol.Optional(CONF_RATE, default=DEFAULT_FADE_RATE): selector.NumberSelector(
        selector.NumberSelectorConfig(
            min=0,
            max=20,
            mode=selector.NumberSelectorMode.SLIDER,
            step=0.1,
        )
    ),
}

BUTTON_EDIT = {
    vol.Optional(CONF_LED, default=False): selector.BooleanSelector(),
    vol.Optional(CONF_RELEASE_DELAY, default=0): selector.NumberSelector(
        selector.NumberSelectorConfig(
            min=0,
            max=5,
            step=0.01,
            mode=selector.NumberSelectorMode.BOX,
            unit_of_measurement="s",
        ),
    ),
}


validate_addr = cv.matches_regex(r"\[(?:\d\d:)?\d\d:\d\d:\d\d\]")


async def validate_add_controller(
    handler: ConfigFlow | SchemaOptionsFlowHandler, user_input: dict[str, Any]
) -> dict[str, Any]:
    """Validate controller setup."""
    user_input[CONF_CONTROLLER_ID] = slugify(user_input[CONF_NAME])
    user_input[CONF_PORT] = int(user_input[CONF_PORT])
    try:
        handler._async_abort_entries_match(  # pylint: disable=protected-access
            {CONF_HOST: user_input[CONF_HOST], CONF_PORT: user_input[CONF_PORT]}
        )
    except AbortFlow as err:
        raise SchemaFlowError("duplicated_host_port") from err

    try:
        handler._async_abort_entries_match(  # pylint: disable=protected-access
            {CONF_CONTROLLER_ID: user_input[CONF_CONTROLLER_ID]}
        )
    except AbortFlow as err:
        raise SchemaFlowError("duplicated_controller_id") from err

    await _try_connection(user_input)

    return user_input


async def _try_connection(user_input: dict[str, Any]) -> None:
    """Try connecting to the controller."""

    def _try_connect(host: str, port: int) -> None:
        """Try connecting to the controller.

        Raises ConnectionError if the connection fails.
        """
        _LOGGER.debug(
            "Trying to connect to %s:%s", user_input[CONF_HOST], user_input[CONF_PORT]
        )
        controller = Homeworks(host, port, lambda msg_types, values: None)
        controller.close()
        controller.join()

    hass = async_get_hass()
    try:
        await hass.async_add_executor_job(
            _try_connect, user_input[CONF_HOST], user_input[CONF_PORT]
        )
    except ConnectionError as err:
        raise SchemaFlowError("connection_error") from err
    except Exception as err:
        _LOGGER.exception("Caught unexpected exception")
        raise SchemaFlowError("unknown_error") from err


def _create_import_issue(hass: HomeAssistant) -> None:
    """Create a repair issue asking the user to remove YAML."""
    ir.async_create_issue(
        hass,
        HOMEASSISTANT_DOMAIN,
        f"deprecated_yaml_{DOMAIN}",
        breaks_in_ha_version="2024.6.0",
        is_fixable=False,
        issue_domain=DOMAIN,
        severity=ir.IssueSeverity.WARNING,
        translation_key="deprecated_yaml",
        translation_placeholders={
            "domain": DOMAIN,
            "integration_title": "Lutron Homeworks",
        },
    )


def _validate_address(handler: SchemaCommonFlowHandler, addr: str) -> None:
    """Validate address."""
    try:
        validate_addr(addr)
    except vol.Invalid as err:
        raise SchemaFlowError("invalid_addr") from err

    for _key in (CONF_DIMMERS, CONF_KEYPADS):
        items: list[dict[str, Any]] = handler.options[_key]

        for item in items:
            if item[CONF_ADDR] == addr:
                raise SchemaFlowError("duplicated_addr")


def _validate_button_number(handler: SchemaCommonFlowHandler, number: int) -> None:
    """Validate button number."""
    keypad = handler.flow_state["_idx"]
    buttons: list[dict[str, Any]] = handler.options[CONF_KEYPADS][keypad][CONF_BUTTONS]

    for button in buttons:
        if button[CONF_NUMBER] == number:
            raise SchemaFlowError("duplicated_number")


async def validate_add_button(
    handler: SchemaCommonFlowHandler, user_input: dict[str, Any]
) -> dict[str, Any]:
    """Validate button input."""
    user_input[CONF_NUMBER] = int(user_input[CONF_NUMBER])
    _validate_button_number(handler, user_input[CONF_NUMBER])

    # Standard behavior is to merge the result with the options.
    # In this case, we want to add a sub-item so we update the options directly.
    keypad = handler.flow_state["_idx"]
    buttons: list[dict[str, Any]] = handler.options[CONF_KEYPADS][keypad][CONF_BUTTONS]
    buttons.append(user_input)
    return {}


async def validate_add_keypad(
    handler: SchemaCommonFlowHandler, user_input: dict[str, Any]
) -> dict[str, Any]:
    """Validate keypad or light input."""
    _validate_address(handler, user_input[CONF_ADDR])

    # Standard behavior is to merge the result with the options.
    # In this case, we want to add a sub-item so we update the options directly.
    items = handler.options[CONF_KEYPADS]
    items.append(user_input | {CONF_BUTTONS: []})
    return {}


async def validate_add_light(
    handler: SchemaCommonFlowHandler, user_input: dict[str, Any]
) -> dict[str, Any]:
    """Validate light input."""
    _validate_address(handler, user_input[CONF_ADDR])

    # Standard behavior is to merge the result with the options.
    # In this case, we want to add a sub-item so we update the options directly.
    items = handler.options[CONF_DIMMERS]
    items.append(user_input)
    return {}


async def get_select_button_schema(handler: SchemaCommonFlowHandler) -> vol.Schema:
    """Return schema for selecting a button."""
    keypad = handler.flow_state["_idx"]
    buttons: list[dict[str, Any]] = handler.options[CONF_KEYPADS][keypad][CONF_BUTTONS]

    return vol.Schema(
        {
            vol.Required(CONF_INDEX): vol.In(
                {
                    str(index): f"{config[CONF_NAME]} ({config[CONF_NUMBER]})"
                    for index, config in enumerate(buttons)
                },
            )
        }
    )


async def get_select_keypad_schema(handler: SchemaCommonFlowHandler) -> vol.Schema:
    """Return schema for selecting a keypad."""
    return vol.Schema(
        {
            vol.Required(CONF_INDEX): vol.In(
                {
                    str(index): f"{config[CONF_NAME]} ({config[CONF_ADDR]})"
                    for index, config in enumerate(handler.options[CONF_KEYPADS])
                },
            )
        }
    )


async def get_select_light_schema(handler: SchemaCommonFlowHandler) -> vol.Schema:
    """Return schema for selecting a light."""
    return vol.Schema(
        {
            vol.Required(CONF_INDEX): vol.In(
                {
                    str(index): f"{config[CONF_NAME]} ({config[CONF_ADDR]})"
                    for index, config in enumerate(handler.options[CONF_DIMMERS])
                },
            )
        }
    )


async def validate_select_button(
    handler: SchemaCommonFlowHandler, user_input: dict[str, Any]
) -> dict[str, Any]:
    """Store button index in flow state."""
    handler.flow_state["_button_idx"] = int(user_input[CONF_INDEX])
    return {}


async def validate_select_keypad_light(
    handler: SchemaCommonFlowHandler, user_input: dict[str, Any]
) -> dict[str, Any]:
    """Store keypad or light index in flow state."""
    handler.flow_state["_idx"] = int(user_input[CONF_INDEX])
    return {}


async def get_edit_button_suggested_values(
    handler: SchemaCommonFlowHandler,
) -> dict[str, Any]:
    """Return suggested values for button editing."""
    keypad_idx: int = handler.flow_state["_idx"]
    button_idx: int = handler.flow_state["_button_idx"]
    return dict(handler.options[CONF_KEYPADS][keypad_idx][CONF_BUTTONS][button_idx])


async def get_edit_light_suggested_values(
    handler: SchemaCommonFlowHandler,
) -> dict[str, Any]:
    """Return suggested values for light editing."""
    idx: int = handler.flow_state["_idx"]
    return dict(handler.options[CONF_DIMMERS][idx])


async def validate_button_edit(
    handler: SchemaCommonFlowHandler, user_input: dict[str, Any]
) -> dict[str, Any]:
    """Update edited keypad or light."""
    # Standard behavior is to merge the result with the options.
    # In this case, we want to add a sub-item so we update the options directly.
    keypad_idx: int = handler.flow_state["_idx"]
    button_idx: int = handler.flow_state["_button_idx"]
    buttons: list[dict] = handler.options[CONF_KEYPADS][keypad_idx][CONF_BUTTONS]
    buttons[button_idx].update(user_input)
    return {}


async def validate_light_edit(
    handler: SchemaCommonFlowHandler, user_input: dict[str, Any]
) -> dict[str, Any]:
    """Update edited keypad or light."""
    # Standard behavior is to merge the result with the options.
    # In this case, we want to add a sub-item so we update the options directly.
    idx: int = handler.flow_state["_idx"]
    handler.options[CONF_DIMMERS][idx].update(user_input)
    return {}


async def get_remove_button_schema(handler: SchemaCommonFlowHandler) -> vol.Schema:
    """Return schema for button removal."""
    keypad_idx: int = handler.flow_state["_idx"]
    buttons: list[dict] = handler.options[CONF_KEYPADS][keypad_idx][CONF_BUTTONS]
    return vol.Schema(
        {
            vol.Required(CONF_INDEX): cv.multi_select(
                {
                    str(index): f"{config[CONF_NAME]} ({config[CONF_NUMBER]})"
                    for index, config in enumerate(buttons)
                },
            )
        }
    )


async def get_remove_keypad_light_schema(
    handler: SchemaCommonFlowHandler, *, key: str
) -> vol.Schema:
    """Return schema for keypad or light removal."""
    return vol.Schema(
        {
            vol.Required(CONF_INDEX): cv.multi_select(
                {
                    str(index): f"{config[CONF_NAME]} ({config[CONF_ADDR]})"
                    for index, config in enumerate(handler.options[key])
                },
            )
        }
    )


async def validate_remove_button(
    handler: SchemaCommonFlowHandler, user_input: dict[str, Any]
) -> dict[str, Any]:
    """Validate remove keypad or light."""
    removed_indexes: set[str] = set(user_input[CONF_INDEX])

    # Standard behavior is to merge the result with the options.
    # In this case, we want to remove sub-items so we update the options directly.
    entity_registry = er.async_get(handler.parent_handler.hass)
    keypad_idx: int = handler.flow_state["_idx"]
    keypad: dict = handler.options[CONF_KEYPADS][keypad_idx]
    items: list[dict[str, Any]] = []
    item: dict[str, Any]
    for index, item in enumerate(keypad[CONF_BUTTONS]):
        if str(index) not in removed_indexes:
            items.append(item)
        button_number = keypad[CONF_BUTTONS][index][CONF_NUMBER]
        for domain in (BINARY_SENSOR_DOMAIN, BUTTON_DOMAIN):
            if entity_id := entity_registry.async_get_entity_id(
                domain,
                DOMAIN,
                calculate_unique_id(
                    handler.options[CONF_CONTROLLER_ID],
                    keypad[CONF_ADDR],
                    button_number,
                ),
            ):
                entity_registry.async_remove(entity_id)
    keypad[CONF_BUTTONS] = items
    return {}


async def validate_remove_keypad_light(
    handler: SchemaCommonFlowHandler, user_input: dict[str, Any], *, key: str
) -> dict[str, Any]:
    """Validate remove keypad or light."""
    removed_indexes: set[str] = set(user_input[CONF_INDEX])

    # Standard behavior is to merge the result with the options.
    # In this case, we want to remove sub-items so we update the options directly.
    entity_registry = er.async_get(handler.parent_handler.hass)
    items: list[dict[str, Any]] = []
    item: dict[str, Any]
    for index, item in enumerate(handler.options[key]):
        if str(index) not in removed_indexes:
            items.append(item)
        elif key != CONF_DIMMERS:
            continue
        if entity_id := entity_registry.async_get_entity_id(
            LIGHT_DOMAIN,
            DOMAIN,
            calculate_unique_id(
                handler.options[CONF_CONTROLLER_ID], item[CONF_ADDR], 0
            ),
        ):
            entity_registry.async_remove(entity_id)
    handler.options[key] = items
    return {}


DATA_SCHEMA_ADD_CONTROLLER = vol.Schema(
    {
        vol.Required(
            CONF_NAME, description={"suggested_value": "Lutron Homeworks"}
        ): selector.TextSelector(),
        **CONTROLLER_EDIT,
    }
)
DATA_SCHEMA_EDIT_CONTROLLER = vol.Schema(CONTROLLER_EDIT)
DATA_SCHEMA_ADD_LIGHT = vol.Schema(
    {
        vol.Optional(CONF_NAME, default=DEFAULT_LIGHT_NAME): TextSelector(),
        vol.Required(CONF_ADDR): TextSelector(),
        **LIGHT_EDIT,
    }
)
DATA_SCHEMA_ADD_KEYPAD = vol.Schema(
    {
        vol.Optional(CONF_NAME, default=DEFAULT_KEYPAD_NAME): TextSelector(),
        vol.Required(CONF_ADDR): TextSelector(),
    }
)
DATA_SCHEMA_ADD_BUTTON = vol.Schema(
    {
        vol.Optional(CONF_NAME, default=DEFAULT_BUTTON_NAME): TextSelector(),
        vol.Required(CONF_NUMBER): selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=1,
                max=24,
                step=1,
                mode=selector.NumberSelectorMode.BOX,
            ),
        ),
        **BUTTON_EDIT,
    }
)
DATA_SCHEMA_EDIT_BUTTON = vol.Schema(BUTTON_EDIT)
DATA_SCHEMA_EDIT_LIGHT = vol.Schema(LIGHT_EDIT)

OPTIONS_FLOW = {
    "init": SchemaFlowMenuStep(
        [
            "add_keypad",
            "select_edit_keypad",
            "remove_keypad",
            "add_light",
            "select_edit_light",
            "remove_light",
        ]
    ),
    "add_keypad": SchemaFlowFormStep(
        DATA_SCHEMA_ADD_KEYPAD,
        suggested_values=None,
        validate_user_input=validate_add_keypad,
    ),
    "select_edit_keypad": SchemaFlowFormStep(
        get_select_keypad_schema,
        suggested_values=None,
        validate_user_input=validate_select_keypad_light,
        next_step="edit_keypad",
    ),
    "edit_keypad": SchemaFlowMenuStep(
        [
            "add_button",
            "select_edit_button",
            "remove_button",
        ]
    ),
    "add_button": SchemaFlowFormStep(
        DATA_SCHEMA_ADD_BUTTON,
        suggested_values=None,
        validate_user_input=validate_add_button,
    ),
    "select_edit_button": SchemaFlowFormStep(
        get_select_button_schema,
        suggested_values=None,
        validate_user_input=validate_select_button,
        next_step="edit_button",
    ),
    "edit_button": SchemaFlowFormStep(
        DATA_SCHEMA_EDIT_BUTTON,
        suggested_values=get_edit_button_suggested_values,
        validate_user_input=validate_button_edit,
    ),
    "remove_button": SchemaFlowFormStep(
        get_remove_button_schema,
        suggested_values=None,
        validate_user_input=validate_remove_button,
    ),
    "remove_keypad": SchemaFlowFormStep(
        partial(get_remove_keypad_light_schema, key=CONF_KEYPADS),
        suggested_values=None,
        validate_user_input=partial(validate_remove_keypad_light, key=CONF_KEYPADS),
    ),
    "add_light": SchemaFlowFormStep(
        DATA_SCHEMA_ADD_LIGHT,
        suggested_values=None,
        validate_user_input=validate_add_light,
    ),
    "select_edit_light": SchemaFlowFormStep(
        get_select_light_schema,
        suggested_values=None,
        validate_user_input=validate_select_keypad_light,
        next_step="edit_light",
    ),
    "edit_light": SchemaFlowFormStep(
        DATA_SCHEMA_EDIT_LIGHT,
        suggested_values=get_edit_light_suggested_values,
        validate_user_input=validate_light_edit,
    ),
    "remove_light": SchemaFlowFormStep(
        partial(get_remove_keypad_light_schema, key=CONF_DIMMERS),
        suggested_values=None,
        validate_user_input=partial(validate_remove_keypad_light, key=CONF_DIMMERS),
    ),
}


class HomeworksConfigFlowHandler(ConfigFlow, domain=DOMAIN):
    """Config flow for Lutron Homeworks."""

    import_config: dict[str, Any]

    async def async_step_import(self, config: dict[str, Any]) -> ConfigFlowResult:
        """Start importing configuration from yaml."""
        self.import_config = {
            CONF_HOST: config[CONF_HOST],
            CONF_PORT: config[CONF_PORT],
            CONF_DIMMERS: [
                {
                    CONF_ADDR: light[CONF_ADDR],
                    CONF_NAME: light[CONF_NAME],
                    CONF_RATE: light[CONF_RATE],
                }
                for light in config[CONF_DIMMERS]
            ],
            CONF_KEYPADS: [
                {
                    CONF_ADDR: keypad[CONF_ADDR],
                    CONF_BUTTONS: [],
                    CONF_NAME: keypad[CONF_NAME],
                }
                for keypad in config[CONF_KEYPADS]
            ],
        }
        return await self.async_step_import_controller_name()

    async def async_step_import_controller_name(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask user to set a name of the controller."""
        errors = {}
        try:
            self._async_abort_entries_match(
                {
                    CONF_HOST: self.import_config[CONF_HOST],
                    CONF_PORT: self.import_config[CONF_PORT],
                }
            )
        except AbortFlow:
            _create_import_issue(self.hass)
            raise

        if user_input:
            try:
                user_input[CONF_CONTROLLER_ID] = slugify(user_input[CONF_NAME])
                self._async_abort_entries_match(
                    {CONF_CONTROLLER_ID: user_input[CONF_CONTROLLER_ID]}
                )
            except AbortFlow:
                errors["base"] = "duplicated_controller_id"
            else:
                self.import_config |= user_input
                return await self.async_step_import_finish()

        return self.async_show_form(
            step_id="import_controller_name",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_NAME, description={"suggested_value": "Lutron Homeworks"}
                    ): selector.TextSelector(),
                }
            ),
            errors=errors,
        )

    async def async_step_import_finish(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask user to remove YAML configuration."""

        if user_input is not None:
            entity_registry = er.async_get(self.hass)
            config = self.import_config
            for light in config[CONF_DIMMERS]:
                addr = light[CONF_ADDR]
                if entity_id := entity_registry.async_get_entity_id(
                    LIGHT_DOMAIN, DOMAIN, f"homeworks.{addr}"
                ):
                    entity_registry.async_update_entity(
                        entity_id,
                        new_unique_id=calculate_unique_id(
                            config[CONF_CONTROLLER_ID], addr, 0
                        ),
                    )
            name = config.pop(CONF_NAME)
            return self.async_create_entry(
                title=name,
                data={},
                options=config,
            )

        return self.async_show_form(step_id="import_finish", data_schema=vol.Schema({}))

    async def _validate_edit_controller(
        self, user_input: dict[str, Any]
    ) -> dict[str, Any]:
        """Validate controller setup."""
        user_input[CONF_PORT] = int(user_input[CONF_PORT])

        our_entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
        assert our_entry
        other_entries = self._async_current_entries()
        for entry in other_entries:
            if entry.entry_id == our_entry.entry_id:
                continue
            if (
                user_input[CONF_HOST] == entry.options[CONF_HOST]
                and user_input[CONF_PORT] == entry.options[CONF_PORT]
            ):
                raise SchemaFlowError("duplicated_host_port")

        await _try_connection(user_input)
        return user_input

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a reconfigure flow."""
        entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
        assert entry

        errors = {}
        suggested_values = {
            CONF_HOST: entry.options[CONF_HOST],
            CONF_PORT: entry.options[CONF_PORT],
        }

        if user_input:
            suggested_values = {
                CONF_HOST: user_input[CONF_HOST],
                CONF_PORT: user_input[CONF_PORT],
            }
            try:
                await self._validate_edit_controller(user_input)
            except SchemaFlowError as err:
                errors["base"] = str(err)
            else:
                new_options = entry.options | {
                    CONF_HOST: user_input[CONF_HOST],
                    CONF_PORT: user_input[CONF_PORT],
                }
                return self.async_update_reload_and_abort(
                    entry,
                    options=new_options,
                    reason="reconfigure_successful",
                    reload_even_if_entry_is_unchanged=False,
                )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                DATA_SCHEMA_EDIT_CONTROLLER, suggested_values
            ),
            errors=errors,
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""
        errors = {}
        if user_input:
            try:
                await validate_add_controller(self, user_input)
            except SchemaFlowError as err:
                errors["base"] = str(err)
            else:
                self._async_abort_entries_match(
                    {CONF_HOST: user_input[CONF_HOST], CONF_PORT: user_input[CONF_PORT]}
                )
                name = user_input.pop(CONF_NAME)
                user_input |= {CONF_DIMMERS: [], CONF_KEYPADS: []}
                return self.async_create_entry(title=name, data={}, options=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=DATA_SCHEMA_ADD_CONTROLLER,
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> SchemaOptionsFlowHandler:
        """Options flow handler for Lutron Homeworks."""
        return SchemaOptionsFlowHandler(config_entry, OPTIONS_FLOW)
