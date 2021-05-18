"""
https://coolkit-technologies.github.io/apiDocs/#/en/APICenter
"""
import asyncio
import base64
import hashlib
import hmac
import json
import logging
import time
from typing import Optional, Callable, List

from aiohttp import ClientSession, WSMsgType, ClientConnectorError, \
    WSMessage, ClientWebSocketResponse
from homeassistant.const import ATTR_BATTERY_LEVEL

_LOGGER = logging.getLogger(__name__)

RETRY_DELAYS = [0, 15, 60, 5 * 60, 15 * 60, 60 * 60]
FAST_DELAY = RETRY_DELAYS.index(5 * 60)
DATA_ERROR = {
    0: 'online',
    503: 'offline',
    504: 'timeout',
    None: 'unknown'
}

CLOUD_ERROR = (
    "Cloud mode cannot work simultaneously with two copies of component. "
    "Read more: https://github.com/AlexxIT/SonoffLAN#config-examples")


def fix_attrs(deviceid: str, state: dict):
    """
    - Sonoff TH `currentTemperature: "24.7"`
    - Sonoff TH `currentTemperature: "unavailable"`
    - Sonoff ZigBee: `temperature: "2096"`
    - Sonoff SC: `temperature: 23`
    - Sonoff POW: `power: "12.78"`
    """
    try:
        # https://github.com/AlexxIT/SonoffLAN/issues/110
        if 'currentTemperature' in state:
            state['temperature'] = float(state['currentTemperature'])
        if 'currentHumidity' in state:
            state['humidity'] = float(state['currentHumidity'])

        # battery_level is common name for battery attribute
        if 'battery' in state:
            state[ATTR_BATTERY_LEVEL] = state['battery']

        for k in ('power', 'voltage', 'current'):
            if k in state:
                state[k] = float(state[k])

        # zigbee device
        if deviceid.startswith('a4'):
            for k in ('temperature', 'humidity'):
                if k in state:
                    state[k] = int(state[k]) / 100.0
    except:
        pass


class ResponseWaiter:
    """Class wait right sequences in response messages."""
    _waiters = {}

    async def _set_response(self, data: dict):
        sequence = data.get('sequence')
        if sequence in self._waiters:
            # sometimes the error doesn't exists
            err = data.get('error')
            result = DATA_ERROR[err] if err in DATA_ERROR else f"E#{err}"
            # set future result
            self._waiters[sequence].set_result(result)

    async def _wait_response(self, sequence: str, timeout: int = 5):
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


class EWeLinkApp:
    appid = 'oeVkj2lYFGnJu5XUtWisfW4utiN4u9Mq'
    appsecret = '6Nz4n0xA8s8qdxQf2GqurZj2Fs55FUvM'


class EWeLinkCloud(ResponseWaiter, EWeLinkApp):
    devices: dict = None
    _handlers = None
    _ws: Optional[ClientWebSocketResponse] = None

    _baseurl = 'https://eu-api.coolkit.cc:8080/'
    _apikey = None
    _token = None
    _last_ts = 0

    def __init__(self, session: ClientSession):
        self.session = session

    async def _api(self, mode: str, api: str, payload: dict) \
            -> Optional[dict]:
        """Send API request to Cloud Server.

        :param mode: `get`, `post` or `login`
        :param api: api url without host: `api/user/login`
        :param payload: url params for `get` mode or json body for `post` mode
        :return: response as dict
        """
        ts = int(time.time())
        payload.update({
            'appid': self.appid,
            'nonce': str(ts),  # 8-digit random alphanumeric characters
            'ts': ts,  # 10-digit standard timestamp
            'version': 8
        })

        if mode == 'post':
            auth = "Bearer " + self._token
            coro = self.session.post(self._baseurl + api, json=payload,
                                     headers={'Authorization': auth})
        elif mode == 'get':
            auth = "Bearer " + self._token
            coro = self.session.get(self._baseurl + api, params=payload,
                                    headers={'Authorization': auth})
        elif mode == 'login':
            hex_dig = hmac.new(self.appsecret.encode(),
                               json.dumps(payload).encode(),
                               digestmod=hashlib.sha256).digest()
            auth = "Sign " + base64.b64encode(hex_dig).decode()
            coro = self.session.post(self._baseurl + api, json=payload,
                                     headers={'Authorization': auth})
        else:
            raise NotImplemented

        try:
            r = await coro
            return await r.json()
        except (Exception, RuntimeError) as e:
            _LOGGER.exception(f"Coolkit API error: {e}")
            return None

    async def _process_ws_msg(self, data: dict):
        """Process WebSocket message."""
        await self._set_response(data)

        deviceid = data.get('deviceid')
        # if msg about device
        if deviceid:
            _LOGGER.debug(f"{deviceid} <= Cloud3 | {data}")

            device = self.devices[deviceid]

            # if msg with device params
            if 'params' in data:
                state = data['params']

                # deal with online/offline state
                if state.get('online') is False:
                    device['online'] = False
                    state['cloud'] = 'offline'
                elif device['online'] is False:
                    device['online'] = True
                    state['cloud'] = 'online'

                fix_attrs(deviceid, state)

                for handler in self._handlers:
                    handler(deviceid, state, data.get('seq'))

            # response on our action update
            elif data['error'] == 0:
                # Force update device actual status
                sequence = str(int(time.time() * 1000))
                _LOGGER.debug(f"{deviceid} => Cloud5 | "
                              f"Force update sequence: {sequence}")

                await self._ws.send_json({
                    'action': 'query',
                    'apikey': device['apikey'],
                    'selfApikey': self._apikey,
                    'deviceid': deviceid,
                    'params': [],
                    'userAgent': 'app',
                    'sequence': sequence,
                    'ts': 0
                })

        # all other msg
        else:
            _LOGGER.debug(f"Cloud msg: {data}")

    async def _connect(self, fails: int = 0):
        """Permanent connection loop to Cloud Servers."""
        resp = await self._api('post', 'dispatch/app', {'accept': 'ws'})
        if resp:
            try:
                url = f"wss://{resp['IP']}:{resp['port']}/api/ws"
                self._ws = await self.session.ws_connect(
                    url, heartbeat=145, ssl=False)

                ts = time.time()
                payload = {
                    'action': 'userOnline',
                    'at': self._token,
                    'apikey': self._apikey,
                    'userAgent': 'app',
                    'appid': self.appid,
                    'nonce': str(int(ts / 100)),
                    'ts': int(ts),
                    'version': 8,
                    'sequence': str(int(ts * 1000))
                }
                await self._ws.send_json(payload)

                msg: WSMessage = await self._ws.receive()
                resp = json.loads(msg.data)
                if resp['error'] == 0:
                    _LOGGER.debug(f"Cloud init: {resp}")

                    fails = 0

                    async for msg in self._ws:
                        if msg.type == WSMsgType.TEXT:
                            resp = json.loads(msg.data)
                            await self._process_ws_msg(resp)

                        elif msg.type == WSMsgType.CLOSED:
                            _LOGGER.debug(f"Cloud WS Closed: {msg.data}")
                            break

                        elif msg.type == WSMsgType.ERROR:
                            _LOGGER.debug(f"Cloud WS Error: {msg.data}")
                            break

                else:
                    _LOGGER.debug(f"Cloud error: {resp}")

                # can't run two WS on same account in same time
                if time.time() - ts < 10 and fails < FAST_DELAY:
                    _LOGGER.error(CLOUD_ERROR)
                    fails = FAST_DELAY

            except ClientConnectorError as e:
                _LOGGER.error(f"Cloud WS Connection error: {e}")

            except (asyncio.CancelledError, RuntimeError) as e:
                if isinstance(e, RuntimeError):
                    assert e.args[0] == 'Session is closed', e.args

                _LOGGER.debug(f"Cancel WS Connection: {e}")
                if not self._ws.closed:
                    await self._ws.close()
                return

            except Exception as e:
                _LOGGER.exception(f"Cloud WS exception: {e}")

        delay = RETRY_DELAYS[fails]
        _LOGGER.debug(f"Cloud WS retrying in {delay} seconds")
        await asyncio.sleep(delay)

        if fails + 1 < len(RETRY_DELAYS):
            fails += 1

        asyncio.create_task(self._connect(fails))

    async def login(self, username: str, password: str) -> bool:
        # add a plus to the beginning of the phone number
        if '@' not in username and not username.startswith('+'):
            username = f"+{username}"

        pname = 'email' if '@' in username else 'phoneNumber'
        payload = {pname: username, 'password': password}
        resp = await self._api('login', 'api/user/login', payload)

        if resp is None or 'region' not in resp:
            _LOGGER.error(f"Login error: {resp}")
            return False

        region = resp['region']
        if region != 'eu':
            self._baseurl = self._baseurl.replace('eu', region)
            _LOGGER.debug(f"Redirect to region: {region}")
            resp = await self._api('login', 'api/user/login', payload)

        self._apikey = resp['user']['apikey']
        self._token = resp['at']

        return True

    async def load_devices(self) -> Optional[list]:
        assert self._token, "Login first"
        resp = await self._api('get', 'api/user/device', {'getTags': 1})
        if resp['error'] == 0:
            num = len(resp['devicelist'])
            _LOGGER.debug(f"{num} devices loaded from the Cloud Server")
            return resp['devicelist']
        else:
            _LOGGER.warning(f"Can't load devices: {resp}")
            return None

    @property
    def started(self) -> bool:
        return self._ws and not self._ws.closed

    async def start(self, handlers: List[Callable], devices: dict = None):
        assert self._token, "Login first"
        self._handlers = handlers
        self.devices = devices

        asyncio.create_task(self._connect())

    async def send(self, deviceid: str, data: dict, sequence: str):
        """Send request to device.

        :param deviceid: example `1000abcdefg`
        :param data: example `{'switch': 'on'}`
        :param sequence: 13-digit standard timestamp, to verify uniqueness
        """

        # protect cloud from DDoS (it can break connection)
        while time.time() - self._last_ts < 0.1:
            _LOGGER.debug("Protect cloud from DDoS")
            await asyncio.sleep(0.1)
            sequence = None

        self._last_ts = time.time()

        if sequence is None:
            sequence = str(int(self._last_ts * 1000))

        payload = {
            'action': 'query',
            'apikey': self.devices[deviceid]['apikey'],
            'selfApikey': self._apikey,
            'deviceid': deviceid,
            'params': [],
            'userAgent': 'app',
            'sequence': sequence,
            'ts': 0
        } if '_query' in data else {
            'action': 'update',
            # device apikey for shared devices
            'apikey': self.devices[deviceid]['apikey'],
            'selfApikey': self._apikey,
            'deviceid': deviceid,
            'userAgent': 'app',
            'sequence': sequence,
            'ts': 0,
            'params': data
        }
        log = f"{deviceid} => Cloud4 | {data} | {sequence}"
        _LOGGER.debug(log)
        try:
            await self._ws.send_json(payload)

            # wait for response with same sequence
            return await self._wait_response(sequence)

        except:
            _LOGGER.exception(log)
            return 'E#???'


class CloudPowHelper:
    def __init__(self, cloud: EWeLinkCloud):
        # search pow devices
        self.devices = [
            device for device in cloud.devices.values()
            if 'params' in device and 'uiActive' in device['params']]
        if not self.devices:
            return

        self.cloud = cloud

        _LOGGER.debug(f"Start refresh task for {len(self.devices)} POW")

        # noinspection PyProtectedMember
        self._cloud_process_ws_msg = cloud._process_ws_msg
        cloud._process_ws_msg = self._process_ws_msg

        asyncio.create_task(self.update())

    async def _process_ws_msg(self, data: dict):
        if 'params' in data and data['params'].get('uiActive') == 60:
            deviceid = data['deviceid']
            device = self.cloud.devices[deviceid]
            device['powActiveTime'] = 0

        elif 'config' in data and 'hundredDaysKwhData' in data['config']:
            # 000002 000207 000003 000002 000201 000008 000003 000006...
            kwh = data['config'].pop('hundredDaysKwhData')
            kwh = [round(int(kwh[i:i + 2], 16) +
                         int(kwh[i + 3] + kwh[i + 5]) * 0.01, 2)
                   for i in range(0, len(kwh), 6)]
            data['params'] = {'consumption': kwh}

        await self._cloud_process_ws_msg(data)

    async def update(self):
        if self.cloud.started:
            t = time.time()
            for device in self.devices:
                if t - device.get('powActiveTime', 0) > 3600:
                    device['powActiveTime'] = t
                    # set pow active status for 2 hours
                    await self.cloud.send(device['deviceid'], {
                        'uiActive': 7200}, None)

        # sleep for 1 minute
        await asyncio.sleep(60)

        asyncio.create_task(self.update())

    async def update_consumption(self):
        if self.cloud.started:
            _LOGGER.debug("Update consumption for all devices")
            for device in self.devices:
                await self.cloud.send(device['deviceid'], {
                    'hundredDaysKwh': 'get'}, None)
