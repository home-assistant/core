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
from zeroconf import Zeroconf, DNSText, DNSAddress, current_time_millis
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
                    address = next(
                        r.address for r, _ in records
                        if isinstance(r, DNSAddress) and
                        # check without `local.` tail
                        record.name.startswith(r.name[:-6])
                    )
                    host = str(ipaddress.ip_address(address))
                    data = self.decode_text(record.text)
                    asyncio.create_task(self.handler(record.name, host, data))
                else:
                    asyncio.create_task(self.handler(record.name))

            except StopIteration:
                _LOGGER.debug(f"Can't find address for {record.name}")
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
                    key = record.key.split(".", 1)[0] + ".local."
                    address = next(
                        r.address for r in cache[key].keys()
                        if isinstance(r, DNSAddress)
                    )
                    host = str(ipaddress.ip_address(address))
                    data = self.decode_text(record.text)
                    asyncio.create_task(self.handler(record.name, host, data))

            except KeyError:
                _LOGGER.debug(f"Can't find key in zeroconf cache: {key}")
            except StopIteration:
                _LOGGER.debug(f"Can't find address for {key}")
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
        if host is None:
            # TTL of record 5 minutes
            msg = {"deviceid": name[8:18], "params": {"online": False}}
            self.dispatcher_send(SIGNAL_UPDATE, msg)
            return

        raw = ''.join([
            data[f'data{i}'] for i in range(1, 5, 1) if f'data{i}' in data
        ])

        msg = {
            "deviceid": data["id"],
            "host": host,
            "localtype": data["type"],
            "seq": data.get("seq"),
        }

        if data.get("encrypt"):
            msg["data"] = raw
            msg["iv"] = data["iv"]
        else:
            msg["params"] = json.loads(raw)

        self.dispatcher_send(SIGNAL_UPDATE, msg)

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
                f"http://{device['host']}:8081/zeroconf/{command}",
                json=payload, headers={'Connection': 'close'}, timeout=timeout
            )
            resp = await r.json()
            err = resp['error']
            # no problem with any response from device for info command
            if err == 0 or command == 'info':
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
