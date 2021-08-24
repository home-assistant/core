# PyTuya Module
# -*- coding: utf-8 -*-
"""
Python module to interface with Tuya WiFi smart devices.

Mostly derived from Shenzhen Xenon ESP8266MOD WiFi smart devices
E.g. https://wikidevi.com/wiki/Xenon_SM-PW701U

Author: clach04
Maintained by: postlund

For more information see https://github.com/clach04/python-tuya

Classes
   TuyaInterface(dev_id, address, local_key=None)
       dev_id (str): Device ID e.g. 01234567891234567890
       address (str): Device Network IP Address e.g. 10.0.1.99
       local_key (str, optional): The encryption key. Defaults to None.

Functions
   json = status()          # returns json payload
   set_version(version)     #  3.1 [default] or 3.3
   detect_available_dps()   # returns a list of available dps provided by the device
   add_dps_to_request(dp_index)  # adds dp_index to the list of dps used by the
                                  # device (to be queried in the payload)
   set_dp(on, dp_index)   # Set value of any dps index.


Credits
 * TuyaAPI https://github.com/codetheweb/tuyapi by codetheweb and blackrozes
   For protocol reverse engineering
 * PyTuya https://github.com/clach04/python-tuya by clach04
   The origin of this python module (now abandoned)
 * LocalTuya https://github.com/rospogrigio/localtuya-homeassistant by rospogrigio
   Updated pytuya to support devices with Device IDs of 22 characters
"""

import asyncio
import base64
import binascii
import json
import logging
import struct
import time
import weakref
from abc import ABC, abstractmethod
from collections import namedtuple
from hashlib import md5

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

version_tuple = (9, 0, 0)
version = version_string = __version__ = "%d.%d.%d" % version_tuple
__author__ = "postlund"

_LOGGER = logging.getLogger(__name__)

TuyaMessage = namedtuple("TuyaMessage", "seqno cmd retcode payload crc")

SET = "set"
STATUS = "status"
HEARTBEAT = "heartbeat"

PROTOCOL_VERSION_BYTES_31 = b"3.1"
PROTOCOL_VERSION_BYTES_33 = b"3.3"

PROTOCOL_33_HEADER = PROTOCOL_VERSION_BYTES_33 + 12 * b"\x00"

MESSAGE_HEADER_FMT = ">4I"  # 4*uint32: prefix, seqno, cmd, length
MESSAGE_RECV_HEADER_FMT = ">5I"  # 4*uint32: prefix, seqno, cmd, length, retcode
MESSAGE_END_FMT = ">2I"  # 2*uint32: crc, suffix

PREFIX_VALUE = 0x000055AA
SUFFIX_VALUE = 0x0000AA55

HEARTBEAT_INTERVAL = 10

# This is intended to match requests.json payload at
# https://github.com/codetheweb/tuyapi :
# type_0a devices require the 0a command as the status request
# type_0d devices require the 0d command as the status request, and the list of
# dps used set to null in the request payload (see generate_payload method)

# prefix: # Next byte is command byte ("hexByte") some zero padding, then length
# of remaining payload, i.e. command + suffix (unclear if multiple bytes used for
# length, zero padding implies could be more than one byte)
PAYLOAD_DICT = {
    "type_0a": {
        STATUS: {"hexByte": 0x0A, "command": {"gwId": "", "devId": ""}},
        SET: {"hexByte": 0x07, "command": {"devId": "", "uid": "", "t": ""}},
        HEARTBEAT: {"hexByte": 0x09, "command": {}},
    },
    "type_0d": {
        STATUS: {"hexByte": 0x0D, "command": {"devId": "", "uid": "", "t": ""}},
        SET: {"hexByte": 0x07, "command": {"devId": "", "uid": "", "t": ""}},
        HEARTBEAT: {"hexByte": 0x09, "command": {}},
    },
}


class TuyaLoggingAdapter(logging.LoggerAdapter):
    """Adapter that adds device id to all log points."""

    def process(self, msg, kwargs):
        """Process log point and return output."""
        dev_id = self.extra["device_id"]
        return f"[{dev_id[0:3]}...{dev_id[-3:]}] {msg}", kwargs


class ContextualLogger:
    """Contextual logger adding device id to log points."""

    def __init__(self):
        """Initialize a new ContextualLogger."""
        self._logger = None

    def set_logger(self, logger, device_id):
        """Set base logger to use."""
        self._logger = TuyaLoggingAdapter(logger, {"device_id": device_id})

    def debug(self, msg, *args):
        """Debug level log."""
        return self._logger.log(logging.DEBUG, msg, *args)

    def info(self, msg, *args):
        """Info level log."""
        return self._logger.log(logging.INFO, msg, *args)

    def warning(self, msg, *args):
        """Warning method log."""
        return self._logger.log(logging.WARNING, msg, *args)

    def error(self, msg, *args):
        """Error level log."""
        return self._logger.log(logging.ERROR, msg, *args)

    def exception(self, msg, *args):
        """Exception level log."""
        return self._logger.exception(msg, *args)


def pack_message(msg):
    """Pack a TuyaMessage into bytes."""
    # Create full message excluding CRC and suffix
    buffer = (
        struct.pack(
            MESSAGE_HEADER_FMT,
            PREFIX_VALUE,
            msg.seqno,
            msg.cmd,
            len(msg.payload) + struct.calcsize(MESSAGE_END_FMT),
        )
        + msg.payload
    )

    # Calculate CRC, add it together with suffix
    buffer += struct.pack(MESSAGE_END_FMT, binascii.crc32(buffer), SUFFIX_VALUE)

    return buffer


def unpack_message(data):
    """Unpack bytes into a TuyaMessage."""
    header_len = struct.calcsize(MESSAGE_RECV_HEADER_FMT)
    end_len = struct.calcsize(MESSAGE_END_FMT)

    _, seqno, cmd, _, retcode = struct.unpack(
        MESSAGE_RECV_HEADER_FMT, data[:header_len]
    )
    payload = data[header_len:-end_len]
    crc, _ = struct.unpack(MESSAGE_END_FMT, data[-end_len:])
    return TuyaMessage(seqno, cmd, retcode, payload, crc)


class AESCipher:
    """Cipher module for Tuya communication."""

    def __init__(self, key):
        """Initialize a new AESCipher."""
        self.block_size = 16
        self.cipher = Cipher(algorithms.AES(key), modes.ECB(), default_backend())

    def encrypt(self, raw, use_base64=True):
        """Encrypt data to be sent to device."""
        encryptor = self.cipher.encryptor()
        crypted_text = encryptor.update(self._pad(raw)) + encryptor.finalize()
        return base64.b64encode(crypted_text) if use_base64 else crypted_text

    def decrypt(self, enc, use_base64=True):
        """Decrypt data from device."""
        if use_base64:
            enc = base64.b64decode(enc)

        decryptor = self.cipher.decryptor()
        return self._unpad(decryptor.update(enc) + decryptor.finalize()).decode()

    def _pad(self, data):
        padnum = self.block_size - len(data) % self.block_size
        return data + padnum * chr(padnum).encode()

    @staticmethod
    def _unpad(data):
        return data[: -ord(data[len(data) - 1 :])]


class MessageDispatcher(ContextualLogger):
    """Buffer and dispatcher for Tuya messages."""

    # Heartbeats always respond with sequence number 0, so they can't be waited for like
    # other messages. This is a hack to allow waiting for heartbeats.
    HEARTBEAT_SEQNO = -100

    def __init__(self, dev_id, listener):
        """Initialize a new MessageBuffer."""
        super().__init__()
        self.buffer = b""
        self.listeners = {}
        self.listener = listener
        self.set_logger(_LOGGER, dev_id)

    def abort(self):
        """Abort all waiting clients."""
        for key in self.listeners:
            sem = self.listeners[key]
            self.listeners[key] = None

            # TODO: Received data and semahore should be stored separately
            if isinstance(sem, asyncio.Semaphore):
                sem.release()

    async def wait_for(self, seqno, timeout=5):
        """Wait for response to a sequence number to be received and return it."""
        if seqno in self.listeners:
            raise Exception(f"listener exists for {seqno}")

        self.debug("Waiting for sequence number %d", seqno)
        self.listeners[seqno] = asyncio.Semaphore(0)
        try:
            await asyncio.wait_for(self.listeners[seqno].acquire(), timeout=timeout)
        except asyncio.TimeoutError:
            del self.listeners[seqno]
            raise

        return self.listeners.pop(seqno)

    def add_data(self, data):
        """Add new data to the buffer and try to parse messages."""
        self.buffer += data
        header_len = struct.calcsize(MESSAGE_RECV_HEADER_FMT)

        while self.buffer:
            # Check if enough data for measage header
            if len(self.buffer) < header_len:
                break

            # Parse header and check if enough data according to length in header
            _, seqno, cmd, length, retcode = struct.unpack_from(
                MESSAGE_RECV_HEADER_FMT, self.buffer
            )
            if len(self.buffer[header_len - 4 :]) < length:
                break

            # length includes payload length, retcode, crc and suffix
            if (retcode & 0xFFFFFF00) != 0:
                payload_start = header_len - 4
                payload_length = length - struct.calcsize(MESSAGE_END_FMT)
            else:
                payload_start = header_len
                payload_length = length - 4 - struct.calcsize(MESSAGE_END_FMT)
            payload = self.buffer[payload_start : payload_start + payload_length]

            crc, _ = struct.unpack_from(
                MESSAGE_END_FMT,
                self.buffer[payload_start + payload_length : payload_start + length],
            )

            self.buffer = self.buffer[header_len - 4 + length :]
            self._dispatch(TuyaMessage(seqno, cmd, retcode, payload, crc))

    def _dispatch(self, msg):
        """Dispatch a message to someone that is listening."""
        self.debug("Dispatching message %s", msg)
        if msg.seqno in self.listeners:
            self.debug("Dispatching sequence number %d", msg.seqno)
            sem = self.listeners[msg.seqno]
            self.listeners[msg.seqno] = msg
            sem.release()
        elif msg.cmd == 0x09:
            self.debug("Got heartbeat response")
            if self.HEARTBEAT_SEQNO in self.listeners:
                sem = self.listeners[self.HEARTBEAT_SEQNO]
                self.listeners[self.HEARTBEAT_SEQNO] = msg
                sem.release()
        elif msg.cmd == 0x08:
            self.debug("Got status update")
            self.listener(msg)
        else:
            self.debug(
                "Got message type %d for unknown listener %d: %s",
                msg.cmd,
                msg.seqno,
                msg,
            )


class TuyaListener(ABC):
    """Listener interface for Tuya device changes."""

    @abstractmethod
    def status_updated(self, status):
        """Device updated status."""

    @abstractmethod
    def disconnected(self):
        """Device disconnected."""


class EmptyListener(TuyaListener):
    """Listener doing nothing."""

    def status_updated(self, status):
        """Device updated status."""

    def disconnected(self):
        """Device disconnected."""


class TuyaProtocol(asyncio.Protocol, ContextualLogger):
    """Implementation of the Tuya protocol."""

    def __init__(self, dev_id, local_key, protocol_version, on_connected, listener):
        """
        Initialize a new TuyaInterface.

        Args:
            dev_id (str): The device id.
            address (str): The network address.
            local_key (str, optional): The encryption key. Defaults to None.

        Attributes:
            port (int): The port to connect to.
        """
        super().__init__()
        self.loop = asyncio.get_running_loop()
        self.set_logger(_LOGGER, dev_id)
        self.id = dev_id
        self.local_key = local_key.encode("latin1")
        self.version = protocol_version
        self.dev_type = "type_0a"
        self.dps_to_request = {}
        self.cipher = AESCipher(self.local_key)
        self.seqno = 0
        self.transport = None
        self.listener = weakref.ref(listener)
        self.dispatcher = self._setup_dispatcher()
        self.on_connected = on_connected
        self.heartbeater = None
        self.dps_cache = {}

    def _setup_dispatcher(self):
        def _status_update(msg):
            decoded_message = self._decode_payload(msg.payload)
            if "dps" in decoded_message:
                self.dps_cache.update(decoded_message["dps"])

            listener = self.listener and self.listener()
            if listener is not None:
                listener.status_updated(self.dps_cache)

        return MessageDispatcher(self.id, _status_update)

    def connection_made(self, transport):
        """Did connect to the device."""

        async def heartbeat_loop():
            """Continuously send heart beat updates."""
            self.debug("Started heartbeat loop")
            while True:
                try:
                    await self.heartbeat()
                    await asyncio.sleep(HEARTBEAT_INTERVAL)
                except asyncio.CancelledError:
                    self.debug("Stopped heartbeat loop")
                    raise
                except asyncio.TimeoutError:
                    self.debug("Heartbeat failed due to timeout, disconnecting")
                    break
                except Exception as ex:  # pylint: disable=broad-except
                    self.exception("Heartbeat failed (%s), disconnecting", ex)
                    break

            transport = self.transport
            self.transport = None
            transport.close()

        self.transport = transport
        self.on_connected.set_result(True)
        self.heartbeater = self.loop.create_task(heartbeat_loop())

    def data_received(self, data):
        """Received data from device."""
        self.dispatcher.add_data(data)

    def connection_lost(self, exc):
        """Disconnected from device."""
        self.debug("Connection lost: %s", exc)
        try:
            listener = self.listener and self.listener()
            if listener is not None:
                listener.disconnected()
        except Exception:  # pylint: disable=broad-except
            self.exception("Failed to call disconnected callback")

    async def close(self):
        """Close connection and abort all outstanding listeners."""
        self.debug("Closing connection")
        if self.heartbeater is not None:
            self.heartbeater.cancel()
            try:
                await self.heartbeater
            except asyncio.CancelledError:
                pass
            self.heartbeater = None
        if self.dispatcher is not None:
            self.dispatcher.abort()
            self.dispatcher = None
        if self.transport is not None:
            transport = self.transport
            self.transport = None
            transport.close()

    async def exchange(self, command, dps=None):
        """Send and receive a message, returning response from device."""
        self.debug(
            "Sending command %s (device type: %s)",
            command,
            self.dev_type,
        )
        payload = self._generate_payload(command, dps)
        dev_type = self.dev_type

        # Wait for special sequence number if heartbeat
        seqno = (
            MessageDispatcher.HEARTBEAT_SEQNO
            if command == HEARTBEAT
            else (self.seqno - 1)
        )

        self.transport.write(payload)
        msg = await self.dispatcher.wait_for(seqno)
        if msg is None:
            self.debug("Wait was aborted for seqno %d", seqno)
            return None

        # TODO: Verify stuff, e.g. CRC sequence number?
        payload = self._decode_payload(msg.payload)

        # Perform a new exchange (once) if we switched device type
        if dev_type != self.dev_type:
            self.debug(
                "Re-send %s due to device type change (%s -> %s)",
                command,
                dev_type,
                self.dev_type,
            )
            return await self.exchange(command, dps)
        return payload

    async def status(self):
        """Return device status."""
        status = await self.exchange(STATUS)
        if status and "dps" in status:
            self.dps_cache.update(status["dps"])
        return self.dps_cache

    async def heartbeat(self):
        """Send a heartbeat message."""
        return await self.exchange(HEARTBEAT)

    async def set_dp(self, value, dp_index):
        """
        Set value (may be any type: bool, int or string) of any dps index.

        Args:
            dp_index(int):   dps index to set
            value: new value for the dps index
        """
        return await self.exchange(SET, {str(dp_index): value})

    async def set_dps(self, dps):
        """Set values for a set of datapoints."""
        return await self.exchange(SET, dps)

    async def detect_available_dps(self):
        """Return which datapoints are supported by the device."""
        # type_0d devices need a sort of bruteforce querying in order to detect the
        # list of available dps experience shows that the dps available are usually
        # in the ranges [1-25] and [100-110] need to split the bruteforcing in
        # different steps due to request payload limitation (max. length = 255)
        self.dps_cache = {}
        ranges = [(2, 11), (11, 21), (21, 31), (100, 111)]

        for dps_range in ranges:
            # dps 1 must always be sent, otherwise it might fail in case no dps is found
            # in the requested range
            self.dps_to_request = {"1": None}
            self.add_dps_to_request(range(*dps_range))
            try:
                data = await self.status()
            except Exception as ex:
                self.exception("Failed to get status: %s", ex)
                raise
            if "dps" in data:
                self.dps_cache.update(data["dps"])

            if self.dev_type == "type_0a":
                return self.dps_cache
        self.debug("Detected dps: %s", self.dps_cache)
        return self.dps_cache

    def add_dps_to_request(self, dp_indicies):
        """Add a datapoint (DP) to be included in requests."""
        if isinstance(dp_indicies, int):
            self.dps_to_request[str(dp_indicies)] = None
        else:
            self.dps_to_request.update({str(index): None for index in dp_indicies})

    def _decode_payload(self, payload):
        if not payload:
            payload = "{}"
        elif payload.startswith(b"{"):
            pass
        elif payload.startswith(PROTOCOL_VERSION_BYTES_31):
            payload = payload[len(PROTOCOL_VERSION_BYTES_31) :]  # remove version header
            # remove (what I'm guessing, but not confirmed is) 16-bytes of MD5
            # hexdigest of payload
            payload = self.cipher.decrypt(payload[16:])
        elif self.version == 3.3:
            if self.dev_type != "type_0a" or payload.startswith(
                PROTOCOL_VERSION_BYTES_33
            ):
                payload = payload[len(PROTOCOL_33_HEADER) :]
            payload = self.cipher.decrypt(payload, False)

            if "data unvalid" in payload:
                self.dev_type = "type_0d"
                self.debug(
                    "switching to dev_type %s",
                    self.dev_type,
                )
                return None
        else:
            raise Exception(f"Unexpected payload={payload}")

        if not isinstance(payload, str):
            payload = payload.decode()
        self.debug("Decrypted payload: %s", payload)
        return json.loads(payload)

    def _generate_payload(self, command, data=None):
        """
        Generate the payload to send.

        Args:
            command(str): The type of command.
                This is one of the entries from payload_dict
            data(dict, optional): The data to be send.
                This is what will be passed via the 'dps' entry
        """
        cmd_data = PAYLOAD_DICT[self.dev_type][command]
        json_data = cmd_data["command"]
        command_hb = cmd_data["hexByte"]

        if "gwId" in json_data:
            json_data["gwId"] = self.id
        if "devId" in json_data:
            json_data["devId"] = self.id
        if "uid" in json_data:
            json_data["uid"] = self.id  # still use id, no separate uid
        if "t" in json_data:
            json_data["t"] = str(int(time.time()))

        if data is not None:
            json_data["dps"] = data
        elif command_hb == 0x0D:
            json_data["dps"] = self.dps_to_request

        payload = json.dumps(json_data).replace(" ", "").encode("utf-8")
        self.debug("Send payload: %s", payload)

        if self.version == 3.3:
            payload = self.cipher.encrypt(payload, False)
            if command_hb != 0x0A:
                # add the 3.3 header
                payload = PROTOCOL_33_HEADER + payload
        elif command == SET:
            payload = self.cipher.encrypt(payload)
            to_hash = (
                b"data="
                + payload
                + b"||lpv="
                + PROTOCOL_VERSION_BYTES_31
                + b"||"
                + self.local_key
            )
            hasher = md5()
            hasher.update(to_hash)
            hexdigest = hasher.hexdigest()
            payload = (
                PROTOCOL_VERSION_BYTES_31
                + hexdigest[8:][:16].encode("latin1")
                + payload
            )

        msg = TuyaMessage(self.seqno, command_hb, 0, payload, 0)
        self.seqno += 1
        return pack_message(msg)

    def __repr__(self):
        """Return internal string representation of object."""
        return self.id


async def connect(
    address,
    device_id,
    local_key,
    protocol_version,
    listener=None,
    port=6668,
    timeout=5,
):
    """Connect to a device."""
    loop = asyncio.get_running_loop()
    on_connected = loop.create_future()
    _, protocol = await loop.create_connection(
        lambda: TuyaProtocol(
            device_id,
            local_key,
            protocol_version,
            on_connected,
            listener or EmptyListener(),
        ),
        address,
        port,
    )

    await asyncio.wait_for(on_connected, timeout=timeout)
    return protocol
