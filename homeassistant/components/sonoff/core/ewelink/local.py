"""This registry can read data from LAN devices and send commands to them.
For non DIY devices data will be encrypted with devicekey. The registry cannot
decode such messages by itself because it does not manage the list of known
devices and their devicekey.
"""
import asyncio
import base64
import ipaddress
import json
import logging
from typing import Callable

import aiohttp
from Crypto.Cipher import AES
from Crypto.Hash import MD5
from Crypto.Random import get_random_bytes
from zeroconf import Zeroconf, DNSText, DNSAddress, DNSService, \
    current_time_millis
from zeroconf.asyncio import AsyncServiceBrowser

from .base import XRegistryBase, XDevice, SIGNAL_CONNECTED, SIGNAL_UPDATE

_LOGGER = logging.getLogger(__name__)


# some venv users don't have Crypto.Util.Padding
# I don't know why pycryptodome is not installed on their systems
# https://github.com/AlexxIT/SonoffLAN/issues/129

def pad(data_to_pad: bytes, block_size: int):
    padding_len = block_size - len(data_to_pad) % block_size
    padding = bytes([padding_len]) * padding_len
    return data_to_pad + padding


def unpad(padded_data: bytes, block_size: int):
    padding_len = padded_data[-1]
    return padded_data[:-padding_len]


def encrypt(payload: dict, devicekey: str):
    devicekey = devicekey.encode('utf-8')

    hash_ = MD5.new()
    hash_.update(devicekey)
    key = hash_.digest()

    iv = get_random_bytes(16)
    plaintext = json.dumps(payload['data']).encode('utf-8')

    cipher = AES.new(key, AES.MODE_CBC, iv=iv)
    padded = pad(plaintext, AES.block_size)
    ciphertext = cipher.encrypt(padded)

    payload['encrypt'] = True
    payload['data'] = base64.b64encode(ciphertext).decode('utf-8')
    payload['iv'] = base64.b64encode(iv).decode('utf-8')

    return payload


def decrypt(payload: dict, devicekey: str):
    devicekey = devicekey.encode('utf-8')

    hash_ = MD5.new()
    hash_.update(devicekey)
    key = hash_.digest()

    cipher = AES.new(key, AES.MODE_CBC, iv=base64.b64decode(payload['iv']))
    ciphertext = base64.b64decode(payload['data'])
    padded = cipher.decrypt(ciphertext)
    return unpad(padded, AES.block_size)


class XServiceBrowser(AsyncServiceBrowser):
    """Default ServiceBrowser have problems with processing messages. So we
    will process them manually.
    """

    def __init__(self, zeroconf: Zeroconf, type_: str, handler: Callable):
        super().__init__(zeroconf, type_, [self.default_handler])
        self.handler = handler
        self.suffix = "." + type_

    def default_handler(self, zeroconf, service_type, name, state_change):
        pass

    @staticmethod
    def decode_text(text: bytes):
        data = {}
        i = 0
        end = len(text)
        while i < end:
            j = text[i] + 1
            k, v = text[i + 1:i + j].split(b"=", 1)
            i += j
            data[k.decode()] = v.decode()
        return data

    def async_update_records(self, zc, now: float, records: list) -> None:
        # in normal situation we receive:
        #   1. DNSPointer (prt) - useless
        #   2. DNSText (txt) - has text array (key=value)
        #   3. DNSService (srv) - has port, usual 8081
        #   4. DNSAddress (a) - has IP-address
        # but some devices may not send IP-address
        #   https://github.com/AlexxIT/SonoffLAN/issues/839
        for record, old_record in records:
            try:
                # old_record - skip previous seen record
                # record.ttl <= 1 - skip previous (old) cached records
                # process only DNSText records with our suffix
                if old_record or record.ttl <= 1 or \
                        not isinstance(record, DNSText) or \
                        not record.key.endswith(self.suffix):
                    continue

                if not record.is_expired(now):
                    name = None
                    for r, _ in records:
                        if isinstance(r, DNSAddress) and record.name.startswith(r.name[:-6]):
                            name = r.name
                    key = record.key[:18]
                    host = None
                    port = None
                    for r, _ in records:
                        if r.key[:18] != key:
                            continue
                        if isinstance(r, DNSAddress):
                            host = str(ipaddress.ip_address(r.address))
                        elif isinstance(r, DNSService):
                            port = r.port

                    # support empty host and different port
                    if host:
                        host += f":{port}"

                    data = self.decode_text(record.text)
                    data["parentDevice"] = name[8:- 7] if name and data["type"] == 'diy_meter' else ''
                    asyncio.create_task(self.handler(record.name, host, data))
                else:
                    asyncio.create_task(self.handler(record.name))

            except Exception as e:
                _LOGGER.warning("Can't process zeroconf", exc_info=e)

        AsyncServiceBrowser.async_update_records(self, zc, now, records)

    def restore_from_cache(self):
        now = current_time_millis()
        cache: dict = self.zc.cache.cache
        for key, records in cache.items():
            try:
                if not key.endswith(self.suffix):
                    continue

                for record in records.keys():
                    if not isinstance(record, DNSText) or \
                            record.is_expired(now):
                        continue

                    host = None

                    key = record.key[:18] + ".local."
                    if key in cache:
                        for r in cache[key].keys():
                            if isinstance(r, DNSAddress):
                                host = str(ipaddress.ip_address(r.address))
                        for r in records.keys():
                            if isinstance(r, DNSService):
                                host += f":{r.port}"

                    data = self.decode_text(record.text)
                    asyncio.create_task(self.handler(record.name, host, data))

            except Exception as e:
                _LOGGER.warning("Can't restore zeroconf cache", exc_info=e)


class XRegistryLocal(XRegistryBase):
    browser: XServiceBrowser = None
    online: bool = False

    def start(self, zeroconf: Zeroconf):
        self.browser = XServiceBrowser(
            zeroconf, "_ewelink._tcp.local.", self._process_zeroconf
        )
        self.online = True
        self.browser.restore_from_cache()
        self.dispatcher_send(SIGNAL_CONNECTED)

    async def stop(self):
        if not self.online:
            return
        self.online = False
        await self.browser.async_cancel()

    async def _process_zeroconf(
            self, name: str, host: str = None, data: dict = None
    ):
        async def _explicitUpdate():
            payload = {
                "deviceid": data["parentDevice"],
                "data": {}
            }
            res = await self.diy_api_cmd(host, "subDevList", payload)
            if type(res) is not str and res["error"] == 0:
                subdevlist = res['data']['subDevList']
                for device in subdevlist:
                    if data["id"] == device['subDevId']:
                        continue
                    payload = {
                        "deviceid": data["parentDevice"],
                        "data": {
                            "subDevId": device['subDevId']
                        }
                    }
                    res = await self.diy_api_cmd(host, "getState", payload)
                    if type(res) is not str and res["error"] == 0:
                        params = {
                            "switches": res['data']['switches']
                        }
                        msg = {"deviceid": device["subDevId"], "parentdeviceid": data["parentDevice"],
                               "localtype": data["type"], "seq": res.get("seq"), "host": host, "params": params}
                        self.dispatcher_send(SIGNAL_UPDATE, msg)
            return

        if data is None:
            # TTL of record 5 minutes
            msg = {"deviceid": name[8:18], "params": {"online": False}}
            self.dispatcher_send(SIGNAL_UPDATE, msg)
            return

        raw = ''.join([
            data[f'data{i}'] for i in range(1, 5, 1) if f'data{i}' in data
        ])

        if "parentDevice" in data.keys() and len(data['parentDevice']) > 2:
            if data["id"] == data["parentDevice"]:
                await _explicitUpdate()
                return

            else:
                msg = {
                    "deviceid": data["id"],
                    "parentdeviceid": data["parentDevice"],
                    # "host": host,
                    "localtype": data["type"],
                    "seq": data.get("seq"),
                }
                if host != 'NA':
                    payload = {
                        "deviceid": data["parentDevice"],
                        "data": {
                            "subDevId": data["id"]
                        }
                    }
                    res = await self.diy_api_cmd(host, "getState", payload)
                    if type(res) is not str and res["error"] == 0:
                        params = {
                            "switches": res['data']['switches']
                        }
                        raw = json.dumps(params)
        else:
            msg = {
                "deviceid": data["id"],
                "localtype": data["type"],
                "seq": data.get("seq"),
            }

        if host:
            msg["host"] = host

        if data.get("encrypt"):
            msg["data"] = raw
            msg["iv"] = data["iv"]
        else:
            msg["params"] = json.loads(raw)

        self.dispatcher_send(SIGNAL_UPDATE, msg)
        if "parentDevice" in data.keys() and len(data['parentDevice']) > 2 and host != 'NA':
            await _explicitUpdate()

    async def diy_api_cmd(
            self, host, cmd: str, payload, timeout: int = 5
    ):

        log = "diy_api_cmd cmd:"+cmd

        try:
            # noinspection HttpUrlsUsage
            r = await self.session.post(
                f"http://{host}/zeroconf/{cmd}",
                json=payload, headers={'Connection': 'close'}, timeout=timeout
            )

            resp = await r.json()
            err = resp['error']
            if err == 0:
                _LOGGER.debug(f"{log} <= {resp}")
                return resp
            else:
                _LOGGER.warning(f"{log} <= {resp}")
                return f"E#{err}"

        except asyncio.TimeoutError:
            _LOGGER.debug(f"{log} !! Timeout {timeout}")
            return 'timeout'

        except aiohttp.ClientConnectorError as e:
            _LOGGER.debug(f"{log} !! Can't connect: {e}")
            return "E#CON"

        except (aiohttp.ClientOSError, aiohttp.ServerDisconnectedError,
                asyncio.CancelledError) as e:
            _LOGGER.debug(log, exc_info=e)
            return 'E#COS'

        except Exception as e:
            _LOGGER.error(log, exc_info=e)
            return 'E#???'

    async def send(
            self, device: XDevice, params: dict = None, sequence: str = None,
            timeout: int = 5
    ):
        # known commands for DIY: switch, startup, pulse, sledonline
        # other commands: switch, switches, transmit, dimmable, light, fan

        # cmd for D1 and RF Bridge 433
        if params:
            command = params.get("cmd") or next(iter(params))
        elif "sledOnline" in device["params"]:
            # device response with current status if we change any param
            command = "sledonline"
            params = {"sledOnline": device["params"]["sledOnline"]}
        else:
            return "noquery"

        if sequence is None:
            sequence = self.sequence()

        if ("localtype" in device.keys() and device["localtype"] == 'diy_meter'):

            t1 = {
                "sequence": sequence,
                "subDevId": device["deviceid"],
                "selfApikey": "123",
                # "data": params
            }
            data = dict(t1, **params)
            payload = {
                "deviceid": device["parentDevice"],
                "data": data
            }

        else:
            payload = {
                "sequence": sequence,
                "deviceid": device["deviceid"],
                "selfApikey": "123",
                "data": params
            }

        if 'devicekey' in device:
            payload = encrypt(payload, device['devicekey'])

        log = f"{device['deviceid']} => Local4 | {params}"

        try:
            # noinspection HttpUrlsUsage
            r = await self.session.post(
                f"http://{device['host']}/zeroconf/{command}",
                json=payload, headers={'Connection': 'close'}, timeout=timeout
            )

            if command == 'info':
                # better don't read response on info command
                # https://github.com/AlexxIT/SonoffLAN/issues/871
                _LOGGER.debug(f"{log} <= info: {r.status}")
                return 'online'

            resp = await r.json()
            err = resp['error']
            if err == 0:
                _LOGGER.debug(f"{log} <= {resp}")
                return 'online'
            else:
                _LOGGER.warning(f"{log} <= {resp}")
                return f"E#{err}"

        except asyncio.TimeoutError:
            _LOGGER.debug(f"{log} !! Timeout {timeout}")
            return 'timeout'

        except aiohttp.ClientConnectorError as e:
            _LOGGER.debug(f"{log} !! Can't connect: {e}")
            return "E#CON"

        except (aiohttp.ClientOSError, aiohttp.ServerDisconnectedError,
                asyncio.CancelledError) as e:
            _LOGGER.debug(log, exc_info=e)
            return 'E#COS'

        except Exception as e:
            _LOGGER.error(log, exc_info=e)
            return 'E#???'

    @staticmethod
    def decrypt_msg(msg: dict, devicekey: str = None) -> dict:
        data = decrypt(msg, devicekey)
        # Fix Sonoff RF Bridge sintax bug
        if data and data.startswith(b'{"rf'):
            data = data.replace(b'"="', b'":"')
        return json.loads(data)
