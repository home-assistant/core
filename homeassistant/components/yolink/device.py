"""YoLink Device Instance."""

import logging

import async_timeout

from homeassistant.core import callback
from homeassistant.helpers.entity import Entity

from .const import DOMAIN
from .model import BSDPHelper


class YoLinkDevice(Entity):
    """Representation a base YoLink device."""

    def __init__(self, device, device_type, config_entry):
        """Initialize the YoLink device."""
        self._state = None
        self._is_available = True
        self._attr_unique_id = device["deviceId"]
        self._attr_net_token = device["token"]
        self._model = device["type"]
        self._attr_name = device["name"]
        self._type = device_type
        self._extra_state_attributes = {}
        self._remove_unavailability_tracker = None
        self._is_gateway = False
        self._config_entry = config_entry

    @property
    def logger(self) -> logging.Logger:
        """Return logger."""
        return logging.getLogger(__name__)

    def _add_push_data_job(self, *args):
        self.hass.add_job(self.push_data, *args)

    async def async_added_to_hass(self):
        """Start unavailability tracking."""
        # self._xiaomi_hub.callbacks[self._sid].append(self._add_push_data_job)
        # self._async_track_unavailable()

    @property
    def devceId(self):
        """Return the device id of the Xiaomi Aqara device."""
        return self._attr_unique_id

    @property
    def device_info(self):
        """Return the device info of the Xiaomi Aqara device."""
        if self._is_gateway:
            device_info = {
                "identifiers": {(DOMAIN, self._attr_unique_id)},
                "model": self._model,
            }
        else:
            device_info = {
                # "connections": {
                #     (device_registry.CONNECTION_ZIGBEE, self._attr_unique_id)
                # },
                "identifiers": {(DOMAIN, self._attr_unique_id)},
                "manufacturer": "YoLink",
                "model": self._model,
                "name": self._attr_name,
                # "sw_version": self._protocol,
                # "via_device": (DOMAIN, self._gateway_id),
            }

        return device_info

    @property
    def available(self):
        """Return True if entity is available."""
        return self._is_available

    @property
    def should_poll(self):
        """Return the polling state. No polling needed."""
        return True

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

    def parse_state(self, state):
        """Parse state from data, Should be override."""

        return

    @callback
    def push_data(self, data, raw_data):
        """Push from Hub."""

        self.logger.info("PUSH >> %s: %s", self, data)
        # was_unavailable = self._async_track_unavailable()
        # is_data = self.parse_data(data, raw_data)
        # is_voltage = self.parse_voltage(data)
        # if is_data or is_voltage or was_unavailable:
        #     self.async_write_ha_state()

    async def async_update(self) -> None:
        """Get the current Device State address for hostname."""
        try:
            async with async_timeout.timeout(5):
                response = await self.getStateFromYoLink()
        except BaseException as err:
            self.logger.warning(
                "Fetch device(%s) state failed: %s",
                self._attr_unique_id,
                err,
            )
            response = None

        if response and response.data:
            self.parse_state(response.data)
            # self._attr_native_value = response[0].host
        # else:
        # self._attr_native_value = None

    def __repr__(self) -> str:
        """Return the representation."""
        return f"<YoLinkDevice {self.name}:Class: {self.device_class} />"

    async def getStateFromYoLink(self):
        """Call *.getState with device to fetch realtime state data."""
        bsdp = BSDPHelper(
            self.devceId,
            self._attr_net_token,
            f"{self._model}.getState",
        ).build()
        return await self.hass.data[DOMAIN][self._config_entry.entry_id][
            "client"
        ].callYoLinkAPI(bsdp)
