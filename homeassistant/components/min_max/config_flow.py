"""Config flow for Min/Max integration."""

from typing import Any

import probatio

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers import selector

from .const import DOMAIN

OPTIONS_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_ENTITY_IDS): selector.EntitySelector(
            selector.EntitySelectorConfig(
                domain=[SENSOR_DOMAIN, NUMBER_DOMAIN, INPUT_NUMBER_DOMAIN],
                multiple=True,
            ),
        ),
        probatio.Required(CONF_TYPE): selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=_STATISTIC_MEASURES, translation_key=CONF_TYPE
            ),
        ),
        probatio.Required(CONF_ROUND_DIGITS, default=2): selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=0, max=6, mode=selector.NumberSelectorMode.BOX
            ),
        ),
    }
)

CONFIG_SCHEMA = probatio.Schema(
    {
        probatio.Required("name"): selector.TextSelector(),
    }
).extend(OPTIONS_SCHEMA.schema)


class MinMaxConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for min_max integration."""

    VERSION = 2

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the user step."""
        return self.async_abort(reason="migrated_to_groups")
