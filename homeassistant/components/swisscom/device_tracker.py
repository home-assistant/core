"""Support for Swisscom routers (Internet-Box)."""
from __future__ import annotations

from contextlib import suppress
import logging
import json

import requests
import voluptuous as vol

from homeassistant.components.device_tracker import (
    DOMAIN,
    PLATFORM_SCHEMA as PARENT_PLATFORM_SCHEMA,
    DeviceScanner,
)
from homeassistant.const import CONF_HOST, CONF_PASSWORD
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType

_LOGGER = logging.getLogger(__name__)

DEFAULT_IP = "internetbox.swisscom.ch"

PLATFORM_SCHEMA = PARENT_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_HOST, default=DEFAULT_IP): cv.string
    }
)


def get_scanner(hass: HomeAssistant, config: ConfigType) -> DeviceScanner | None:
    """Return the Swisscom device scanner."""
    scanner = SwisscomDeviceScanner(config[DOMAIN])

    return scanner if scanner.success_init else None


class SwisscomDeviceScanner(DeviceScanner):
    """This class queries a router running Swisscom Internet-Box firmware."""

    def __init__(self, config):
        """Initialize the scanner."""
        self.host = config[CONF_HOST]
        self.password = config[CONF_PASSWORD]
        self.last_results = {}

        # Test the router is accessible.
        data = self.get_swisscom_data()
        self.success_init = data is not None

    def scan_devices(self):
        """Scan for new devices and return a list with found device IDs."""
        self._update_info()
        return [client["mac"] for client in self.last_results]

    def get_device_name(self, device):
        """Return the name of the given device or None if we don't know."""
        if not self.last_results:
            return None
        for client in self.last_results:
            if client["mac"] == device:
                return client["host"]
        return None

    def _update_info(self):
        """Ensure the information from the Swisscom router is up to date.

        Return boolean if scanning successful.
        """
        if not self.success_init:
            return False

        _LOGGER.info("Loading data from Swisscom Internet Box")
        if not (data := self.get_swisscom_data()):
            return False

        active_clients = [client for client in data.values() if client["status"]]
        self.last_results = active_clients
        return True

    def swisscom_post_request(self, session, headers, data):
        # Send a POST request to /ws endpoint of the router.
        # Returns None on failure or the response object
        url = f"https://{self.host}/ws"
        _LOGGER.debug(
            f"Send request to {url}:\nheaders={headers} \ndata={data} \ncookies={session.cookies}"
        )
        try:
            response = session.post(url, headers=headers, data=data, timeout=10)
        except (
            requests.exceptions.ConnectionError,
            requests.exceptions.Timeout,
            requests.exceptions.ConnectTimeout,
        ):
            _LOGGER.warning("No response from Swisscom Internet Box")
            return None

        _LOGGER.debug(f"Headers: {response.headers}")
        _LOGGER.debug(f"Response: {response.text}")

        # Check validity
        if response.status_code != 200:
            _LOGGER.warning(f"Response status unexpected: {response.status_code}")
            return None
        # Check status
        if "status" not in response.json():
            _LOGGER.warning("No status in response from Swisscom Internet Box")
            return None
        # Check for errors
        if "errors" in response.json():
            _LOGGER.warning("Errors in response from Swisscom Internet Box:")
            _LOGGER.warning(json.dumps(response.json()["errors"]))
            return None
        return response

    def get_swisscom_data(self):
        # Retrieve data from Swisscom router and return parsed result.
        session = requests.session()

        # Send a request to create a authenticated session 
        headers = {
            "Authorization": "X-Sah-Login", 
            "Content-Type": "application/x-sah-ws-4-call+json"}
        data = (
            """{"service": "sah.Device.Information","method": "createContext","parameters": {"applicationName": "webui","username": "admin","password": \""""
            + self.password
            + """\"}}"""
        )

        _LOGGER.debug("Send session request")
        authentication_response = self.swisscom_post_request(session, headers, data)
        if authentication_response is None:
            return {}

        _LOGGER.debug("Got session response:")
        authentication_data = authentication_response.json()
        _LOGGER.debug(json.dumps(authentication_data))
        # response data should have the following content:
        # {
        #  "status": 0,
        #  "data": {
        #    "contextID": "XXX",
        #    "username": "admin",
        #    "groups": "http,admin"
        #  }
        # }
        if authentication_data["status"] != 0:
            _LOGGER.warn(
                "Unexpected status in response from Swisscom Internet Box during session setup"
            )
            return {}
        if (
            "data" not in authentication_data
            or "contextID" not in authentication_data["data"]
        ):
            _LOGGER.warn(
                "No data/contextID in response from Swisscom Internet Box during session setup"
            )
            return {}

        # extract context ID
        context_id = authentication_data["data"]["contextID"]

        # And it should have a session id in the 'Set-Cookie' header of the response:
        # DEVICEID/sessid=SESSIONID; 
        # Note: there might be multiple cookies that contain '/sessid=' but some have no SESSIONID value. 
        # Assumption is that these try to clear a previous session id first, because the last occurence has the desired value.
        session_cookies = authentication_response.headers["set-cookie"]
        session_cookie_list = session_cookies.split(";")
        # find the last matching the '/sessid=' substring...
        needle = "/sessid="
        matching_cookies = [s for s in session_cookie_list if needle in s]
        if len(matching_cookies) == 0:
            _LOGGER.warn(
                "No matches for session id in response header from Swisscom Internet Box during session setup"
            )
            return {}
        # ... and use the last one...
        matching_cookie = matching_cookies[-1]
        _LOGGER.info(f"Session ID Cookie: {matching_cookie}")
        try:
            match_position = matching_cookie.index(needle)
        except ValueError:
            _LOGGER.warn(
                "No matching session id in response header from Swisscom Internet Box during session setup"
            )
            return {}

        # ... to extract the device id ...
        device_id = matching_cookie[0:match_position:1]
        # ... and the session id
        session_id = matching_cookie[
            match_position + len(needle) : len(matching_cookie) : 1
        ]

        _LOGGER.debug(
            f">> Information from handshake: context_id={context_id} / device_id={device_id} / session_id={session_id}"
        )

        # Now, we can access the router! Send a request to get the devices ...
        # ... containing the required cookies ...
        session.cookies.set(f"{device_id}/sessid", session_id, domain="internetbox.swisscom.ch")
        session.cookies.set(f"swc/deviceID", device_id, domain="internetbox.swisscom.ch")
        session.cookies.set(f"{device_id}/context", context_id, domain="internetbox.swisscom.ch")
        session.cookies.set(f"{device_id}/accept-language", "en-US,en", domain="internetbox.swisscom.ch")
        # ... and headers
        headers = {
            "Authorization": f"X-Sah {context_id}",
            "X-Context": context_id,
            "Content-Type": "application/x-sah-ws-4-call+json",
        }
        # the request wants to get the devices in the LAN
        data = """{"service": "Devices", "method": "get", "parameters": {"expression": "lan and not self and not interface"}, "flags": "no_actions"}"""
        device_response = self.swisscom_post_request(session, headers, data)
        if device_response is None:
            return {}

        # extract the devices
        devices = {}
        for device in device_response.json()["status"]:
            with suppress(KeyError, requests.exceptions.RequestException):
                devices[device["Key"]] = {
                    "ip": device["IPAddress"],
                    "mac": device["PhysAddress"],
                    "host": device["Name"],
                    "status": device["Active"],
                }
        return devices
