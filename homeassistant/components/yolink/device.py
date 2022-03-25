"""YoLink Device Instance."""

import logging
from typing import List

from yolink_client.yolink_device import YoLinkDeviceEntry
from yolink_client.yolink_model import BRDP, BSDPHelper

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import Entity

from .const import DOMAIN


class YoLinkDevice(YoLinkDeviceEntry):
    """Representation a base YoLink device."""

    def __init__(self, device: dict, hass, config_entry):
        """Init YoLink Device."""
        self.device_id = device["deviceId"]
        self.device_name = device["name"]
        self.device_net_token = device["token"]
        self.device_type = device["type"]
        self._config_entry = config_entry
        self.hass: HomeAssistant = hass
        self._is_gateway = False
        self.entities: List[YoLinkDeviceEntity] = []

    @property
    def should_poll(self):
        """Return the polling state. No polling needed."""
        return True

    @property
    def device_info(self):
        """Return the device info of the YoLink device."""
        return {
            "identifiers": {(DOMAIN, self.device_id)},
            "manufacturer": "YoLink",
            "model": self.device_type,
            "name": self.device_name,
        }

    def resolve_state_in_event(self, data: BRDP, event_type: str):
        """Get state in BRDP."""
        if (
            event_type == "Report"
            or event_type == "Alert"
            or event_type == "StatusChange"
            or event_type == "getState"
        ):
            return data.data
        return None

    @callback
    def push_data(self, data: BRDP):
        """Push from Hub."""
        if data.event is not None:
            event_param = data.event.split(".")
            event_type = event_param[len(event_param) - 1]
            resovled_state = self.resolve_state_in_event(data, event_type)
            if resovled_state is not None:
                self.hass.async_create_task(self.parse_state(resovled_state))

    async def parse_state(self, state):
        """Parse state from data, Should be override."""
        return

    async def call_device_http_api(self, method: str, params: dict) -> BRDP:
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

    async def get_state_with_api(self):
        """Call *.getState with device to request realtime state data."""
        return await self.call_device_http_api("getState", None)

    async def fetch_state_with_api(self):
        """Call *.fetchState with device to fetch state data."""
        return await self.call_device_http_api("fetchState", None)

    @property
    def logger(self) -> logging.Logger:
        """Return logger."""
        return logging.getLogger(__name__)

    def async_added_to_hass(self):
        """Start unavailability tracking."""
        for entity in self.entities:
            if entity._registed_ is False:
                return

        async def request_state():
            resp = await self.fetch_state_with_api()
            if "state" in resp.data:
                await self.parse_state(resp.data["state"])

        self.hass.create_task(request_state())


class YoLinkDeviceEntity(Entity):
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

    async def async_added_to_hass(self):
        """Start unavailability tracking."""
        self._registed_ = True
        self._yl_device.async_added_to_hass()

    @property
    def device_id(self):
        """Return the device id of the YoLink device."""
        return self._yl_device.device_id

    @property
    def device_info(self):
        """Return the device info for HA."""
        return self._yl_device.device_info

    @property
    def available(self):
        """Return True if entity is available."""
        return self._is_available

    @property
    def should_poll(self):
        """Return the polling state. No polling needed."""
        return self._yl_device.should_poll

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        return self._extra_state_attributes

    @callback
    def _async_set_unavailable(self, now):
        """Set state to UNAVAILABLE."""
        self._remove_unavailability_tracker = None
        self._is_available = False
        self.async_write_ha_state()

    def update(self) -> None:
        """Get the current Device State address for hostname."""

    def __repr__(self) -> str:
        """Return the representation."""
        return f"<YoLinkDevice {self.name}:Class: {self.device_class} />"
