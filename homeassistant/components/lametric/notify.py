"""Support for LaMetric notifications."""
from __future__ import annotations

from typing import Any

from lmnotify import Model, SimpleFrame, Sound
from oauthlib.oauth2 import TokenExpiredError
from requests.exceptions import ConnectionError as RequestsConnectionError
import voluptuous as vol

from homeassistant.components.notify import (
    ATTR_DATA,
    ATTR_TARGET,
    PLATFORM_SCHEMA,
    BaseNotificationService,
)
from homeassistant.const import CONF_ICON
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import HassLaMetricManager
from .const import (
    AVAILABLE_ICON_TYPES,
    AVAILABLE_PRIORITIES,
    CONF_CYCLES,
    CONF_ICON_TYPE,
    CONF_LIFETIME,
    CONF_PRIORITY,
    DOMAIN,
    LOGGER,
)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_ICON, default="a7956"): cv.string,
        vol.Optional(CONF_LIFETIME, default=10): cv.positive_int,
        vol.Optional(CONF_CYCLES, default=1): cv.positive_int,
        vol.Optional(CONF_PRIORITY, default="warning"): vol.In(AVAILABLE_PRIORITIES),
        vol.Optional(CONF_ICON_TYPE, default="info"): vol.In(AVAILABLE_ICON_TYPES),
    }
)


def get_service(
    hass: HomeAssistant,
    config: ConfigType,
    discovery_info: DiscoveryInfoType | None = None,
) -> LaMetricNotificationService:
    """Get the LaMetric notification service."""
    return LaMetricNotificationService(
        hass.data[DOMAIN],
        config[CONF_ICON],
        config[CONF_LIFETIME] * 1000,
        config[CONF_CYCLES],
        config[CONF_PRIORITY],
        config[CONF_ICON_TYPE],
    )


class LaMetricNotificationService(BaseNotificationService):
    """Implement the notification service for LaMetric."""

    def __init__(
        self,
        hasslametricmanager: HassLaMetricManager,
        icon: str,
        lifetime: int,
        cycles: int,
        priority: str,
        icon_type: str,
    ) -> None:
        """Initialize the service."""
        self.hasslametricmanager = hasslametricmanager
        self._icon = icon
        self._lifetime = lifetime
        self._cycles = cycles
        self._priority = priority
        self._icon_type = icon_type
        self._devices: list[dict[str, Any]] = []

    def send_message(self, message: str = "", **kwargs: Any) -> None:
        """Send a message to some LaMetric device."""

        targets = kwargs.get(ATTR_TARGET)
        data = kwargs.get(ATTR_DATA)
        LOGGER.debug("Targets/Data: %s/%s", targets, data)
        icon = self._icon
        cycles = self._cycles
        sound = None
        priority = self._priority
        icon_type = self._icon_type

        # Additional data?
        if data is not None:
            if "icon" in data:
                icon = data["icon"]
            if "sound" in data:
                try:
                    sound = Sound(category="notifications", sound_id=data["sound"])
                    LOGGER.debug("Adding notification sound %s", data["sound"])
                except AssertionError:
                    LOGGER.error("Sound ID %s unknown, ignoring", data["sound"])
            if "cycles" in data:
                cycles = int(data["cycles"])
            if "icon_type" in data:
                if data["icon_type"] in AVAILABLE_ICON_TYPES:
                    icon_type = data["icon_type"]
                else:
                    LOGGER.warning(
                        "Priority %s invalid, using default %s",
                        data["priority"],
                        priority,
                    )
            if "priority" in data:
                if data["priority"] in AVAILABLE_PRIORITIES:
                    priority = data["priority"]
                else:
                    LOGGER.warning(
                        "Priority %s invalid, using default %s",
                        data["priority"],
                        priority,
                    )
        text_frame = SimpleFrame(icon, message)
        LOGGER.debug(
            "Icon/Message/Cycles/Lifetime: %s, %s, %d, %d",
            icon,
            message,
            self._cycles,
            self._lifetime,
        )

        frames = [text_frame]

        model = Model(frames=frames, cycles=cycles, sound=sound)
        lmn = self.hasslametricmanager.manager
        try:
            self._devices = lmn.get_devices()
        except TokenExpiredError:
            LOGGER.debug("Token expired, fetching new token")
            lmn.get_token()
            self._devices = lmn.get_devices()
        except RequestsConnectionError:
            LOGGER.warning(
                "Problem connecting to LaMetric, using cached devices instead"
            )
        for dev in self._devices:
            if targets is None or dev["name"] in targets:
                try:
                    lmn.set_device(dev)
                    lmn.send_notification(
                        model,
                        lifetime=self._lifetime,
                        priority=priority,
                        icon_type=icon_type,
                    )
                    LOGGER.debug("Sent notification to LaMetric %s", dev["name"])
                except OSError:
                    LOGGER.warning("Cannot connect to LaMetric %s", dev["name"])
