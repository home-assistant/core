"""http_device."""
from __future__ import annotations

import asyncio
from hashlib import md5
import json
import logging
import random
import string
import time

LOGGER = logging.getLogger(__name__)
from typing import Union

from aiohttp import ClientSession

from .enums import Namespace
from .util import BaseDictPayload


class HttpDeviceInfo(BaseDictPayload):
    """Base class."""

    def __init__(
        self,
        uuid: str,
        dev_name: str,
        device_type: str,
        dev_soft_ware: str,
        dev_hard_ware: str,
        ip: str,
        port: str,
        mac: str,
        sub_type: str,
        channels: list[int],
        *args,
        **kwargs,
    ) -> None:
        """Create a HttpDeviceInfo."""
        super().__init__(*args, **kwargs)

        self.uuid = uuid
        self.dev_name = dev_name
        self.device_type = device_type
        self.fmware_version = dev_soft_ware
        self.hdware_version = dev_hard_ware
        self.inner_ip = ip
        self.port = port
        self.mac = mac
        self.sub_type = sub_type
        self.channels = channels

    def __str__(self) -> str:
        """Returns a string."""
        basic_info = f"{self.dev_name} ({self.device_type}, HW {self.hdware_version}, FW {self.fmware_version}, Uuid {self.uuid},channels {self.channels} )"
        return basic_info

    async def async_execute_cmd(
        self,
        device_uuid: str,
        method: str,
        namespace: Union[Namespace, str],
        payload: dict,
        timeout: int = 20,
    ):
        """async_execute_cmd."""
        message, message_id = self._build_mqtt_message(
            method, namespace, payload, device_uuid
        )
        if message_id is None:
            return None
        try:
            async with ClientSession() as session, session.post(
                f"http://{self.inner_ip}/config",
                json=json.loads(message.decode()),
                timeout=timeout,
            ) as response:
                data = await response.json()
                if data is not None:
                    header = data.get("header", {})
                    messageId = header.get("messageId")
                    ack_method = header.get("method")
                    if messageId == message_id and ack_method == method + "ACK":
                        return data
                return None

        except asyncio.TimeoutError:
            LOGGER.warning("http TimeoutError,namespace:%s", namespace)
            return None
        except Exception as e:
            LOGGER.warning("http err: %s", e)
            return None

    def _build_mqtt_message(
        self,
        method: str,
        namespace: Union[Namespace, str],
        payload: dict,
        destination_device_uuid: str,
    ):
        # Generate a random 16 byte string
        randomstring = "".join(
            random.SystemRandom().choice(string.ascii_uppercase + string.digits)
            for _ in range(16)
        )

        userkey = ""

        # Hash it as md5
        md5_hash = md5()
        md5_hash.update(randomstring.encode("utf8"))
        messageId = md5_hash.hexdigest().lower()
        timestamp = int(round(time.time()))

        # Hash the messageId, the key and the timestamp
        md5_hash = md5()
        strtohash = f"{messageId}{userkey}{timestamp}"
        md5_hash.update(strtohash.encode("utf8"))
        signature = md5_hash.hexdigest().lower()

        if not isinstance(namespace, Namespace) and not isinstance(namespace, str):
            LOGGER.debug(
                "Namespace parameter：%s must be a Namespace enum or a string.",
                namespace,
            )
            return
        namespace_val = (
            namespace.value if isinstance(namespace, Namespace) else namespace
        )

        data = {
            "header": {
                "from": f"/app/{randomstring}/subscribe",
                "messageId": messageId,
                "method": method,
                "namespace": namespace_val,
                "payloadVersion": 1,
                "sign": signature,
                "timestamp": timestamp,
                "triggerSrc": "HA",
                "uuid": destination_device_uuid,
            },
            "payload": payload,
        }

        strdata = json.dumps(data, separators=(",", ":"))
        return strdata.encode("utf-8"), messageId
