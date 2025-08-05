"""Huawei LTE buttons."""

from __future__ import annotations

import logging

from huawei_lte_api.enums.device import ControlModeEnum

from homeassistant.components.button import (
    ButtonDeviceClass,
    ButtonEntity,
    ButtonEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_platform

from .const import DOMAIN
from .entity import HuaweiLteBaseEntityWithDevice

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: entity_platform.AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Huawei LTE buttons."""
    router = hass.data[DOMAIN].routers[config_entry.entry_id]
    buttons = [
        ClearTrafficStatisticsButton(router),
        RestartButton(router),
    ]
    async_add_entities(buttons)


class BaseButton(HuaweiLteBaseEntityWithDevice, ButtonEntity):
    """Huawei LTE button base class."""

    @property
    def _device_unique_id(self) -> str:
        """Return unique ID for entity within a router."""
        return f"button-{self.entity_description.key}"

    async def async_update(self) -> None:
        """Update is not necessary for button entities."""

    def press(self) -> None:
        """Press button."""
        if self.router.suspended:
            _LOGGER.debug(
                "%s: ignored, integration suspended", self.entity_description.key
            )
            return
        result = self._press()
        _LOGGER.debug("%s: %s", self.entity_description.key, result)

    def _press(self) -> str:
        """Invoke low level action of button press."""
        raise NotImplementedError


BUTTON_KEY_CLEAR_TRAFFIC_STATISTICS = "clear_traffic_statistics"


class ClearTrafficStatisticsButton(BaseButton):
    """Huawei LTE clear traffic statistics button."""

    entity_description = ButtonEntityDescription(
        key=BUTTON_KEY_CLEAR_TRAFFIC_STATISTICS,
        name="Clear traffic statistics",
        entity_category=EntityCategory.CONFIG,
    )

    def _press(self) -> str:
        """Call clear traffic statistics endpoint."""
        return self.router.client.monitoring.set_clear_traffic()


BUTTON_KEY_RESTART = "restart"


class RestartButton(BaseButton):
    """Huawei LTE restart button."""

    entity_description = ButtonEntityDescription(
        key=BUTTON_KEY_RESTART,
        name="Restart",
        device_class=ButtonDeviceClass.RESTART,
        entity_category=EntityCategory.CONFIG,
    )

    def _press(self) -> str:
        """Call restart endpoint."""
        return self.router.client.device.set_control(ControlModeEnum.REBOOT)
