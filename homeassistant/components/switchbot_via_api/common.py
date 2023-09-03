"""Tools to query the SwitchBot API."""
import base64
from dataclasses import dataclass
from enum import Enum
import hashlib
import hmac
import logging
import time
import uuid

from aiohttp import ClientSession

from homeassistant.auth.providers.homeassistant import InvalidAuth

from .const import API_HOST

_LOGGER = logging.getLogger(__name__)
OBSERVED_DEVICE_TYPES = ["Remote", "Plug", "Plug Mini (US)", "Plug Mini (JP)"]
NON_OBSERVED_REMOTE_TYPES = ["Others"]


class CannotConnect(Exception):
    """Cannot connect to the SwitchBot API."""


@dataclass
class Device:
    """Device."""

    device_id: str
    device_name: str
    device_type: str
    hub_device_id: str

    def __init__(self, **kwargs) -> None:
        """Initialize."""
        self.device_id = kwargs["deviceId"]
        self.device_name = kwargs["deviceName"]
        self.device_type = kwargs["deviceType"]
        self.hub_device_id = kwargs["hubDeviceId"]


@dataclass
class Remote:
    """Remote device."""

    device_id: str
    device_name: str
    device_type: str
    hub_device_id: str

    def __init__(self, **kwargs) -> None:
        """Initialize."""
        self.device_id = kwargs["deviceId"]
        self.device_name = kwargs["deviceName"]
        self.device_type = kwargs["remoteType"]
        self.hub_device_id = kwargs["hubDeviceId"]


class PowerState(Enum):
    """Power state."""

    ON = "on"
    OFF = "off"


class CommonCommands(Enum):
    """Common commands."""

    ON = "turnOn"
    OFF = "turnOff"


class OthersCommands(Enum):
    """Others commands."""

    CUSTOMIZE = "customize"  # Command {user-defined button name}


class AirConditionerCommands(Enum):
    """xtending inherited Enum class "CommonCommands"pylint(invalid-enum-extensAir conditioner commands."""

    SET_ALL = "setAll"  # parameter: {temperature},{mode},{fan speed},{power state}


class TVCommands(Enum):
    """TV commands."""

    SET_CHANNEL = "SetChannel"
    VOLUME_ADD = "volumeAdd"
    VOLUME_SUB = "volumeSub"
    CHANNEL_ADD = "channelAdd"
    CHANNEL_SUB = "channelSub"


class DVDCommands(Enum):
    """DVD commands."""

    SET_MUTE = "setMute"
    FAST_FORWARD = "FastForward"
    REWIND = "Rewind"
    NEXT = "Next"
    PREVIOUS = "Previous"
    PAUSE = "Pause"
    PLAY = "Play"
    STOP = "Stop"


class SpeakerCommands(Enum):
    """Speaker commands."""

    VOLUME_ADD = "volumeAdd"
    VOLUME_SUB = "volumeSub"


class FanCommands(Enum):
    """Fan commands."""

    SWING = "swing"
    TIMER = "timer"
    LOW_SPEED = "lowSpeed"
    MIDDLE_SPEED = "middleSpeed"
    HIGH_SPEED = "highSpeed"


class LightCommands(Enum):
    """Light commands."""

    BRIGHTNESS_UP = "brightnessUp"
    BRIGHTNESS_DOWN = "brightnessDown"


class SwitchBotAPI:
    """SwitchBot API."""

    def __init__(self, token: str, secret: str) -> None:
        """Initialize."""
        self.token = token
        self.secret = secret

    def make_headers(self, token: str, secret: str):
        """Make headers."""
        nonce = uuid.uuid4()
        timestamp = int(round(time.time() * 1000))
        string_to_sign = bytes(f"{token}{timestamp}{nonce}", "utf-8")
        secret_bytes = bytes(secret, "utf-8")

        sign = base64.b64encode(
            hmac.new(
                secret_bytes, msg=string_to_sign, digestmod=hashlib.sha256
            ).digest()
        )

        return {
            "Authorization": token,
            "Content-Type": "application/json",
            "charset": "utf8",
            "t": str(timestamp),
            "sign": str(sign, "utf-8"),
            "nonce": str(nonce),
        }

    async def _request_device(self, path: str = "", callback: str = "get", json=None):
        async with ClientSession() as session:
            async with getattr(session, callback)(
                f"{API_HOST}/v1.1/devices/{path}",
                headers=self.make_headers(self.token, self.secret),
                json=json,
            ) as response:
                if response.status == 403:
                    raise InvalidAuth()
                body = await response.json()
                if response.status >= 400 or body.get("statusCode") != 100:
                    _LOGGER.error("Error %s: %s", response.status, body)
                    raise CannotConnect()
                return body.get("body")

    async def list_devices(self):
        """List devices."""
        body = await self._request_device("")
        _LOGGER.debug("Devices: %s", body)
        devices = [
            Device(**device)
            for device in body.get("deviceList")
            if device.get("deviceType") in OBSERVED_DEVICE_TYPES
        ]
        remotes = [
            Remote(**remote)
            for remote in body.get("infraredRemoteList")
            if remote.get("remoteType") not in NON_OBSERVED_REMOTE_TYPES
        ]
        return [*devices, *remotes]

    async def get_status(self, device_id: str):
        """No status for IR devices."""
        body = await self._request_device(f"{device_id}/status")
        return body

    async def send_command(
        self,
        device_id: str,
        command: CommonCommands,
        command_type: str = "command",
        parameters: dict | str = "default",
    ):
        """Send command to device.

        Args:
            device_id (str): The ID of the device.
            command (CommonCommands): The command to be sent.
            command_type (str, optional): The type of the command. Defaults to "command".
            parameters (dict | str, optional): The parameters for the command. Defaults to "default".

        Example JSON:
            {
                "commandType": "customize",
                "command": "ボタン", // the name of the customized button
                "parameter": "default"
            }
        """
        json = {
            "commandType": command_type,
            "command": command.value,
            "parameter": parameters,
        }
        await self._request_device(f"{device_id}/commands", callback="post", json=json)
