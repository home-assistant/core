"""Config flow for Compensation integration."""

from collections.abc import Mapping
from typing import Any, cast, override

import probatio

from homeassistant.const import (
    CONF_ATTRIBUTE,
    CONF_ENTITY_ID,
    CONF_NAME,
    CONF_UNIT_OF_MEASUREMENT,
)
from homeassistant.data_entry_flow import SectionConfig, section
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
    CONF_COMPENSATED_VALUE,
    CONF_DATAPOINTS,
    CONF_DEGREE,
    CONF_LOWER_LIMIT,
    CONF_POLYNOMIAL_CONFIG,
    CONF_PRECISION,
    CONF_UNCOMPENSATED_VALUE,
    CONF_UPPER_LIMIT,
    DEFAULT_DEGREE,
    DEFAULT_NAME,
    DEFAULT_PRECISION,
    DOMAIN,
)


async def get_options_schema(handler: SchemaCommonFlowHandler) -> probatio.Schema:
    """Get options schema."""
    entity_id = handler.options[CONF_ENTITY_ID]

    return probatio.Schema(
        {
            probatio.Required(CONF_POLYNOMIAL_CONFIG): section(
                probatio.Schema(
                    {
                        probatio.Optional(CONF_DATAPOINTS): ObjectSelector(
                            ObjectSelectorConfig(
                                label_field="uncompensated_value",
                                description_field="compensated_value",
                                multiple=True,
                                translation_key=CONF_DATAPOINTS,
                                overview_labels=True,
                                fields={
                                    CONF_UNCOMPENSATED_VALUE: ObjectSelectorField(
                                        required=True,
                                        selector=NumberSelector(
                                            NumberSelectorConfig(
                                                mode=NumberSelectorMode.BOX
                                            )
                                        ),
                                    ),
                                    CONF_COMPENSATED_VALUE: ObjectSelectorField(
                                        required=True,
                                        selector=NumberSelector(
                                            NumberSelectorConfig(
                                                mode=NumberSelectorMode.BOX
                                            )
                                        ),
                                    ),
                                },
                            )
                        ),
                        probatio.Optional(
                            CONF_DEGREE, default=DEFAULT_DEGREE
                        ): NumberSelector(
                            NumberSelectorConfig(
                                min=1, max=7, step=1, mode=NumberSelectorMode.BOX
                            )
                        ),
                    },
                ),
                SectionConfig(collapsed=False),
            ),
            probatio.Optional(CONF_ATTRIBUTE): AttributeSelector(
                AttributeSelectorConfig(entity_id=entity_id)
            ),
            probatio.Optional(CONF_UPPER_LIMIT, default=False): BooleanSelector(),
            probatio.Optional(CONF_LOWER_LIMIT, default=False): BooleanSelector(),
            probatio.Optional(
                CONF_PRECISION, default=DEFAULT_PRECISION
            ): NumberSelector(
                NumberSelectorConfig(min=0, step=1, mode=NumberSelectorMode.BOX)
            ),
            probatio.Optional(CONF_UNIT_OF_MEASUREMENT): TextSelector(),
        }
    )


async def validate_options(
    handler: SchemaCommonFlowHandler, user_input: dict[str, Any]
) -> dict[str, Any]:
    """Validate options selected."""

    if not user_input[CONF_POLYNOMIAL_CONFIG].get(CONF_DATAPOINTS):
        raise SchemaFlowError("not_enough_datapoints")

    user_input[CONF_PRECISION] = int(user_input[CONF_PRECISION])
    user_input[CONF_POLYNOMIAL_CONFIG][CONF_DEGREE] = int(
        user_input[CONF_POLYNOMIAL_CONFIG][CONF_DEGREE]
    )

    if (
        len(user_input[CONF_POLYNOMIAL_CONFIG][CONF_DATAPOINTS])
        <= user_input[CONF_POLYNOMIAL_CONFIG][CONF_DEGREE]
    ):
        raise SchemaFlowError("not_enough_datapoints")

    handler.parent_handler._async_abort_entries_match({**handler.options, **user_input})  # noqa: SLF001

    return user_input


DATA_SCHEMA_SETUP = probatio.Schema(
    {
        probatio.Required(CONF_NAME, default=DEFAULT_NAME): TextSelector(),
        probatio.Required(CONF_ENTITY_ID): EntitySelector(),
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
    options_flow_reloads = True

    @override
    def async_config_entry_title(self, options: Mapping[str, Any]) -> str:
        """Return config entry title."""
        return cast(str, options[CONF_NAME])
