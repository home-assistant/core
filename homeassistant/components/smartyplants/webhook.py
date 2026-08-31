"""Webhook receiver for SmartyPlants push updates."""

from hashlib import sha256
import hmac
import json
import logging
from typing import TYPE_CHECKING

from aiohttp.web import Request, Response
from pysmartyplants import EVENT_SENSOR_UPDATE, SensorUpdate

from homeassistant.components import webhook as hass_webhook
from homeassistant.const import CONF_WEBHOOK_ID
from homeassistant.core import HomeAssistant, callback

from .const import CONF_WEBHOOK_SECRET, DOMAIN, SIGNATURE_HEADER

if TYPE_CHECKING:
    from .coordinator import SmartyPlantsConfigEntry

_LOGGER = logging.getLogger(__name__)


def _signature_matches(secret: str, body: bytes, provided: str | None) -> bool:
    """Verify the HMAC-SHA256 signature the backend sends with each push."""
    if not provided:
        return False

    expected = hmac.new(secret.encode(), body, sha256).hexdigest()
    # Constant-time compare so a wrong signature cannot be guessed by timing.
    return hmac.compare_digest(expected, provided.strip())


async def async_register_webhook(
    hass: HomeAssistant, entry: SmartyPlantsConfigEntry
) -> None:
    """Register the push endpoint for this config entry."""
    webhook_id = entry.data.get(CONF_WEBHOOK_ID)
    if not webhook_id:
        return

    secret = entry.data.get(CONF_WEBHOOK_SECRET)

    async def _handle(
        hass: HomeAssistant, webhook_id: str, request: Request
    ) -> Response:
        """Validate and apply one pushed update."""
        body = await request.read()

        # Without a secret we cannot prove the caller is the SmartyPlants
        # backend, so we refuse rather than trusting an unauthenticated post.
        if not secret:
            _LOGGER.warning("Rejected webhook: no signing secret is configured")
            return Response(status=401)

        if not _signature_matches(secret, body, request.headers.get(SIGNATURE_HEADER)):
            _LOGGER.warning("Rejected webhook: signature did not match")
            return Response(status=401)

        try:
            payload = json.loads(body)
        except ValueError:
            _LOGGER.warning("Rejected webhook: body was not valid JSON")
            return Response(status=400)

        # The body arrives from the internet, so it is parsed and type-checked
        # before anything reads it. Anything unusable is refused outright.
        update = SensorUpdate.from_api(payload)
        if update is None:
            _LOGGER.warning("Rejected webhook: payload was malformed")
            return Response(status=400)

        if update.event == EVENT_SENSOR_UPDATE:
            await entry.runtime_data.async_apply_update(update)
        else:
            # Unknown events are accepted and ignored so that adding new event
            # types on the backend never breaks an older integration.
            _LOGGER.debug("Ignoring unsupported webhook event: %s", update.event)

        return Response(status=200)

    hass_webhook.async_register(hass, DOMAIN, "SmartyPlants", webhook_id, _handle)
    _LOGGER.debug("Registered SmartyPlants webhook %s", webhook_id)


@callback
def async_unregister_webhook(
    hass: HomeAssistant, entry: SmartyPlantsConfigEntry
) -> None:
    """Remove the push endpoint for this config entry."""
    if webhook_id := entry.data.get(CONF_WEBHOOK_ID):
        hass_webhook.async_unregister(hass, webhook_id)
