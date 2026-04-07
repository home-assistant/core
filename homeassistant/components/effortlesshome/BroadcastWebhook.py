from __future__ import annotations
import logging
from .const import DOMAIN
from homeassistant.core import HomeAssistant, callback
from homeassistant.components import webhook
from aiohttp import web

_LOGGER = logging.getLogger(__name__)

class BroadcastWebhook:
    """Class to handle Broadcast Webhook functionality."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize."""
        self.hass = hass

    async def async_setup_webhook(self) -> bool:
        _LOGGER.info("Setting up Broadcast Webhook")

        try:
            webhook.async_register(
                self.hass,
                DOMAIN,
                "Broadcast Webhook",
                "effortlesshome_broadcast",
                self.handle_webhook,
            )
        except Exception as e:
            _LOGGER.info(f"Error setting up Broadcast Webhook: {e}")

        return True

    async def handle_webhook(self, hass: HomeAssistant, webhook_id, request):
        """Handle incoming webhook requests."""
        _LOGGER.info("In broadcast handle webhook")

        if request.method not in ["POST", "PUT"]:
            _LOGGER.warning("Invalid method: %s", request.method)
            return web.Response(status=405, text="Method not allowed")

        try:
            responsejson = await request.json()
            _LOGGER.info("Webhook JSON: %s", responsejson)

            # 1) Send notification using notify.notify
            await hass.services.async_call(
                "notify",
                "notify",
                {
                    "message": responsejson.get("message", str(responsejson)),
                    "title": responsejson.get("title", "Broadcast Message"),
                    "data": responsejson.get("data", {}),
                },
                blocking=False,
            )

            # 2) Fire a custom event in HA for automations
            hass.bus.async_fire(
                f"{DOMAIN}_broadcast_received",
                {"payload": responsejson},
            )
            _LOGGER.debug("Fired event %s_broadcast_received", DOMAIN)

            return web.Response(status=200, text="OK")

        except ValueError as e:
            _LOGGER.error("Webhook JSON error: invalid JSON body - %s", e)
            return web.Response(status=400, text="Invalid JSON")
        except Exception as e:
            _LOGGER.error("Error processing broadcast webhook: %s", e)
            return web.Response(status=500, text="Internal server error")

async def async_remove(self) -> None:
    """Unregister the webhook when the integration is removed."""
    try:
        webhook.async_unregister(self.hass, "effortlesshome_broadcast")
        _LOGGER.info("Broadcast Webhook unregistered")
    except Exception as e:
        _LOGGER.info(f"Error unregistering webhook: {e}")
