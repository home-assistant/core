"""Support for YoLink Device."""
from __future__ import annotations

from yolink.client import YoLinkClient
from yolink.device import YoLinkDevice
from yolink.model import BRDP

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import YoLinkCoordinator
from .const import ATTR_DEVICE_STATE, DOMAIN, MANUFACTURER


def resolve_state_in_event(data: BRDP, event_type: str) -> dict | None:
    """Get state in BRDP."""
    if event_type in ("Report", "Alert", "StatusChange", "getState"):
        return data.data
    return None


class YoLinkEntity(CoordinatorEntity[YoLinkCoordinator]):
    """YoLink Device Basic Entity."""

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: YoLinkCoordinator,
        device_info: dict,
        client: YoLinkClient,
    ) -> None:
        """Init YoLink Entity."""
        super().__init__(coordinator)
        self.hass = hass
        self.device = YoLinkDevice(device_info, client)

    @property
    def device_id(self) -> str:
        """Return the device id of the YoLink device."""
        return self.device.device_id

    async def async_added_to_hass(self) -> None:
        """Add to hass."""

        async def request_state():
            resp = await self.device.fetch_state_with_api()
            if "state" in resp.data:
                self.update_entity_state(resp.data[ATTR_DEVICE_STATE])

        self.hass.create_task(request_state())
        self.coordinator.async_add_listener(self._handle_coordinator_update)

    @callback
    def _handle_coordinator_update(self) -> None:
        _device_id = self.coordinator.data[0]
        if _device_id != self.device.device_id:
            return None
        data = self.coordinator.data[1]
        if data.event is None:
            return None
        event_param = data.event.split(".")
        event_type = event_param[len(event_param) - 1]
        resolved_state = resolve_state_in_event(data, event_type)
        if resolved_state is None:
            return None
        self.update_entity_state(data)

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info for HA."""
        return DeviceInfo(
            identifiers={(DOMAIN, self.device.device_id)},
            manufacturer=MANUFACTURER,
            model=self.device.device_type,
            name=self.device.device_name,
        )

    def _async_set_unavailable(self, now) -> None:
        """Set state to UNAVAILABLE."""
        self._attr_available = False

    @callback
    def update_entity_state(self, state: dict) -> None:
        """Parse and update entity stat, Should be override."""
        raise NotImplementedError
