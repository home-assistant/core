"""Support for loads connected with WMS WebControl pro."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from wmspro.const import (
    WMS_WebControl_pro_API_actionDescription,
    WMS_WebControl_pro_API_responseType,
)

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import WebControlProConfigEntry
from .entity import WebControlProGenericEntity

SCAN_INTERVAL = timedelta(seconds=15)
PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: WebControlProConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the WMS based switches from a config entry."""
    hub = config_entry.runtime_data

    async_add_entities(
        WebControlProSwitch(config_entry.entry_id, dest)
        for dest in hub.dests.values()
        if dest.hasAction(WMS_WebControl_pro_API_actionDescription.LoadSwitch)
    )


class WebControlProSwitch(WebControlProGenericEntity, SwitchEntity):
    """Representation of a WMS based switch."""

    _attr_name = None

    @property
    def is_on(self) -> bool:
        """Return true if switch is on."""
        action = self._dest.action(WMS_WebControl_pro_API_actionDescription.LoadSwitch)
        return action["onOffState"]

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        action = self._dest.action(WMS_WebControl_pro_API_actionDescription.LoadSwitch)
        await action(
            onOffState=True, responseType=WMS_WebControl_pro_API_responseType.Detailed
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        action = self._dest.action(WMS_WebControl_pro_API_actionDescription.LoadSwitch)
        await action(
            onOffState=False, responseType=WMS_WebControl_pro_API_responseType.Detailed
        )
