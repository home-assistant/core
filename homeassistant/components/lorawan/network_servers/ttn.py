"""Parser for The Things Network (V3) network server."""
import base64
import logging

import aiohttp

from ..helpers.exceptions import CannotConnect, InvalidAuth
from ..models import Device, Uplink

_LOGGER = logging.getLogger(__name__)

USER_AGENT = "Home Assistant LoRaWAN integration"


class TTN:
    """Network server class for TTN."""

    def __init__(self, api_key: str, application: str, url: str) -> None:
        """Construct the TTN object.

        :param api_key: TTN application API Key (rights: View devices in application, Read application traffic, Write downlink application traffic)"
        :param application: TTN application ID
        :param url: TTN URL
        """
        self._application = application
        self._url = url
        self._headers = {
            "Authorization": f"Bearer {api_key}",
            "Accept": "application/json",
            "User-Agent": USER_AGENT,
        }

        if self._url[-1] != "/":
            self._url += "/"

    @staticmethod
    def normalize_uplink(uplink: dict) -> Uplink:
        """Parse TTN uplink json to internal modem."""
        return Uplink(
            payload=base64.b64decode(uplink["uplink_message"]["frm_payload"]),
            f_port=uplink["uplink_message"]["f_port"],
        )

    async def list_device_euis(self, session: aiohttp.ClientSession) -> list[Device]:
        """List device euis of the TTN application.

        A = {
            "end_devices": [
                {
                    "ids": {
                        "device_id": "test-device",
                        "application_ids": {"application_id": "hass-test"},
                        "dev_eui": "FEEDABCD00000002",
                        "join_eui": "FEEDABCD00000001",
                    },
                    "created_at": "2023-07-24T11:35:49.598651Z",
                    "updated_at": "2023-07-24T11:35:49.598651Z",
                }
            ]
        }.
        """
        async with session.request(
            "GET",
            f"{self._url}api/v3/applications/{self._application}/devices",
            headers=self._headers,
        ) as res:
            if res.status == 401:
                raise InvalidAuth
            if res.status < 200 or res.status >= 300:
                raise CannotConnect(res.status)
            devices = (await res.json())["end_devices"]
            # OTODO Handle pages
            return [
                Device(device["ids"]["dev_eui"], device["ids"]["device_id"])
                for device in devices
            ]
