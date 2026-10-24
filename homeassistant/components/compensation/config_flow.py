"""Config flow for Compensation integration."""

from collections.abc import Mapping
from typing import Any, cast, override

import numpy as np
import probatio

from homeassistant.components.sensor import CONF_STATE_CLASS
from homeassistant.const import (
    CONF_ATTRIBUTE,
    CONF_DEVICE_CLASS,
    CONF_ENTITY_ID,
    CONF_NAME,
    CONF_UNIT_OF_MEASUREMENT,
    Platform,
)
from homeassistant.data_entry_flow import SectionConfig, section
from homeassistant.helpers import entity_registry as er
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
    DeviceClassSelector,
    DeviceClassSelectorConfig,
    EntitySelector,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    ObjectSelector,
    ObjectSelectorConfig,
    ObjectSelectorField,
    StateClassSelector,
    TextSelector,
    UnitOfMeasurementSelector,
    UnitOfMeasurementSelectorConfig,
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
            probatio.Optional(CONF_DEVICE_CLASS): DeviceClassSelector(
                DeviceClassSelectorConfig(domain=Platform.SENSOR)
            ),
            probatio.Optional(CONF_STATE_CLASS): StateClassSelector(),
            probatio.Optional(CONF_UNIT_OF_MEASUREMENT): UnitOfMeasurementSelector(
                UnitOfMeasurementSelectorConfig(
                    context={
                        "filter_device_class": CONF_DEVICE_CLASS,
                        "filter_state_class": CONF_STATE_CLASS,
                    }
                )
            ),
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

    data_points = user_input[CONF_POLYNOMIAL_CONFIG][CONF_DATAPOINTS]
    degree = user_input[CONF_POLYNOMIAL_CONFIG][CONF_DEGREE]
    if len(data_points) <= degree:
        raise SchemaFlowError("not_enough_datapoints")

    with np.errstate(all="raise"):
        try:
            np.polyfit(
                [data_point[CONF_UNCOMPENSATED_VALUE] for data_point in data_points],
                [data_point[CONF_COMPENSATED_VALUE] for data_point in data_points],
                degree,
            )
        except FloatingPointError as error:
            raise SchemaFlowError("invalid_datapoints") from error

    handler.parent_handler._async_abort_entries_match({**handler.options, **user_input})  # noqa: SLF001

    return user_input


async def validate_setup(
    handler: SchemaCommonFlowHandler, user_input: dict[str, Any]
) -> dict[str, Any]:
    """Validate setup input."""
    # The attribute selector in the options step needs an entity ID, not a UUID
    user_input[CONF_ENTITY_ID] = er.async_validate_entity_id(
        er.async_get(handler.parent_handler.hass), user_input[CONF_ENTITY_ID]
    )
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
        validate_user_input=validate_setup,
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
