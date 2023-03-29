"""Repair flow for imap email content integration."""

from typing import Any

import voluptuous as vol
import yaml

from homeassistant import data_entry_flow
from homeassistant.components.imap import DOMAIN as IMAP_DOMAIN
from homeassistant.components.imap.config_flow import STEP_USER_DATA_SCHEMA
from homeassistant.components.repairs import RepairsFlow
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import (
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
    CONF_VALUE_TEMPLATE,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.typing import ConfigType

from .const import CONF_FOLDER, CONF_SENDERS, CONF_SERVER, DOMAIN


@callback
def process_issue(hass: HomeAssistant, config: ConfigType) -> None:
    """Register an issue and suggest new config."""

    name: str = config.get(CONF_NAME) or config[CONF_USERNAME]

    issue_id = (
        f"{name}_{config[CONF_USERNAME]}_{config[CONF_SERVER]}_{config[CONF_FOLDER]}"
    )

    if CONF_VALUE_TEMPLATE in config:
        template: str = config[CONF_VALUE_TEMPLATE].template
        template = template.replace("subject", 'trigger.event.data["subject"]')
        template = template.replace("from", 'trigger.event.data["sender"]')
        template = template.replace("date", 'trigger.event.data["date"]')
        template = template.replace("body", 'trigger.event.data["text"]')
    else:
        template = '{{ trigger.event.data["subject"] }}'
    data = config.copy()
    data[CONF_VALUE_TEMPLATE] = template
    data[CONF_NAME] = name

    template_sensor_config: ConfigType = {
        "template": [
            {
                "trigger": [
                    {
                        "id": "custom_event",
                        "platform": "event",
                        "event_type": "imap_content",
                        "event_data": {"sender": config[CONF_SENDERS][0]},
                    }
                ],
                "sensor": [
                    {
                        "state": template,
                        "name": name,
                    }
                ],
            }
        ]
    }

    hass.data.setdefault(
        DOMAIN,
        {
            "unique_id": issue_id,
            "config": config,
            "yaml_example": yaml.dump(template_sensor_config),
        },
    )

    placeholders = {"yaml_example": yaml.dump(template_sensor_config)}
    placeholders.update(data)

    ir.async_create_issue(
        hass,
        DOMAIN,
        issue_id,
        breaks_in_ha_version="2023.10.0",
        is_fixable=True,
        severity=ir.IssueSeverity.WARNING,
        translation_key="deprecation",
        translation_placeholders=placeholders,
        learn_more_url="https://www.home-assistant.io/integrations/imap/#using-events",
        data=data,
    )


class DeprecationRepairFlow(RepairsFlow):
    """Handler for an issue fixing flow."""

    def __init__(self, issue_id: str, config: ConfigType) -> None:
        """Create flow."""
        self._name: str = config[CONF_NAME]
        self._config: dict[str, Any] = STEP_USER_DATA_SCHEMA(
            {
                CONF_SERVER: config[CONF_SERVER],
                CONF_PORT: config[CONF_PORT],
                CONF_USERNAME: config[CONF_USERNAME],
                CONF_PASSWORD: config[CONF_PASSWORD],
                CONF_FOLDER: config[CONF_FOLDER],
            }
        )
        self._issue_id = issue_id
        super().__init__()

    async def async_step_init(
        self, user_input: dict[str, str] | None = None
    ) -> data_entry_flow.FlowResult:
        """Handle the first step of a fix flow."""
        if self._async_abort_entries_match(self._config):
            return await self.async_step_deprecation()
        return await self.async_step_start()

    @callback
    def _async_get_placeholders(self) -> dict[str, str] | None:
        issue_registry = ir.async_get(self.hass)
        description_placeholders = None
        if issue := issue_registry.async_get_issue(self.handler, self.issue_id):
            description_placeholders = issue.translation_placeholders

        return description_placeholders

    def _async_abort_entries_match(
        self, match_dict: dict[str, Any] | None
    ) -> dict[str, str]:
        """Validate the user input against other config entries."""
        if match_dict is None:
            return {}

        errors: dict[str, str] = {}
        for entry in list(self.hass.config_entries.async_entries(IMAP_DOMAIN)):
            if all(item in entry.data.items() for item in match_dict.items()):
                errors["base"] = "already_configured"
                break
        return errors

    async def async_step_start(
        self, user_input: dict[str, str] | None = None
    ) -> data_entry_flow.FlowResult:
        """Wait for the user to start the config migration."""
        placeholders = self._async_get_placeholders()
        if user_input is None:
            return self.async_show_form(
                step_id="start",
                data_schema=vol.Schema({}),
                description_placeholders=placeholders,
            )

        return self.async_show_form(
            step_id="confirm",
            data_schema=vol.Schema({}),
            description_placeholders=placeholders,
        )

    async def async_step_confirm(
        self, user_input: dict[str, str] | None = None
    ) -> data_entry_flow.FlowResult:
        """Handle the confirm step of a fix flow."""
        if user_input is not None:
            entry = ConfigEntry(
                version=1,
                domain=IMAP_DOMAIN,
                title=self._name,
                data=self._config,
                source=SOURCE_IMPORT,
            )
            await self.hass.config_entries.async_add(entry)
            return self.async_create_entry(
                title="",
                data={},
            )

        return self.async_show_form(
            step_id="confirm",
            data_schema=vol.Schema({}),
            description_placeholders=self._config,
        )

    async def async_step_deprecation(
        self, user_input: dict[str, str] | None = None
    ) -> data_entry_flow.FlowResult:
        """Show deprecation warning."""
        placeholders = self._async_get_placeholders()
        if user_input is None:
            return self.async_show_form(
                step_id="deprecation",
                data_schema=vol.Schema({}),
                description_placeholders=placeholders,
            )

        return self.async_create_entry(
            title="",
            data={},
        )


async def async_create_fix_flow(
    hass: HomeAssistant,
    issue_id: str,
    data: dict[str, str | int | float | None],
) -> RepairsFlow:
    """Create flow."""
    return DeprecationRepairFlow(issue_id, data)
