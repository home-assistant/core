"""Support for Govee Heater switches."""

import json
import logging

import requests

from homeassistant.components.switch import SwitchEntity

from .const import CONF_API_KEY, CONF_DEVICE_ID, CONF_SKU

_LOGGER = logging.getLogger(__name__)
API_URL = "https://openapi.api.govee.com/router/api/v1/device/control"


def send_command(api_key, device_id, sku, command):
    """Send control command to the Govee API."""
    headers = {"Govee-API-Key": api_key, "Content-Type": "application/json"}
    payload = {
        "requestId": "uuid",
        "payload": {
            "sku": sku,
            "device": device_id,
            "capability": {
                "type": "devices.capabilities.on_off",
                "instance": "powerSwitch",
                "value": command,
            },
        },
    }
    json_payload = json.dumps(payload, ensure_ascii=False)
    _LOGGER.debug("Sending request to Govee API - URL: %s", API_URL)
    _LOGGER.debug("Headers: %s", headers)
    _LOGGER.debug("Payload: %s", json_payload)

    try:
        response = requests.post(
            API_URL, data=json_payload, headers=headers, timeout=20
        )
        _LOGGER.debug("Response status code: %s", response.status_code)
        _LOGGER.debug("Response content: %s", response.text)
        if response.status_code != 200:
            _LOGGER.error("Govee API error: %s", response.text)
        else:
            _LOGGER.info("Successfully sent command to Govee API: %s", command)
    except (
        ConnectionError,
        TimeoutError,
        ValueError,
    ) as e:  # Be specific about what exceptions you expect
        _LOGGER.error("Exception during API call: %s", str(e))


class GoveeHeater(SwitchEntity):
    """Representation of a Govee Heater switch."""

    def __init__(self, api_key, device_id, sku):
        """Initialize the heater switch."""
        super().__init__()
        self._api_key = api_key
        self._device_id = device_id
        self._sku = sku
        self._attr_is_on = False  # Use _attr_is_on instead of _is_on
        self._attr_name = "Govee Heater"
        self._attr_unique_id = f"govee_heater_{device_id}"
        _LOGGER.debug("GoveeHeater initialized for device: %s", device_id)

    @property
    def available(self):
        """Return True if entity is available."""
        return True

    def turn_on(self, **kwargs):
        """Turn the heater on."""
        _LOGGER.debug("Turning on heater: %s", self._device_id)
        if send_command(self._api_key, self._device_id, self._sku, 1):
            self._attr_is_on = True  # Update _attr_is_on
            self.schedule_update_ha_state()
            _LOGGER.debug("Heater turned on successfully")
        else:
            _LOGGER.error("Failed to turn on heater")

    def turn_off(self, **kwargs):
        """Turn the heater off."""
        _LOGGER.debug("Turning off heater: %s", self._device_id)
        if send_command(self._api_key, self._device_id, self._sku, 0):
            self._attr_is_on = False  # Update _attr_is_on
            self.schedule_update_ha_state()
            _LOGGER.debug("Heater turned off successfully")
        else:
            _LOGGER.error("Failed to turn off heater")


async def async_setup_entry(_hass, entry, async_add_entities):
    """Set up the Govee Heater switch from a config entry."""
    api_key = entry.data[CONF_API_KEY]
    device_id = entry.data[CONF_DEVICE_ID]
    sku = entry.data[CONF_SKU]

    _LOGGER.debug("Setting up Govee Heater with ID: %s", device_id)
    async_add_entities([GoveeHeater(api_key, device_id, sku)], True)
