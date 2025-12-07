"""Switch platform for Hass.io addons."""

from __future__ import annotations

import logging
from typing import Any

from aiohasupervisor import SupervisorError

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ICON
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import ADDONS_COORDINATOR, ATTR_STARTED, ATTR_STATE, DATA_KEY_ADDONS
from .entity import HassioAddonEntity
from .handler import get_supervisor_client

_LOGGER = logging.getLogger(__name__)


ENTITY_DESCRIPTION = SwitchEntityDescription(
    key=ATTR_STATE,
    name=None,
    icon="mdi:puzzle",
    entity_registry_enabled_default=False,
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Switch set up for Hass.io config entry."""
    coordinator = hass.data[ADDONS_COORDINATOR]

    async_add_entities(
        HassioAddonSwitch(
            addon=addon,
            coordinator=coordinator,
            entity_description=ENTITY_DESCRIPTION,
        )
        for addon in coordinator.data[DATA_KEY_ADDONS].values()
    )


class HassioAddonSwitch(HassioAddonEntity, SwitchEntity):
    """Switch for Hass.io add-ons."""

    @property
    def is_on(self) -> bool | None:
        """Return true if the add-on is on."""
        addon_data = self.coordinator.data[DATA_KEY_ADDONS].get(self._addon_slug, {})
        state = addon_data.get(self.entity_description.key)
        return state == ATTR_STARTED

    @property
    def entity_picture(self) -> str | None:
        """Return the icon of the add-on if any."""
        if not self.available:
            return None
        addon_data = self.coordinator.data[DATA_KEY_ADDONS].get(self._addon_slug, {})
        if addon_data.get(ATTR_ICON):
            return f"/api/hassio/addons/{self._addon_slug}/icon"
        return None

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the entity on."""
        supervisor_client = get_supervisor_client(self.hass)
        try:
            await supervisor_client.addons.start_addon(self._addon_slug)
        except SupervisorError as err:
            raise HomeAssistantError(err) from err

        await self.coordinator.force_addon_info_data_refresh(self._addon_slug)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        supervisor_client = get_supervisor_client(self.hass)
        try:
            await supervisor_client.addons.stop_addon(self._addon_slug)
        except SupervisorError as err:
            _LOGGER.error("Failed to stop addon %s: %s", self._addon_slug, err)
            raise HomeAssistantError(err) from err

        await self.coordinator.force_addon_info_data_refresh(self._addon_slug)
