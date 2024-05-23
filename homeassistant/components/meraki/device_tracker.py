"""Support for the Meraki CMX location service."""

from __future__ import annotations

from http import HTTPStatus
import json
import logging

import voluptuous as vol

from homeassistant.components.device_tracker import (
    PLATFORM_SCHEMA as PARENT_PLATFORM_SCHEMA,
    AsyncSeeCallback,
    SourceType,
)
from homeassistant.components.http import KEY_HASS, HomeAssistantView
from homeassistant.core import HomeAssistant, callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

CONF_VALIDATOR = "validator"
CONF_SECRET = "secret"
URL = "/api/meraki"
VERSION = "2.0"


_LOGGER = logging.getLogger(__name__)


PLATFORM_SCHEMA = PARENT_PLATFORM_SCHEMA.extend(
    {vol.Required(CONF_VALIDATOR): cv.string, vol.Required(CONF_SECRET): cv.string}
)


async def async_setup_scanner(
    hass: HomeAssistant,
    config: ConfigType,
    async_see: AsyncSeeCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> bool:
    """Set up an endpoint for the Meraki tracker."""
    hass.http.register_view(MerakiView(config, async_see))

    return True


class MerakiView(HomeAssistantView):
    """View to handle Meraki requests."""

    url = URL
    name = "api:meraki"
    requires_auth = False

    def __init__(self, config: ConfigType, async_see: AsyncSeeCallback) -> None:
        """Initialize Meraki URL endpoints."""
        self.async_see = async_see
        self.validator = config[CONF_VALIDATOR]
        self.secret = config[CONF_SECRET]

    async def get(self, request):
        """Meraki message received as GET."""
        return self.validator

    async def post(self, request):
        """Meraki CMX message received."""
        try:
            data = await request.json()
        except ValueError:
            return self.json_message("Invalid JSON", HTTPStatus.BAD_REQUEST)
        _LOGGER.debug("Meraki Data from Post: %s", json.dumps(data))
        if not data.get("secret", False):
            _LOGGER.error("The secret is invalid")
            return self.json_message("No secret", HTTPStatus.UNPROCESSABLE_ENTITY)
        if data["secret"] != self.secret:
            _LOGGER.error("Invalid Secret received from Meraki")
            return self.json_message("Invalid secret", HTTPStatus.UNPROCESSABLE_ENTITY)
        if data["version"] != VERSION:
            _LOGGER.error("Invalid API version: %s", data["version"])
            return self.json_message("Invalid version", HTTPStatus.UNPROCESSABLE_ENTITY)
        _LOGGER.debug("Valid Secret")
        if data["type"] not in ("DevicesSeen", "BluetoothDevicesSeen"):
            _LOGGER.error("Unknown Device %s", data["type"])
            return self.json_message(
                "Invalid device type", HTTPStatus.UNPROCESSABLE_ENTITY
            )
        _LOGGER.debug("Processing %s", data["type"])
        if not data["data"]["observations"]:
            _LOGGER.debug("No observations found")
            return None
        self._handle(request.app[KEY_HASS], data)

    @callback
    def _handle(self, hass, data):
        for i in data["data"]["observations"]:
            data["data"]["secret"] = "hidden"

            lat = i["location"]["lat"]
            lng = i["location"]["lng"]
            try:
                accuracy = int(float(i["location"]["unc"]))
            except ValueError:
                accuracy = 0

            mac = i["clientMac"]
            _LOGGER.debug("clientMac: %s", mac)

            if lat == "NaN" or lng == "NaN":
                _LOGGER.debug("No coordinates received, skipping location for: %s", mac)
                gps_location = None
                accuracy = None
            else:
                gps_location = (lat, lng)

            attrs = {}
            if i.get("os", False):
                attrs["os"] = i["os"]
            if i.get("manufacturer", False):
                attrs["manufacturer"] = i["manufacturer"]
            if i.get("ipv4", False):
                attrs["ipv4"] = i["ipv4"]
            if i.get("ipv6", False):
                attrs["ipv6"] = i["ipv6"]
            if i.get("seenTime", False):
                attrs["seenTime"] = i["seenTime"]
            if i.get("ssid", False):
                attrs["ssid"] = i["ssid"]
            hass.async_create_task(
                self.async_see(
                    gps=gps_location,
                    mac=mac,
                    source_type=SourceType.ROUTER,
                    gps_accuracy=accuracy,
                    attributes=attrs,
                )
            )
