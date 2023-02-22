"""Offer webhook triggered automation rules."""
from __future__ import annotations

from dataclasses import dataclass

from aiohttp import hdrs
import voluptuous as vol

from homeassistant.const import CONF_PLATFORM, CONF_WEBHOOK_ID
from homeassistant.core import CALLBACK_TYPE, HassJob, HomeAssistant, callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.trigger import TriggerActionType, TriggerInfo
from homeassistant.helpers.typing import ConfigType

from . import DOMAIN, async_register, async_unregister

DEPENDENCIES = ("webhook",)

TRIGGER_SCHEMA = cv.TRIGGER_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_PLATFORM): "webhook",
        vol.Required(CONF_WEBHOOK_ID): cv.string,
    }
)

WEBHOOK_TRIGGERS = f"{DOMAIN}_triggers"


@dataclass
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
        )
        triggers[webhook_id] = []

    trigger_instance = TriggerInstance(trigger_info, job)
    triggers[webhook_id].append(trigger_instance)

    @callback
    def unregister():
        """Unregister webhook."""
        triggers[webhook_id].remove(trigger_instance)
        if not triggers[webhook_id]:
            async_unregister(hass, webhook_id)
            triggers.pop(webhook_id)

    return unregister
