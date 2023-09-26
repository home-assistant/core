"""Repair flow for imap email content integration."""

from typing import Any

import voluptuous as vol
import yaml

from homeassistant import data_entry_flow
from homeassistant.components.imap import DOMAIN as IMAP_DOMAIN
from homeassistant.components.repairs import RepairsFlow
from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import (
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
    CONF_VALUE_TEMPLATE,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.typing import ConfigType

from .const import CONF_FOLDER, CONF_SENDERS, CONF_SERVER, DOMAIN


async def async_process_issue(hass: HomeAssistant, config: ConfigType) -> None:
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

    data = {
        CONF_SERVER: config[CONF_SERVER],
        CONF_PORT: config[CONF_PORT],
        CONF_USERNAME: config[CONF_USERNAME],
        CONF_PASSWORD: config[CONF_PASSWORD],
        CONF_FOLDER: config[CONF_FOLDER],
    }
    data[CONF_VALUE_TEMPLATE] = template
    data[CONF_NAME] = name
    placeholders = {"yaml_example": yaml.dump(template_sensor_config)}
    placeholders.update(data)

    ir.async_create_issue(
        hass,
        DOMAIN,
        issue_id,
        breaks_in_ha_version="2023.11.0",
        is_fixable=True,
        severity=ir.IssueSeverity.WARNING,
        translation_key="migration",
        translation_placeholders=placeholders,
        data=data,
    )


class DeprecationRepairFlow(RepairsFlow):
    """Handler for an issue fixing flow."""

    def __init__(self, issue_id: str, config: ConfigType) -> None:
        """Create flow."""
        self._name: str = config[CONF_NAME]
        self._config: dict[str, Any] = config
        self._issue_id = issue_id
        super().__init__()

    async def async_step_init(
        self, user_input: dict[str, str] | None = None
    ) -> data_entry_flow.FlowResult:
        """Handle the first step of a fix flow."""
        return await self.async_step_start()

    @callback
    def _async_get_placeholders(self) -> dict[str, str] | None:
        issue_registry = ir.async_get(self.hass)
        description_placeholders = None
        if issue := issue_registry.async_get_issue(self.handler, self.issue_id):
            description_placeholders = issue.translation_placeholders

        return description_placeholders

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

        return await self.async_step_confirm()

    async def async_step_confirm(
        self, user_input: dict[str, str] | None = None
    ) -> data_entry_flow.FlowResult:
        """Handle the confirm step of a fix flow."""
        placeholders = self._async_get_placeholders()
        if user_input is not None:
            user_input[CONF_NAME] = self._name
            result = await self.hass.config_entries.flow.async_init(
                IMAP_DOMAIN, context={"source": SOURCE_IMPORT}, data=self._config
            )
            if result["type"] == FlowResultType.ABORT:
                ir.async_delete_issue(self.hass, DOMAIN, self._issue_id)
                ir.async_create_issue(
                    self.hass,
                    DOMAIN,
                    self._issue_id,
                    breaks_in_ha_version="2023.11.0",
                    is_fixable=False,
                    severity=ir.IssueSeverity.WARNING,
                    translation_key="deprecation",
                    translation_placeholders=placeholders,
                    data=self._config,
                    learn_more_url="https://www.home-assistant.io/integrations/imap/#using-events",
                )
                return self.async_abort(reason=result["reason"])
            return self.async_create_entry(
                title="",
                data={},
            )

        return self.async_show_form(
            step_id="confirm",
            data_schema=vol.Schema({}),
            description_placeholders=placeholders,
        )


async def async_create_fix_flow(
    hass: HomeAssistant,
    issue_id: str,
    data: dict[str, str | int | float | None],
) -> RepairsFlow:
    """Create flow."""
    return DeprecationRepairFlow(issue_id, data)
