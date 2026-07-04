"""Dataclass storing integration data in hass.data[DOMAIN]."""

from dataclasses import dataclass, field
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
from .coordinator import NotificationCoordinator

_LOGGER = logging.getLogger(__name__)


@dataclass
class NASwebData:
    """Class storing integration data."""

    notify_coordinator: NotificationCoordinator = field(
        default_factory=NotificationCoordinator
    )
    webhook_id = ""

    def is_initialized(self) -> bool:
        """Return True if instance was initialized and is ready for use."""
        return bool(self.webhook_id)

    def can_be_deinitialized(self) -> bool:
        """Return whether this instance can be deinitialized."""
        return not self.notify_coordinator.has_coordinators()

    def initialize(self, hass: HomeAssistant) -> None:
        """Initialize NASwebData instance."""
        if self.is_initialized():
            return
        new_webhook_id = async_generate_id()
        webhook_register(
            hass,
            DOMAIN,
            "NASweb",
            new_webhook_id,
            self.notify_coordinator.handle_webhook_request,
            allowed_methods=[METH_POST],
        )
        self.webhook_id = new_webhook_id
        _LOGGER.debug("Registered webhook: %s", self.webhook_id)

    def deinitialize(self, hass: HomeAssistant) -> None:
        """Deinitialize NASwebData instance."""
        if not self.is_initialized():
            return
        webhook_unregister(hass, self.webhook_id)

    def get_webhook_url(self, hass: HomeAssistant) -> str:
        """Return webhook url for Push API."""
        hass_url = get_url(hass, allow_external=False)
        return WEBHOOK_URL.format(internal_url=hass_url, webhook_id=self.webhook_id)
