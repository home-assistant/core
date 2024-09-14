"""Support for Minut Point."""

from __future__ import annotations

from collections.abc import Callable
import logging

from homeassistant.components.alarm_control_panel import (
    DOMAIN as ALARM_CONTROL_PANEL_DOMAIN,
    AlarmControlPanelEntity,
    AlarmControlPanelEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    STATE_ALARM_ARMED_AWAY,
    STATE_ALARM_DISARMED,
    STATE_ALARM_TRIGGERED,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import MinutPointClient
from .const import DOMAIN as POINT_DOMAIN, POINT_DISCOVERY_NEW, SIGNAL_WEBHOOK

_LOGGER = logging.getLogger(__name__)


EVENT_MAP = {
    "off": STATE_ALARM_DISARMED,
    "alarm_silenced": STATE_ALARM_DISARMED,
    "alarm_grace_period_expired": STATE_ALARM_TRIGGERED,
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up a Point's alarm_control_panel based on a config entry."""

    async def async_discover_home(home_id):
        """Discover and add a discovered home."""
        client = config_entry.runtime_data.client
        async_add_entities([MinutPointAlarmControl(client, home_id)], True)

    async_dispatcher_connect(
        hass,
        POINT_DISCOVERY_NEW.format(ALARM_CONTROL_PANEL_DOMAIN, POINT_DOMAIN),
        async_discover_home,
    )


class MinutPointAlarmControl(AlarmControlPanelEntity):
    """The platform class required by Home Assistant."""

    _attr_supported_features = AlarmControlPanelEntityFeature.ARM_AWAY
    _attr_code_arm_required = False

    def __init__(self, point_client: MinutPointClient, home_id: str) -> None:
        """Initialize the entity."""
        self._client = point_client
        self._home_id = home_id
        self._async_unsub_hook_dispatcher_connect: Callable[[], None] | None = None
        self._home = point_client.homes[self._home_id]

        self._attr_name = self._home["name"]
        self._attr_unique_id = f"point.{home_id}"
        self._attr_device_info = DeviceInfo(
            identifiers={(POINT_DOMAIN, home_id)},
            manufacturer="Minut",
            name=self._attr_name,
        )

    async def async_added_to_hass(self) -> None:
        """Call when entity is added to HOme Assistant."""
        await super().async_added_to_hass()
        self._async_unsub_hook_dispatcher_connect = async_dispatcher_connect(
            self.hass, SIGNAL_WEBHOOK, self._webhook_event
        )

    async def async_will_remove_from_hass(self) -> None:
        """Disconnect dispatcher listener when removed."""
        await super().async_will_remove_from_hass()
        if self._async_unsub_hook_dispatcher_connect:
            self._async_unsub_hook_dispatcher_connect()

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
    def state(self) -> str:
        """Return state of the device."""
        return EVENT_MAP.get(self._home["alarm_status"], STATE_ALARM_ARMED_AWAY)

    async def async_alarm_disarm(self, code: str | None = None) -> None:
        """Send disarm command."""
        status = await self._client.async_alarm_disarm(self._home_id)
        if status:
            self._home["alarm_status"] = "off"

    async def async_alarm_arm_away(self, code: str | None = None) -> None:
        """Send arm away command."""
        status = await self._client.async_alarm_arm(self._home_id)
        if status:
            self._home["alarm_status"] = "on"
