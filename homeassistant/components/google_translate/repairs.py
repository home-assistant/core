"""Repair flow for Google Translate Text-to-Speech integration."""
import voluptuous as vol

from homeassistant import data_entry_flow
from homeassistant.components.repairs import RepairsFlow
from homeassistant.components.tts import CONF_LANG
from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.typing import ConfigType

from .const import CONF_TLD, DOMAIN


@callback
def async_process_issue(hass: HomeAssistant, config: ConfigType) -> None:
    """Register an issue and suggest new config."""
    issue_id = f"{config[CONF_LANG]}_{config[CONF_TLD]}"

    ir.async_create_issue(
        hass,
        DOMAIN,
        issue_id,
        breaks_in_ha_version="2024.5.0",
        is_fixable=True,
        severity=ir.IssueSeverity.WARNING,
        translation_key="migration",
        data=config,
    )


class DeprecationRepairFlow(RepairsFlow):
    """Handler for an issue fixing flow."""

    async def async_step_init(
        self, user_input: dict[str, str] | None = None
    ) -> data_entry_flow.FlowResult:
        """Handle the first step of a fix flow."""
        return await self.async_step_confirm()

    async def async_step_confirm(
        self, user_input: dict[str, str] | None = None
    ) -> data_entry_flow.FlowResult:
        """Handle the confirm step of a fix flow."""
        if user_input is not None:
            result = await self.hass.config_entries.flow.async_init(
                DOMAIN, context={"source": SOURCE_IMPORT}, data=self.data
            )
            if result["type"] == FlowResultType.ABORT:
                ir.async_delete_issue(self.hass, DOMAIN, self.issue_id)
                ir.async_create_issue(
                    self.hass,
                    DOMAIN,
                    self.issue_id,
                    breaks_in_ha_version="2024.5.0",
                    is_fixable=False,
                    severity=ir.IssueSeverity.WARNING,
                    translation_key="deprecated_yaml",
                    data=self.data,
                    learn_more_url="https://www.home-assistant.io/integrations/google_translate/",
                )
                return self.async_abort(reason=result["reason"])
            return self.async_create_entry(
                title="",
                data={},
            )

        return self.async_show_form(
            step_id="confirm",
            data_schema=vol.Schema({}),
        )


async def async_create_fix_flow(
    hass: HomeAssistant,
    issue_id: str,
    data: dict[str, str | int | float | None],
) -> RepairsFlow:
    """Create flow."""
    return DeprecationRepairFlow()
