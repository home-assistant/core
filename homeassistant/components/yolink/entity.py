"""Support for YoLink Device."""
from __future__ import annotations

from yolink.client import YoLinkClient
from yolink.device import YoLinkDevice
from yolink.model import BRDP

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo, Entity

from .const import DOMAIN, MANUFACTURER


def resolve_state_in_event(data: BRDP, event_type: str) -> dict | None:
    """Get state in BRDP."""
    if event_type in ("Report", "Alert", "StatusChange", "getState"):
        return data.data
    return None


class YoLinkHADevice(YoLinkDevice):
    """YoLink Device Common."""

    def __init__(
        self,
        hass: HomeAssistant,
        device: dict,
        client: YoLinkClient,
    ) -> None:
        """HA YoLink Device."""
        super().__init__(device, client)
        self.hass = hass

    @property
    def device_id(self) -> str:
        """Return the device id of the YoLink device."""
        return self._device_id


class YoLinkEntity(YoLinkHADevice, Entity):
    """YoLink Device Basic Entity."""

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info for HA."""

        return DeviceInfo(
            identifiers={(DOMAIN, self.device_id)},
            manufacturer=MANUFACTURER,
            model=self._device_type,
            name=self._device_name,
        )

    def _async_set_unavailable(self, now) -> None:
        """Set state to UNAVAILABLE."""
        self._attr_available = False

    @callback
    def on_data_push(self, data: BRDP) -> None:
        """Push from Hub."""
        if data.event is None:
            return None
        event_param = data.event.split(".")
        event_type = event_param[len(event_param) - 1]
        resolved_state = resolve_state_in_event(data, event_type)
        if resolved_state is None:
            return None
        self.hass.async_create_task(self.update_entity_state(resolved_state))

    async def update_entity_state(self, state: dict) -> None:
        """Parse and update entity stat, Should be override."""
        raise NotImplementedError
