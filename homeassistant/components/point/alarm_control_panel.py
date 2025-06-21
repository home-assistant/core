"""Support for Minut Point."""

from __future__ import annotations

import logging

from pypoint import PointSession

from homeassistant.components.alarm_control_panel import (
    AlarmControlPanelEntity,
    AlarmControlPanelEntityFeature,
    AlarmControlPanelState,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import PointConfigEntry
from .const import DOMAIN, SIGNAL_WEBHOOK

_LOGGER = logging.getLogger(__name__)


EVENT_MAP = {
    "off": AlarmControlPanelState.DISARMED,
    "alarm_silenced": AlarmControlPanelState.DISARMED,
    "alarm_grace_period_expired": AlarmControlPanelState.TRIGGERED,
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: PointConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up a Point's alarm_control_panel based on a config entry."""
    coordinator = config_entry.runtime_data

    def async_discover_home(home_id: str) -> None:
        """Discover and add a discovered home."""
        async_add_entities([MinutPointAlarmControl(coordinator.point, home_id)])

    coordinator.new_home_callback = async_discover_home

    for home_id in coordinator.point.homes:
        async_discover_home(home_id)


class MinutPointAlarmControl(AlarmControlPanelEntity):
    """The platform class required by Home Assistant."""

    _attr_supported_features = AlarmControlPanelEntityFeature.ARM_AWAY
    _attr_code_arm_required = False

    def __init__(self, point: PointSession, home_id: str) -> None:
        """Initialize the entity."""
        self._client = point
        self._home_id = home_id
        self._home = point.homes[self._home_id]

        self._attr_name = self._home["name"]
        self._attr_unique_id = f"point.{home_id}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, home_id)},
            manufacturer="Minut",
            name=self._attr_name,
        )

    async def async_added_to_hass(self) -> None:
        """Call when entity is added to HOme Assistant."""
        await super().async_added_to_hass()
        self.async_on_remove(
            async_dispatcher_connect(self.hass, SIGNAL_WEBHOOK, self._webhook_event)
        )

    @callback
    def _webhook_event(self, data, webhook):
        """Process new event from the webhook."""
        _type = data.get("event", {}).get("type")
        _device_id = data.get("event", {}).get("device_id")
        _changed_by = data.get("event", {}).get("user_id")
        if (
            _device_id not in self._home["devices"] and _type not in EVENT_MAP
        ) and _type != "alarm_silenced":  # alarm_silenced does not have device_id
            return
        _LOGGER.debug("Received webhook: %s", _type)
        self._home["alarm_status"] = _type
        self._attr_changed_by = _changed_by
        self.async_write_ha_state()

    @property
    def alarm_state(self) -> AlarmControlPanelState:
        """Return state of the device."""
        return EVENT_MAP.get(
            self._home["alarm_status"], AlarmControlPanelState.ARMED_AWAY
        )

    async def async_alarm_disarm(self, code: str | None = None) -> None:
        """Send disarm command."""
        status = await self._client.alarm_disarm(self._home_id)
        if status:
            self._home["alarm_status"] = "off"

    async def async_alarm_arm_away(self, code: str | None = None) -> None:
        """Send arm away command."""
        status = await self._client.alarm_arm(self._home_id)
        if status:
            self._home["alarm_status"] = "on"
