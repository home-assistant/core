"""Offer webhook triggered automation rules."""
from __future__ import annotations

from dataclasses import dataclass
import logging

from aiohttp import hdrs
import voluptuous as vol

from homeassistant.const import CONF_PLATFORM, CONF_WEBHOOK_ID
from homeassistant.core import CALLBACK_TYPE, HassJob, HomeAssistant, callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.issue_registry import (
    IssueSeverity,
    async_create_issue,
    async_delete_issue,
)
from homeassistant.helpers.trigger import TriggerActionType, TriggerInfo
from homeassistant.helpers.typing import ConfigType

from . import (
    DEFAULT_METHODS,
    DOMAIN,
    SUPPORTED_METHODS,
    async_register,
    async_unregister,
)

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ("webhook",)

CONF_ALLOWED_METHODS = "allowed_methods"
CONF_LOCAL_ONLY = "local_only"

TRIGGER_SCHEMA = cv.TRIGGER_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_PLATFORM): "webhook",
        vol.Required(CONF_WEBHOOK_ID): cv.string,
        vol.Optional(CONF_ALLOWED_METHODS): vol.All(
            cv.ensure_list,
            [vol.All(vol.Upper, vol.In(SUPPORTED_METHODS))],
            vol.Unique(),
        ),
        vol.Optional(CONF_LOCAL_ONLY): bool,
    }
)

WEBHOOK_TRIGGERS = f"{DOMAIN}_triggers"


@dataclass(slots=True)
class TriggerInstance:
    """Attached trigger settings."""

    trigger_info: TriggerInfo
    job: HassJob


async def _handle_webhook(hass, webhook_id, request):
    """Handle incoming webhook."""
    base_result = {"platform": "webhook", "webhook_id": webhook_id}

    if "json" in request.headers.get(hdrs.CONTENT_TYPE, ""):
        base_result["json"] = await request.json()
    else:
        base_result["data"] = await request.post()

    base_result["query"] = request.query
    base_result["description"] = "webhook"

    triggers: dict[str, list[TriggerInstance]] = hass.data.setdefault(
        WEBHOOK_TRIGGERS, {}
    )
    for trigger in triggers[webhook_id]:
        result = {**base_result, **trigger.trigger_info["trigger_data"]}
        hass.async_run_hass_job(trigger.job, {"trigger": result})


async def async_attach_trigger(
    hass: HomeAssistant,
    config: ConfigType,
    action: TriggerActionType,
    trigger_info: TriggerInfo,
) -> CALLBACK_TYPE:
    """Trigger based on incoming webhooks."""
    webhook_id: str = config[CONF_WEBHOOK_ID]
    local_only = config.get(CONF_LOCAL_ONLY)
    issue_id: str | None = None
    if local_only is None:
        issue_id = f"trigger_missing_local_only_{webhook_id}"
        variables = trigger_info["variables"] or {}
        automation_info = variables.get("this", {})
        automation_id = automation_info.get("attributes", {}).get("id")
        automation_entity_id = automation_info.get("entity_id")
        automation_name = trigger_info.get("name") or automation_entity_id
        async_create_issue(
            hass,
            DOMAIN,
            issue_id,
            breaks_in_ha_version="2023.11.0",
            is_fixable=False,
            severity=IssueSeverity.WARNING,
            learn_more_url="https://www.home-assistant.io/docs/automation/trigger/#webhook-trigger",
            translation_key="trigger_missing_local_only",
            translation_placeholders={
                "webhook_id": webhook_id,
                "automation_name": automation_name,
                "entity_id": automation_entity_id,
                "edit": f"/config/automation/edit/{automation_id}",
            },
        )
    allowed_methods = config.get(CONF_ALLOWED_METHODS, DEFAULT_METHODS)
    job = HassJob(action)

    triggers: dict[str, list[TriggerInstance]] = hass.data.setdefault(
        WEBHOOK_TRIGGERS, {}
    )

    if webhook_id not in triggers:
        async_register(
            hass,
            trigger_info["domain"],
            trigger_info["name"],
            webhook_id,
            _handle_webhook,
            local_only=local_only,
            allowed_methods=allowed_methods,
        )
        triggers[webhook_id] = []

    trigger_instance = TriggerInstance(trigger_info, job)
    triggers[webhook_id].append(trigger_instance)

    @callback
    def unregister():
        """Unregister webhook."""
        if issue_id:
            async_delete_issue(hass, DOMAIN, issue_id)
        triggers[webhook_id].remove(trigger_instance)
        if not triggers[webhook_id]:
            async_unregister(hass, webhook_id)
            triggers.pop(webhook_id)

    return unregister
