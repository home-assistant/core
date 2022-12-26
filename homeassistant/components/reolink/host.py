"""This component encapsulates the NVR/camera API and subscription."""
from __future__ import annotations

import asyncio
import logging

import aiohttp
from reolink_ip.api import Host
from reolink_ip.exceptions import (
    ApiError,
    CredentialsInvalidError,
    InvalidContentTypeError,
)

from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import format_mac

from .const import CONF_PROTOCOL, CONF_USE_HTTPS, DEFAULT_PROTOCOL, DEFAULT_TIMEOUT

_LOGGER = logging.getLogger(__name__)


class ReolinkHost:
    """The implementation of the Reolink Host class."""

    def __init__(
        self,
        hass: HomeAssistant,
        config: dict,
        options: dict,
    ) -> None:
        """Initialize Reolink Host. Could be either NVR, or Camera."""
        self._hass: HomeAssistant = hass

        self._clientsession: aiohttp.ClientSession | None = None
        self._unique_id: str | None = None

        cur_protocol = (
            DEFAULT_PROTOCOL if CONF_PROTOCOL not in options else options[CONF_PROTOCOL]
        )

        self._api = Host(
            config[CONF_HOST],
            config[CONF_USERNAME],
            config[CONF_PASSWORD],
            port=config.get(CONF_PORT),
            use_https=config.get(CONF_USE_HTTPS),
            protocol=cur_protocol,
            timeout=DEFAULT_TIMEOUT,
        )

    @property
    def unique_id(self):
        """Create the unique ID, base for all entities."""
        return self._unique_id

    @property
    def api(self):
        """Return the API object."""
        return self._api

    async def async_init(self) -> bool:
        """Connect to Reolink host."""
        self._api.expire_session()

        if not await self._api.get_host_data():
            return False

        if self._api.mac_address is None:
            return False

        enable_onvif = None
        enable_rtmp = None
        enable_rtsp = None

        if not self._api.onvif_enabled:
            _LOGGER.debug(
                "ONVIF is disabled on %s, trying to enable it", self._api.nvr_name
            )
            enable_onvif = True

        if not self._api.rtmp_enabled and self._api.protocol == "rtmp":
            _LOGGER.debug(
                "RTMP is disabled on %s, trying to enable it", self._api.nvr_name
            )
            enable_rtmp = True
        elif not self._api.rtsp_enabled and self._api.protocol == "rtsp":
            _LOGGER.debug(
                "RTSP is disabled on %s, trying to enable it", self._api.nvr_name
            )
            enable_rtsp = True

        if enable_onvif or enable_rtmp or enable_rtsp:
            if not await self._api.set_net_port(
                enable_onvif=enable_onvif,
                enable_rtmp=enable_rtmp,
                enable_rtsp=enable_rtsp,
            ):
                if enable_onvif:
                    _LOGGER.error(
                        "Unable to switch on ONVIF on %s. You need it to be ON to receive notifications",
                        self._api.nvr_name,
                    )

                if enable_rtmp:
                    _LOGGER.error(
                        "Unable to switch on RTMP on %s. You need it to be ON",
                        self._api.nvr_name,
                    )
                elif enable_rtsp:
                    _LOGGER.error(
                        "Unable to switch on RTSP on %s. You need it to be ON",
                        self._api.nvr_name,
                    )

        if self._unique_id is None:
            self._unique_id = format_mac(self._api.mac_address)

        return True

    async def update_states(self) -> bool:
        """Call the API of the camera device to update the states."""
        return await self._api.get_states()

    async def disconnect(self):
        """Disconnect from the API, so the connection will be released."""
        await self._api.unsubscribe_all()

        try:
            await self._api.logout()
        except aiohttp.ClientConnectorError as err:
            _LOGGER.error(
                "Reolink connection error while logging out for host %s:%s: %s",
                self._api.host,
                self._api.port,
                str(err),
            )
        except asyncio.TimeoutError:
            _LOGGER.error(
                "Reolink connection timeout while logging out for host %s:%s",
                self._api.host,
                self._api.port,
            )
        except ApiError as err:
            _LOGGER.error(
                "Reolink API error while logging out for host %s:%s: %s",
                self._api.host,
                self._api.port,
                str(err),
            )
        except CredentialsInvalidError:
            _LOGGER.error(
                "Reolink credentials error while logging out for host %s:%s",
                self._api.host,
                self._api.port,
            )
        except InvalidContentTypeError as err:
            _LOGGER.error(
                "Reolink content type error while logging out for host %s:%s: %s",
                self._api.host,
                self._api.port,
                str(err),
            )

    async def stop(self, event=None):
        """Disconnect the API."""
        await self.disconnect()
