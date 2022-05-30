"""
https://coolkit-technologies.github.io/eWeLink-API/#/en/PlatformOverview
"""
import asyncio
import base64
import hashlib
import hmac
import json
import logging
import time
from typing import List

from aiohttp import ClientConnectorError, WSMessage, ClientWebSocketResponse

from .base import XRegistryBase, XDevice, SIGNAL_CONNECTED, SIGNAL_UPDATE

_LOGGER = logging.getLogger(__name__)

RETRY_DELAYS = [15, 60, 5 * 60, 15 * 60, 60 * 60]

# https://coolkit-technologies.github.io/eWeLink-API/#/en/APICenterV2?id=interface-domain-name
API = {
    "cn": "https://cn-apia.coolkit.cn",
    "as": "https://as-apia.coolkit.cc",
    "us": "https://us-apia.coolkit.cc",
    "eu": "https://eu-apia.coolkit.cc",
}
# https://coolkit-technologies.github.io/eWeLink-API/#/en/APICenterV2?id=http-dispatchservice-app
WS = {
    "cn": "https://cn-dispa.coolkit.cn/dispatch/app",
    "as": "https://as-dispa.coolkit.cc/dispatch/app",
    "us": "https://us-dispa.coolkit.cc/dispatch/app",
    "eu": "https://eu-dispa.coolkit.cc/dispatch/app",
}

DATA_ERROR = {
    0: 'online',
    503: 'offline',
    504: 'timeout',
    None: 'unknown'
}

APP = [
    ("oeVkj2lYFGnJu5XUtWisfW4utiN4u9Mq", "6Nz4n0xA8s8qdxQf2GqurZj2Fs55FUvM"),
    ("R8Oq3y0eSZSYdKccHlrQzT1ACCOUT9Gv", "1ve5Qk9GXfUhKAn1svnKwpAlxXkMarru")
]


class AuthError(Exception):
    pass


class ResponseWaiter:
    """Class wait right sequences in response messages."""
    _waiters = {}

    def _set_response(self, sequence: str, error: int) -> bool:
        if sequence not in self._waiters:
            return False
        # sometimes the error doesn't exists
        result = DATA_ERROR[error] if error in DATA_ERROR else f"E#{error}"
        self._waiters[sequence].set_result(result)
        return True

    async def _wait_response(self, sequence: str, timeout: int):
        self._waiters[sequence] = asyncio.get_event_loop().create_future()

        try:
            # limit future wait time
            await asyncio.wait_for(self._waiters[sequence], timeout)
        except asyncio.TimeoutError:
            # remove future from waiters, in very rare cases, we can send two
            # commands with the same sequence
            self._waiters.pop(sequence, None)
            return 'timeout'

        # remove future from waiters and return result
        return self._waiters.pop(sequence).result()


class XRegistryCloud(ResponseWaiter, XRegistryBase):
    auth: dict = None
    devices: dict = None
    last_ts = 0
    online = None
    region = "eu"

    task: asyncio.Task = None
    ws: ClientWebSocketResponse = None

    @property
    def host(self) -> str:
        return API[self.region]

    @property
    def ws_host(self) -> str:
        return WS[self.region]

    @property
    def headers(self) -> dict:
        return {"Authorization": "Bearer " + self.auth["at"]}

    @property
    def token(self) -> str:
        return self.region + ":" + self.auth["at"]

    async def login(self, username: str, password: str, app=0) -> bool:
        if username == "token":
            self.region, token = password.split(":")
            return await self.login_token(token, 1)

        # https://coolkit-technologies.github.io/eWeLink-API/#/en/DeveloperGuideV2
        payload = {
            "password": password,
            "countryCode": "+86",
        }
        if "@" in username:
            payload["email"] = username
        elif username.startswith("+"):
            payload["phoneNumber"] = username
        else:
            payload["phoneNumber"] = "+" + username

        appid, appsecret = APP[app]

        hex_dig = hmac.new(
            appsecret.encode(), json.dumps(payload).encode(), hashlib.sha256
        ).digest()

        headers = {
            "Authorization": "Sign " + base64.b64encode(hex_dig).decode(),
            "X-CK-Appid": appid,
        }
        r = await self.session.post(
            self.host + "/v2/user/login", json=payload, headers=headers,
            timeout=30
        )
        resp = await r.json()

        # wrong default region
        if resp["error"] == 10004:
            self.region = resp["data"]["region"]
            r = await self.session.post(
                self.host + "/v2/user/login", json=payload, headers=headers,
                timeout=30
            )
            resp = await r.json()

        if resp["error"] != 0:
            raise AuthError(resp["msg"])

        self.auth = resp["data"]
        self.auth["appid"] = appid

        return True

    async def login_token(self, token: str, app: int = 0) -> bool:
        appid = APP[app][0]
        headers = {"Authorization": "Bearer " + token, "X-CK-Appid": appid}
        r = await self.session.get(
            self.host + "/v2/user/profile", headers=headers, timeout=30
        )
        resp = await r.json()
        if resp["error"] != 0:
            raise AuthError(resp["msg"])

        self.auth = resp["data"]
        self.auth["at"] = token
        self.auth["appid"] = appid

        return True

    async def get_homes(self) -> dict:
        r = await self.session.get(
            self.host + "/v2/family", headers=self.headers, timeout=30
        )
        resp = await r.json()
        return {i["id"]: i["name"] for i in resp["data"]["familyList"]}

    async def get_devices(self, homes: list = None) -> List[dict]:
        devices = []
        for home in homes or [None]:
            r = await self.session.get(
                self.host + "/v2/device/thing",
                headers=self.headers, timeout=30,
                params={"num": 0, "familyid": home} if home else {"num": 0}
            )
            resp = await r.json()
            if resp["error"] != 0:
                raise Exception(resp["msg"])
            # item type: 1 - user device, 2 - shared device, 3 - user group,
            # 5 - share device (home)
            devices += [
                i["itemData"] for i in resp["data"]["thingList"]
                if i["itemType"] != 3  # skip groups
            ]
        return devices

    async def send(
            self, device: XDevice, params: dict = None, sequence: str = None,
            timeout: int = 5
    ):
        """With params - send new state to device, without - request device
        state. With zero timeout - won't wait response.
        """
        log = f"{device['deviceid']} => Cloud4 | "
        if params:
            log += f"{params} | "

        # protect cloud from DDoS (it can break connection)
        while time.time() - self.last_ts < 0.1:
            log += "DDoS | "
            await asyncio.sleep(0.1)
        self.last_ts = time.time()

        if sequence is None:
            sequence = self.sequence()
        log += sequence

        # https://coolkit-technologies.github.io/eWeLink-API/#/en/APICenterV2?id=websocket-update-device-status
        payload = {
            "action": "update" if params else "query",
            # we need to use device apikey bacause device may be shared from
            # another account
            "apikey": device["apikey"],
            "selfApikey": self.auth["user"]["apikey"],
            "deviceid": device['deviceid'],
            "params": params or [],
            "userAgent": "app",
            "sequence": sequence,
        }

        _LOGGER.debug(log)
        try:
            await self.ws.send_json(payload)

            if timeout:
                # wait for response with same sequence
                return await self._wait_response(sequence, timeout)
        except ConnectionResetError:
            return 'offline'
        except Exception as e:
            _LOGGER.error(log, exc_info=e)
            return 'E#???'

    def start(self):
        self.task = asyncio.create_task(self.run_forever())

    async def stop(self):
        if self.task:
            self.task.cancel()

        self.set_online(False)

    def set_online(self, value: bool):
        _LOGGER.debug(f"CLOUD {self.online} => {value}")
        if self.online == value:
            return
        self.online = value
        self.dispatcher_send(SIGNAL_CONNECTED)

    async def run_forever(self):
        fails = 0

        while not self.session.closed:
            if not await self.connect():
                self.set_online(False)

                delay = RETRY_DELAYS[fails]
                _LOGGER.debug(f"Cloud connection retrying in {delay} seconds")
                if fails + 1 < len(RETRY_DELAYS):
                    fails += 1
                await asyncio.sleep(delay)
                continue

            fails = 0

            self.set_online(True)

            try:
                msg: WSMessage
                async for msg in self.ws:
                    resp = json.loads(msg.data)
                    await self._process_ws_msg(resp)
            except Exception as e:
                _LOGGER.warning("Cloud processing error", exc_info=e)

    async def connect(self) -> bool:
        try:
            # https://coolkit-technologies.github.io/eWeLink-API/#/en/APICenterV2?id=http-dispatchservice-app
            r = await self.session.get(self.ws_host, headers=self.headers)
            resp = await r.json()

            # we can use IP, but using domain because security
            self.ws = await self.session.ws_connect(
                f"wss://{resp['domain']}:{resp['port']}/api/ws", heartbeat=90
            )

            # https://coolkit-technologies.github.io/eWeLink-API/#/en/APICenterV2?id=websocket-handshake
            ts = time.time()
            payload = {
                "action": "userOnline",
                "at": self.auth["at"],
                "apikey": self.auth["user"]["apikey"],
                "appid": self.auth["appid"],
                "nonce": str(int(ts / 100)),
                "ts": int(ts),
                "userAgent": "app",
                "sequence": str(int(ts * 1000)),
                "version": 8,
            }
            await self.ws.send_json(payload)

            resp = await self.ws.receive_json()
            if resp["error"] != 0:
                raise Exception(resp)

            return True

        except ClientConnectorError as e:
            _LOGGER.warning(f"Cloud WS Connection error: {e}")

        except Exception as e:
            _LOGGER.error(f"Cloud WS exception", exc_info=e)

        return False

    async def _process_ws_msg(self, data: dict):
        if "action" not in data:
            # response on our command
            self._set_response(data["sequence"], data["error"])

            # with params response on query, without - on update
            if "params" in data:
                self.dispatcher_send(SIGNAL_UPDATE, data)
            elif "config" in data:
                data["params"] = data.pop("config")
                self.dispatcher_send(SIGNAL_UPDATE, data)
            elif data["error"] != 0:
                _LOGGER.warning(f"Cloud ERROR: {data}")

        elif data["action"] == "update":
            # new state from device
            self.dispatcher_send(SIGNAL_UPDATE, data)

        elif data["action"] == "sysmsg":
            # changed device online status
            self.dispatcher_send(SIGNAL_UPDATE, data)

        elif data["action"] == "reportSubDevice":
            # nothing useful: https://github.com/AlexxIT/SonoffLAN/issues/767
            pass

        else:
            _LOGGER.warning(f"UNKNOWN cloud msg: {data}")
