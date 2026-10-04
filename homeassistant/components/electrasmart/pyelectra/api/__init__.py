"""Electra Smart API client (vendored from upstream ``pyElectra``).

See ``NOTICE.md`` in this package for provenance and the divergences from
upstream.
"""

from asyncio import create_task
from datetime import datetime
from json import JSONDecodeError
from logging import getLogger
from typing import Any

from aiohttp import ClientError, ClientSession

from ..device import ElectraAirConditioner
from .const import (
    DELAY_BETWEEM_SID_REQUESTS,
    SID_EXPIRATION,
    STATUS_SUCCESS,
    Attributes,
)

logger = getLogger(__name__)


class ElectraApiError(Exception):
    """Raised on communication problems with the Electra API."""


class ElectraAPI:
    """Client for the Electra smart AC cloud API."""

    def __init__(
        self,
        websession: ClientSession,
        imei: str | None = None,
        token: str | None = None,
    ) -> None:
        """Initialize the API client."""
        self._base_url = "https://app.ecpiot.co.il/mobile/mobilecommand"
        self._sid: str | None = None
        self._imei = imei
        self._token = token
        self._sid_expiration = 0
        self._last_sid_request_ts = 0
        self._session = websession
        self._phone_number: str | None = None
        self._devices: list[ElectraAirConditioner] = []

        logger.debug("Initialized Electra API object")

    @property
    def devices(self) -> list[ElectraAirConditioner]:
        """Return the discovered devices."""
        return self._devices

    async def _send_request(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Send a request to the Electra API."""
        try:
            resp = await self._session.post(
                url=self._base_url,
                json=payload,
                headers={"user-agent": "Electra Client"},
            )
            json_resp: dict[str, Any] = await resp.json(content_type=None)
        except TimeoutError as ex:
            raise ElectraApiError(
                f"Failed to communicate with Electra API due to time out: ({ex!s})"
            ) from ex
        except ClientError as ex:
            raise ElectraApiError(
                f"Failed to communicate with Electra API due to ClientError: ({ex!s})"
            ) from ex
        except JSONDecodeError as ex:
            raise ElectraApiError(
                f"Recieved invalid response from Electra API: {ex!s}"
            ) from ex

        return json_resp

    async def generate_new_token(self, phone_number: str, imei: str) -> dict[str, Any]:
        """Request a one-time password to be sent to the phone."""
        payload = {
            "pvdid": 1,
            "id": 99,
            "cmd": "SEND_OTP",
            "data": {"imei": imei, "phone": phone_number},
        }

        return await self._send_request(payload=payload)

    async def validate_one_time_password(
        self, otp: str, imei: str, phone_number: str
    ) -> dict[str, Any]:
        """Validate the one-time password and retrieve a token."""
        payload = {
            "pvdid": 1,
            "id": 99,
            "cmd": "CHECK_OTP",
            "data": {
                "imei": imei,
                "phone": phone_number,
                "code": otp,
                "os": "android",
                "osver": "M4B30Z",
            },
        }

        return await self._send_request(payload=payload)

    def _sid_expired(self) -> bool:
        """Return True if the cached session id has expired."""
        current_time = int(datetime.now().timestamp())
        refresh_in = self._sid_expiration - current_time
        if refresh_in > 0:
            logger.debug("Should refresh in %s minutes", round(refresh_in / 60))

        if current_time < self._sid_expiration:
            return False
        self._sid = None
        return True

    async def _get_sid(self, force: bool = False) -> None:
        """Acquire a session id, reusing the cached one when still valid."""
        current_ts = int(datetime.now().timestamp())
        if not force and not self._sid_expired():
            logger.debug("Found valid sid (%s) in cache, using it", self._sid)
            return

        if self._last_sid_request_ts and current_ts < (
            self._last_sid_request_ts + DELAY_BETWEEM_SID_REQUESTS
        ):
            logger.debug(
                "Session ID was requested less than 5 minutes ago! waiting in "
                'order to prevent "intruder lockdown"...'
            )
            return

        payload = {
            "pvdid": 1,
            "id": 99,
            "cmd": "VALIDATE_TOKEN",
            "data": {
                "imei": self._imei,
                "token": self._token,
                "os": "android",
                "osver": "M4B30Z",
            },
        }

        resp = await self._send_request(payload=payload)

        if resp is None:
            raise ElectraApiError("Failed to retrieve sid")
        if not resp[Attributes.DATA][Attributes.SID]:
            raise ElectraApiError(
                "Failed to retrieve SID due to %s",
                resp[Attributes.DATA][Attributes.DESC],
            )
        self._sid = resp[Attributes.DATA][Attributes.SID]
        self._sid_expiration = current_ts + SID_EXPIRATION
        self._last_sid_request_ts = current_ts
        logger.debug("Successfully acquired sid: %s", self._sid)

    async def fetch_devices(self) -> None:
        """Fetch devices and their current operation state."""
        fetch_state_tasks = []
        logger.debug("About to Get Electra AC devices")
        await self._get_sid()

        payload = {"pvdid": 1, "id": 99, "cmd": "GET_DEVICES", "sid": self._sid}

        ac_list: list[ElectraAirConditioner] = []
        resp = await self._send_request(payload=payload)
        if resp[Attributes.STATUS] == STATUS_SUCCESS:
            for ac in resp[Attributes.DATA][Attributes.DEVICES]:
                if ac["deviceTypeName"] == "A/C":
                    electra_ac: ElectraAirConditioner = ElectraAirConditioner(ac)
                    logger.debug("Discovered A/C device %s", electra_ac.name)
                    ac_list.append(electra_ac)
                    fetch_state_tasks.append(
                        create_task(self.get_last_telemtry(electra_ac))
                    )
                else:
                    logger.debug("Discovered non AC device %s", ac)

            for task in fetch_state_tasks:
                await task

            for ac in ac_list:
                ac.update_features()

            self._devices = ac_list
        else:
            raise ElectraApiError("Failed to fetch devices %s", resp)

    async def get_last_telemtry(self, ac: ElectraAirConditioner) -> None:
        """Fetch the current operation state for a device."""
        logger.debug("Getting AC %s state", ac.name)

        await self._get_sid()

        payload = {
            "pvdid": 1,
            "id": 99,
            "cmd": "GET_LAST_TELEMETRY",
            "sid": self._sid,
            "data": {"id": ac.id, "commandName": "OPER,DIAG_L2"},
        }

        resp = await self._send_request(payload=payload)
        if resp[Attributes.STATUS] != STATUS_SUCCESS:
            raise ElectraApiError(f"Failed to get AC operation state: {resp}")
        ac.update_operation_states(resp[Attributes.DATA])

    async def set_state(self, device: ElectraAirConditioner) -> dict[str, Any]:
        """Send the current operation state for a device to the API."""
        json_command = device.get_operation_state()
        await self._get_sid()

        payload = {
            "pvdid": 1,
            "id": 99,
            "cmd": "SEND_COMMAND",
            "sid": self._sid,
            "data": {"id": device.id, "commandJson": json_command},
        }

        return await self._send_request(payload=payload)
