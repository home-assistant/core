"""YoLink Device Instance."""
from __future__ import annotations

import logging

from yolink_client.yolink_device import YoLinkDeviceEntry
from yolink_client.yolink_model import BRDP, BSDPHelper

from homeassistant.const import CONF_NAME, CONF_STATE, CONF_TOKEN, CONF_TYPE
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity

from .const import ATTR_DEVICE_ID, DOMAIN, MANUFACTURER


def resolve_state_in_event(data: BRDP, event_type: str) -> dict | None:
    """Get state in BRDP."""
    if event_type in ("Report", "Alert", "StatusChange", "getState"):
        return data.data
    return None


async def parse_state(state):
    """Parse state from data, Should be override."""
    return


class YoLinkDevice(YoLinkDeviceEntry):
    """Representation a base YoLink device."""

    def __init__(self, device: dict, hass, config_entry):
        """Init YoLink Device."""
        self.device_id = device[ATTR_DEVICE_ID]
        self.device_name = device[CONF_NAME]
        self.device_net_token = device[CONF_TOKEN]
        self.device_type = device[CONF_TYPE]
        self._config_entry = config_entry
        self.hass: HomeAssistant = hass
        self._is_gateway = False
        self.entities: list[YoLinkDeviceEntity] = []

    @property
    def should_poll(self) -> bool:
        """Return the polling state. No polling needed."""
        return True

    @property
    def device_info(self) -> entity.DeviceInfo:
        """Return the device info of the YoLink device."""

        return entity.DeviceInfo(
            identifiers={(DOMAIN, self.device_id)},
            manufacturer=MANUFACTURER,
            model=self.device_type,
            name=self.device_name,
        )

    @callback
    def push_data(self, data: BRDP):
        """Push from Hub."""
        if data.event is not None:
            event_param = data.event.split(".")
            event_type = event_param[len(event_param) - 1]
            resovled_state = resolve_state_in_event(data, event_type)
            if resovled_state is not None:
                self.hass.async_create_task(parse_state(resovled_state))

    async def call_device_http_api(self, method: str, params: dict | None) -> BRDP:
        """Call device API."""
        bsdp_helper = BSDPHelper(
            self.device_id,
            self.device_net_token,
            f"{self.device_type}.{method}",
        )
        if params is not None:
            bsdp_helper.addParams(params)
        return await self.hass.data[DOMAIN][self._config_entry.entry_id][
            "client"
        ].call_yolink_api(bsdp_helper.build())

    async def get_state_with_api(self) -> BRDP:
        """Call *.getState with device to request realtime state data."""
        return await self.call_device_http_api("getState", None)

    async def fetch_state_with_api(self) -> BRDP:
        """Call *.fetchState with device to fetch state data."""
        return await self.call_device_http_api("fetchState", None)

    @property
    def logger(self) -> logging.Logger:
        """Return logger."""
        return logging.getLogger(__name__)

    def async_added_to_hass(self) -> None:
        """Start unavailability tracking."""
        for entity_item in self.entities:
            if entity_item.is_registed is False:
                return

        async def request_state():
            resp = await self.fetch_state_with_api()
            if "state" in resp.data:
                await parse_state(resp.data[CONF_STATE])

        self.hass.create_task(request_state())


class YoLinkDeviceEntity(entity.Entity):
    """Representation a base YoLink device."""

    def __init__(self, device: YoLinkDevice, entity_type: str, config_entry):
        """Initialize the YoLink device."""
        self._yl_device = device
        self._state = None
        self._is_available = True
        self._attr_unique_id = f"{device.device_id}-{entity_type}"
        self._attr_net_token = device.device_net_token
        self._model = device.device_type
        self._attr_name = f"{device.device_name} ({entity_type})"
        self._type = entity_type
        self._extra_state_attributes: dict = {}
        self._remove_unavailability_tracker = None
        self._is_gateway = False
        self._config_entry = config_entry
        self._registed_ = False

    @property
    def logger(self) -> logging.Logger:
        """Return logger."""
        return logging.getLogger(__name__)

    async def async_added_to_hass(self) -> None:
        """Start unavailability tracking."""
        self._registed_ = True
        self._yl_device.async_added_to_hass()

    @property
    def device_id(self) -> str:
        """Return the device id of the YoLink device."""
        return self._yl_device.device_id

    @property
    def device_info(self) -> entity.DeviceInfo:
        """Return the device info for HA."""
        return self._yl_device.device_info

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._is_available

    @property
    def should_poll(self) -> bool:
        """Return the polling state. No polling needed."""
        return self._yl_device.should_poll

    @property
    def extra_state_attributes(self) -> dict:
        """Return the state attributes."""
        return self._extra_state_attributes

    @property
    def is_registed(self) -> bool:
        """Return entity register state."""
        return self._registed_

    @callback
    def _async_set_unavailable(self, now) -> None:
        """Set state to UNAVAILABLE."""
        self._remove_unavailability_tracker = None
        self._is_available = False
        self.async_write_ha_state()

    def update(self) -> None:
        """Get the current Device State address for hostname."""

    def __repr__(self) -> str:
        """Return the representation."""
        return f"<YoLinkDevice {self.name}:Class: {self.device_class} />"
