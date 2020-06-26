"""Support for Sky Hub."""
import logging
import re
import asyncio
import aiohttp

import voluptuous as vol

from homeassistant.helpers.aiohttp_client import async_get_clientsession

from homeassistant.components.device_tracker import (
    DOMAIN,
    PLATFORM_SCHEMA,
    DeviceScanner,
)
from homeassistant.const import CONF_HOST, HTTP_OK
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)
_MAC_REGEX = re.compile(r"(([0-9A-Fa-f]{1,2}\:){5}[0-9A-Fa-f]{1,2})")
_INFO = logging.INFO
_ERROR = logging.ERROR
_CONNECTION_ERROR = "connectionerror"
_DATA_ERROR = "dataerror"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({vol.Optional(CONF_HOST): cv.string})


async def async_get_scanner(hass, config):
    """Return a Sky Hub scanner if successful."""
    scanner = SkyHubDeviceScanner(config[DOMAIN])
    await scanner.async_connect(hass)
    return scanner if scanner.success_init else None


class SkyHubDeviceScanner(DeviceScanner):
    """This class queries a Sky Hub router."""

    def __init__(self, config):
        """Initialise the scanner."""
        self._connection_failed = False
        self._dataparse_failed = False
        self._log_message("Initialising Sky Hub", level=_INFO)
        self.host = config.get(CONF_HOST, "192.168.1.254")
        self.last_results = {}
        self.url = f"http://{self.host}/"
        self.success_init = False

    async def async_connect(self, hass):
        """Test the router is accessible."""
        data = await self._async_get_skyhub_data(self.url, hass)
        self.success_init = data is not None

    async def async_scan_devices(self):
        """Scan for new devices and return a list with found device IDs."""
        await self._async_update_info()

        return (device for device in self.last_results)

    async def async_get_device_name(self, device):
        """Return the name of the given device or None if we don't know."""
        # If not initialised and not already scanned and not found.
        if device not in self.last_results:
            await self._async_update_info()

            if not self.last_results:
                return None

        return self.last_results.get(device)

    async def _async_update_info(self):
        """Ensure the information from the Sky Hub is up to date.

        Return boolean if scanning successful.
        """
        if not self.success_init:
            return False

        self._log_message("Scanning", level=_INFO)

        data = await self._async_get_skyhub_data(self.url)

        if not data:
            return False

        self.last_results = data

        return True

    async def _async_get_skyhub_data(self, url, hass=None):
        """Retrieve data from Sky Hub and return parsed result."""
        websession = async_get_clientsession(hass if hass else self.hass)
        parseddata = None
        try:
            async with getattr(websession, "get")(url,) as response:
                if response.status == HTTP_OK:
                    if self._connection_failed:
                        self._log_message(
                            "Connection restored to router",
                            unset_error=True,
                            level=_ERROR,
                            error_type=_CONNECTION_ERROR,
                        )
                    responsedata = await response.text()
                    parseddata = _parse_skyhub_response(responsedata)
                    if self._dataparse_failed:
                        self._log_message(
                            "Response data from Sky Hub corrected",
                            unset_error=True,
                            level=_ERROR,
                            error_type=_DATA_ERROR,
                        )
                    return parseddata

        except asyncio.TimeoutError:
            self._log_message(
                "Connection to the router timed out",
                level=_ERROR,
                error_type=_CONNECTION_ERROR,
            )
            return
        except aiohttp.client_exceptions.ClientConnectorError as err:
            self._log_message(
                f"Connection to the router failed: {err}",
                level=_ERROR,
                error_type=_CONNECTION_ERROR,
            )
            return
        except (OSError, RuntimeError) as err:
            if not self.success_init:
                message = f"Error parsing data at initialisation for {self.host}, is this a Sky Router?"
            else:
                message = f"Invalid response from Sky Hub: {err}"
            self._log_message(
                message, level=_ERROR, error_type=_DATA_ERROR,
            )
            return

    def _log_message(
        self, log_message, unset_error=False, level=_ERROR, error_type=None
    ):
        if level == _INFO:
            _LOGGER.info(log_message)
            return
        if level == _ERROR:
            if error_type == _CONNECTION_ERROR:
                if self._connection_failed and not unset_error:
                    _LOGGER.debug(log_message)
                    return
                if unset_error:
                    self._connection_failed = False
                else:
                    self._connection_failed = True
            if error_type == _DATA_ERROR:
                if self._dataparse_failed and not unset_error:
                    _LOGGER.debug(log_message)
                    return
                if unset_error:
                    self._dataparse_failed = False
                else:
                    self._dataparse_failed = True
            _LOGGER.error(log_message)
        return


def _parse_skyhub_response(data_str):
    """Parse the Sky Hub data format."""
    pattmatch = re.search("attach_dev = '(.*)'", data_str)
    if pattmatch is None:
        raise OSError(
            "Error: Impossible to fetch data from Sky Hub. Try to reboot the router."
        )
    patt = pattmatch.group(1)

    dev = [patt1.split(",") for patt1 in patt.split("<lf>")]

    devices = {}
    for dvc in dev:
        if _MAC_REGEX.match(dvc[1]):
            devices[dvc[1]] = dvc[0]
        else:
            raise RuntimeError(f"Error: MAC address {dvc[1]} not in correct format.")

    return devices
