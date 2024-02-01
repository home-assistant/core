"""Helper functions for NASweb integration."""

import logging

from aiohttp.hdrs import METH_POST

from homeassistant.components.webhook import (
    async_generate_id,
    async_register as webhook_register,
    async_unregister as webhook_unregister,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.network import get_url

from .const import DOMAIN, WEBHOOK_URL
from .nasweb_data import NASwebData

_LOGGER = logging.getLogger(__name__)


def get_integration_webhook_url(hass: HomeAssistant) -> str:
    """Return webhook url for Push API."""
    hass_url = get_url(hass)
    nasweb_data: NASwebData = hass.data[DOMAIN]
    return WEBHOOK_URL.format(internal_url=hass_url, webhook_id=nasweb_data.webhook_id)


def initialize_nasweb_data(hass: HomeAssistant) -> None:
    """Initialize and set up NASwebData instance."""
    nasweb_data: NASwebData = hass.data[DOMAIN]
    new_webhook_id = async_generate_id()
    webhook_register(
        hass,
        DOMAIN,
        "NASweb",
        new_webhook_id,
        nasweb_data.notify_coordinator.handle_webhook_request,
        allowed_methods=[METH_POST],
    )
    nasweb_data.webhook_id = new_webhook_id
    _LOGGER.debug("Registered webhook: %s", nasweb_data.webhook_id)


def deinitialize_nasweb_data_if_empty(hass: HomeAssistant) -> None:
    """Deinitialize NASwebData instance when no longer needed."""
    nasweb_data: NASwebData = hass.data[DOMAIN]
    if not nasweb_data.notify_coordinator.has_coordinators():
        if nasweb_data.is_initialized():
            webhook_unregister(hass, nasweb_data.webhook_id)
        hass.data.pop(DOMAIN)
        _LOGGER.debug("Removed NASwebData from hass.data")
