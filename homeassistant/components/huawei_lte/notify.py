"""Support for Huawei LTE router notifications."""
from __future__ import annotations

import logging
import time
from typing import Any

from huawei_lte_api.exceptions import ResponseErrorException

from homeassistant.components.notify import ATTR_TARGET, BaseNotificationService
from homeassistant.const import CONF_RECIPIENT
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import Router
from .const import ATTR_CONFIG_ENTRY_ID, DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_get_service(
    hass: HomeAssistant,
    config: ConfigType,
    discovery_info: DiscoveryInfoType | None = None,
) -> HuaweiLteSmsNotificationService | None:
    """Get the notification service."""
    if discovery_info is None:
        return None

    router = hass.data[DOMAIN].routers[discovery_info[ATTR_CONFIG_ENTRY_ID]]
    default_targets = discovery_info[CONF_RECIPIENT] or []

    return HuaweiLteSmsNotificationService(router, default_targets)


class HuaweiLteSmsNotificationService(BaseNotificationService):
    """Huawei LTE router SMS notification service."""

    def __init__(self, router: Router, default_targets: list[str]) -> None:
        """Initialize."""
        self.router = router
        self.default_targets = default_targets

    def send_message(self, message: str = "", **kwargs: Any) -> None:
        """Send message to target numbers."""

        targets = kwargs.get(ATTR_TARGET, self.default_targets)
        if not targets or not message:
            return

        if self.router.suspended:
            _LOGGER.debug(
                "Integration suspended, not sending notification to %s", targets
            )
            return

        try:
            resp = self.router.client.sms.send_sms(
                phone_numbers=targets, message=message
            )
            _LOGGER.debug("Sent to %s: %s", targets, resp)
        except ResponseErrorException as ex:
            _LOGGER.error("Could not send to %s: %s", targets, ex)
        finally:
            self.router.notify_last_attempt = time.monotonic()
