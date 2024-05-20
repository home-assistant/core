"""Issues for OpenWeatherMap."""

from typing import cast

from homeassistant import data_entry_flow
from homeassistant.components.repairs import RepairsFlow
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_MODE
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import issue_registry as ir

from .const import DOMAIN, OWM_MODE_V30


class DeprecatedV25RepairFlow(RepairsFlow):
    """Handler for an issue fixing flow."""

    def __init__(self, entry: ConfigEntry) -> None:
        """Create flow."""
        super().__init__()
        self.entry = entry

    async def async_step_init(
        self, user_input: dict[str, str] | None = None
    ) -> data_entry_flow.FlowResult:
        """Handle the first step of a fix flow."""
        return await self.async_step_migrate()

    async def async_step_migrate(
        self, user_input: dict[str, str] | None = None
    ) -> data_entry_flow.FlowResult:
        """Handle the migrate step of a fix flow."""
        if user_input is None:
            return self.async_show_form(step_id="migrate")

        new_options = {**self.entry.options, CONF_MODE: OWM_MODE_V30}
        self.hass.config_entries.async_update_entry(self.entry, options=new_options)
        await self.hass.config_entries.async_reload(self.entry.entry_id)
        return self.async_create_entry(data={})


async def async_create_fix_flow(
    hass: HomeAssistant,
    issue_id: str,
    data: dict[str, str | int | float | None],
) -> RepairsFlow:
    """Create single repair flow."""
    entry_id = cast(str, data.get("entry_id"))
    entry = hass.config_entries.async_get_entry(entry_id)
    assert entry
    return DeprecatedV25RepairFlow(entry)


def _get_issue_id(entry_id: str) -> str:
    return f"deprecated_v25_{entry_id}"


@callback
def async_create_issue(hass: HomeAssistant, entry_id: str) -> None:
    """Create issue for V2.5 deprecation."""
    ir.async_create_issue(
        hass=hass,
        domain=DOMAIN,
        issue_id=_get_issue_id(entry_id),
        is_fixable=True,
        is_persistent=True,
        severity=ir.IssueSeverity.WARNING,
        learn_more_url="https://www.home-assistant.io/integrations/openweathermap/",
        translation_key="deprecated_v25",
        data={"entry_id": entry_id},
    )


@callback
def async_delete_issue(hass: HomeAssistant, entry_id: str) -> None:
    """Remove issue for V2.5 deprecation."""
    ir.async_delete_issue(hass=hass, domain=DOMAIN, issue_id=_get_issue_id(entry_id))
