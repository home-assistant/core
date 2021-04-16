"""Offer webhook triggered automation rules."""
from functools import partial

from aiohttp import hdrs
import voluptuous as vol

from homeassistant.const import CONF_PLATFORM, CONF_WEBHOOK_ID
from homeassistant.core import HassJob, callback
import homeassistant.helpers.config_validation as cv

# mypy: allow-untyped-defs

DEPENDENCIES = ("webhook",)

TRIGGER_SCHEMA = vol.Schema(
    {vol.Required(CONF_PLATFORM): "webhook", vol.Required(CONF_WEBHOOK_ID): cv.string}
)


async def _handle_webhook(job, trigger_id, hass, webhook_id, request):
    """Handle incoming webhook."""
    result = {"platform": "webhook", "webhook_id": webhook_id}

    if "json" in request.headers.get(hdrs.CONTENT_TYPE, ""):
        result["json"] = await request.json()
    else:
        result["data"] = await request.post()

    result["query"] = request.query
    result["description"] = "webhook"
    result["id"] = trigger_id
    hass.async_run_hass_job(job, {"trigger": result})


async def async_attach_trigger(hass, config, action, automation_info):
    """Trigger based on incoming webhooks."""
    trigger_id = automation_info.get("trigger_id") if automation_info else None
    webhook_id = config.get(CONF_WEBHOOK_ID)
    job = HassJob(action)
    hass.components.webhook.async_register(
        automation_info["domain"],
        automation_info["name"],
        webhook_id,
        partial(_handle_webhook, job, trigger_id),
    )

    @callback
    def unregister():
        """Unregister webhook."""
        hass.components.webhook.async_unregister(webhook_id)

    return unregister
