"""Config flow for statistics."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, cast

import voluptuous as vol

from homeassistant.const import (
    CONF_ATTRIBUTE,
    CONF_ENTITY_ID,
    CONF_NAME,
    CONF_UNIT_OF_MEASUREMENT,
)
from homeassistant.helpers.schema_config_entry_flow import (
    SchemaCommonFlowHandler,
    SchemaConfigFlowHandler,
    SchemaFlowError,
    SchemaFlowFormStep,
)
from homeassistant.helpers.selector import (
    AttributeSelector,
    AttributeSelectorConfig,
    BooleanSelector,
    EntitySelector,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    ObjectSelector,
    ObjectSelectorConfig,
    ObjectSelectorField,
    TextSelector,
)

from .const import (
    CONF_DATAPOINTS,
    CONF_DEGREE,
    CONF_LOWER_LIMIT,
    CONF_PRECISION,
    CONF_UPPER_LIMIT,
    DEFAULT_DEGREE,
    DEFAULT_NAME,
    DEFAULT_PRECISION,
    DOMAIN,
)


async def get_options_schema(handler: SchemaCommonFlowHandler) -> vol.Schema:
    """Get options schema."""
    entity_id = handler.options[CONF_ENTITY_ID]

    return vol.Schema(
        {
            vol.Required(CONF_DATAPOINTS): ObjectSelector(
                ObjectSelectorConfig(
                    label_field="uncompensated_value",
                    description_field="compensated_value",
                    multiple=True,
                    translation_key=CONF_DATAPOINTS,
                    fields={
                        "uncompensated_value": ObjectSelectorField(
                            required=True,
                            selector=TextSelector(),
                        ),
                        "compensated_value": ObjectSelectorField(
                            required=True,
                            selector=TextSelector(),
                        ),
                    },
                )
            ),
            vol.Optional(CONF_ATTRIBUTE): AttributeSelector(
                AttributeSelectorConfig(entity_id=entity_id)
            ),
            vol.Optional(CONF_UPPER_LIMIT, default=False): BooleanSelector(),
            vol.Optional(CONF_LOWER_LIMIT, default=False): BooleanSelector(),
            vol.Optional(CONF_PRECISION, default=DEFAULT_PRECISION): NumberSelector(
                NumberSelectorConfig(min=0, step=1, mode=NumberSelectorMode.BOX)
            ),
            vol.Optional(CONF_DEGREE, default=DEFAULT_DEGREE): NumberSelector(
                NumberSelectorConfig(min=0, max=7, step=1, mode=NumberSelectorMode.BOX)
            ),
            vol.Optional(CONF_UNIT_OF_MEASUREMENT): TextSelector(),
        }
    )


async def validate_options(
    handler: SchemaCommonFlowHandler, user_input: dict[str, Any]
) -> dict[str, Any]:
    """Validate options selected."""

    user_input[CONF_PRECISION] = int(user_input[CONF_PRECISION])
    user_input[CONF_DEGREE] = int(user_input[CONF_DEGREE])

    if len(user_input[CONF_DATAPOINTS]) <= user_input[CONF_DEGREE]:
        raise SchemaFlowError("not_enough_datapoints")

    handler.parent_handler._async_abort_entries_match({**handler.options, **user_input})  # noqa: SLF001

    return user_input


DATA_SCHEMA_SETUP = vol.Schema(
    {
        vol.Required(CONF_NAME, default=DEFAULT_NAME): TextSelector(),
        vol.Required(CONF_ENTITY_ID): EntitySelector(),
    }
)

CONFIG_FLOW = {
    "user": SchemaFlowFormStep(
        schema=DATA_SCHEMA_SETUP,
        next_step="options",
    ),
    "options": SchemaFlowFormStep(
        schema=get_options_schema,
        validate_user_input=validate_options,
    ),
}
OPTIONS_FLOW = {
    "init": SchemaFlowFormStep(
        get_options_schema,
        validate_user_input=validate_options,
    ),
}


class CompensationConfigFlowHandler(SchemaConfigFlowHandler, domain=DOMAIN):
    """Handle a config flow for Compensation."""

    config_flow = CONFIG_FLOW
    options_flow = OPTIONS_FLOW

    def async_config_entry_title(self, options: Mapping[str, Any]) -> str:
        """Return config entry title."""
        return cast(str, options[CONF_NAME])
