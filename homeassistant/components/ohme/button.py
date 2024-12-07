"""Platform for button."""

from __future__ import annotations
import logging
import asyncio

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.components.button import ButtonEntity

from .const import DOMAIN, DATA_CLIENT, DATA_COORDINATORS, COORDINATOR_CHARGESESSIONS
from .base import OhmeEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, config_entry: ConfigEntry, async_add_entities
):
    """Setup switches."""
    account_id = config_entry.data["email"]

    client = hass.data[DOMAIN][account_id][DATA_CLIENT]
    coordinator = hass.data[DOMAIN][account_id][DATA_COORDINATORS][
        COORDINATOR_CHARGESESSIONS
    ]

    buttons = []

    if client.is_capable("pluginsRequireApprovalMode"):
        buttons.append(OhmeApproveChargeButton(coordinator, hass, client))

        async_add_entities(buttons, update_before_add=True)


class OhmeApproveChargeButton(OhmeEntity, ButtonEntity):
    """Button for approving a charge."""

    _attr_translation_key = "approve_charge"
    _attr_icon = "mdi:check-decagram-outline"

    async def async_press(self):
        """Approve the charge."""
        await self._client.async_approve_charge()

        await asyncio.sleep(1)
        await self.coordinator.async_refresh()
