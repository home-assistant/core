# Python module to interface with Shenzhen Xenon ESP8266MOD WiFi smart devices
# E.g. https://wikidevi.com/wiki/Xenon_SM-PW701U
#   SKYROKU SM-PW701U Wi-Fi Plug Smart Plug
#   Wuudi SM-S0301-US - WIFI Smart Power Socket Multi Plug with 4 AC Outlets and 4 USB Charging Works with Alexa
#
# This would not exist without the protocol reverse engineering from
# https://github.com/codetheweb/tuyapi by codetheweb and blackrozes
#
# Tested with Python 2.7 and Python 3.6.1 only


import base64
from hashlib import md5
import json
import socket
import sys
import time


try:
    #raise ImportError
    from Crypto.Cipher import AES  # PyCrypto
except ImportError:
    AES = None
    from . import pyaes  # https://github.com/ricmoo/pyaes



ON = 'on'
OFF = 'off'

IS_PY2 = sys.version_info[0] == 2

class AESCipher(object):
    def __init__(self, key):
        #self.bs = 32  # 32 work fines for ON, does not work for OFF. Padding different compared to js version https://github.com/codetheweb/tuyapi/
        self.bs = 16
        self.key = key
    def encrypt(self, raw):
        if AES:
            raw = self._pad(raw.decode('utf-8'))
            cipher = AES.new(self.key, mode=AES.MODE_ECB)
            crypted_text = cipher.encrypt(raw)
        else:
            cipher = pyaes.blockfeeder.Encrypter(pyaes.AESModeOfOperationECB(self.key))  # no IV, auto pads to 16
            crypted_text = cipher.feed(raw)
            crypted_text += cipher.feed()  # flush final block
        #print('crypted_text %r' % crypted_text)
        #print('crypted_text (%d) %r' % (len(crypted_text), crypted_text))
        crypted_text_b64 = base64.b64encode(crypted_text)
        #print('crypted_text_b64 (%d) %r' % (len(crypted_text_b64), crypted_text_b64))
        return crypted_text_b64
    def decrypt(self, enc):
        enc = base64.b64decode(enc)
        #print('enc (%d) %r' % (len(enc), enc))
        #enc = self._unpad(enc)
        #enc = self._pad(enc)
        #print('upadenc (%d) %r' % (len(enc), enc))
        if AES:
            cipher = AES.new(self.key, AES.MODE_ECB)
            raw = cipher.decrypt(enc)
            #print('raw (%d) %r' % (len(raw), raw))
            return self._unpad(raw).decode('utf-8')
            #return self._unpad(cipher.decrypt(enc)).decode('utf-8')
        else:
            cipher = pyaes.blockfeeder.Decrypter(pyaes.AESModeOfOperationECB(self.key))  # no IV, auto pads to 16
            plain_text = cipher.feed(enc)
            plain_text += cipher.feed()  # flush final block
            return plain_text
    def _pad(self, s):
        rrr = s + (self.bs - len(s) % self.bs) * chr(self.bs - len(s) % self.bs)
        return rrr.encode('utf-8')
    @staticmethod
    def _unpad(s):
        return s[:-ord(s[len(s)-1:])]


def bin2hex(x, pretty=False):
    if pretty:
        space = ' '
    else:
        space = ''
    if IS_PY2:
        result = ''.join('%02X%s' % (ord(y), space) for y in x)
    else:
        result = ''.join('%02X%s' % (y, space) for y in x)
    return result


def hex2bin(x):
    if IS_PY2:
        return x.decode('hex')
    else:
        return bytes.fromhex(x)


payload_dict = {
  "outlet": {
    "status": {
      "prefix": "000055aa000000000000000a000000",  # Next byte is length of remaining payload, i.e. command + suffix (unclear if multiple bytes used for length)
      "command": {"gwId": "", "devId": ""},
      "suffix": "000000000000aa55"
    },
    "on": {
      "prefix": "000055aa0000000000000007000000",  # Next byte is length of remaining payload, i.e. command + suffix (unclear if multiple bytes used for length)
      "command": {"devId": "", "dps": {"1": True}, "uid": "", "t": ""},  # NOTE dps.1 is a sample and will be overwritten
      "suffix": "000000000000aa55"
    },
    "off": {
      "prefix": "000055aa0000000000000007000000",  # Next byte is length of remaining payload, i.e. command + suffix (unclear if multiple bytes used for length)
      "command": {"devId": "", "dps": {"1": False}, "uid": "", "t": ""},  # NOTE dps.1 is a sample and will be overwritten
      "suffix": "000000000000aa55"
    }
  }
}

class XenonDevice(object):
    def __init__(self, dev_id, address, local_key=None, dev_type=None):
        """
        dev_id is the "devId" in payload sent to Tuya servers during device activation/registration
        address is network address, e.g. "ip" packet in payload sent to Tuya servers during device activation/registration
        local_key is the "localkey" from payload sent to Tuya servers during device activation/registration
        """
        self.id = dev_id
        self.address = address
        self.local_key = local_key
        self.local_key = local_key.encode('latin1')
        self.dev_type = dev_type

        self.port = 6668  # default - do not expect caller to pass in
        self.version = 3.1  # default - do not expect caller to pass in

    def __repr__(self):
        return '%r' % ((self.id, self.address),)  # FIXME can do better than this

    def generate_payload(self, command, dps_id=None):
        if 'gwId' in payload_dict[self.dev_type][command]['command']:
            payload_dict[self.dev_type][command]['command']['gwId'] = self.id
        if 'devId' in payload_dict[self.dev_type][command]['command']:
            payload_dict[self.dev_type][command]['command']['devId'] = self.id
        if 'uid' in payload_dict[self.dev_type][command]['command']:
            payload_dict[self.dev_type][command]['command']['uid'] = self.id  # still use id, no seperate uid
        if 't' in payload_dict[self.dev_type][command]['command']:
            payload_dict[self.dev_type][command]['command']['t'] = str(int(time.time()))
        if 'dps' in payload_dict[self.dev_type][command]['command']:
            payload_dict[self.dev_type][command]['command']['dps'] = {}

        if command in (ON, OFF):
            switch_state = True if command == ON else False
            #print('dps_id  %r' % dps_id )
            payload_dict[self.dev_type][command]['command']['dps'][dps_id] = switch_state

        # Create byte buffer from hex data
        json_payload = json.dumps(payload_dict[self.dev_type][command]['command'])
        #print(json_payload)
        json_payload = json_payload.replace(' ', '')  # if spaces are not removed device does not respond!
        json_payload = json_payload.encode('utf-8')
        #print('json_payload %r' % json_payload)

        if command in (ON, OFF):
            # need to encrypt
            #print('json_payload %r' % json_payload)
            self.cipher = AESCipher(self.local_key)  # expect to connect and then disconnect to set new
            json_payload = self.cipher.encrypt(json_payload)
            #print('crypted json_payload %r' % json_payload)
            preMd5String = b'data=' + json_payload + b'||lpv=' + str(self.version).encode('latin1') + b'||' + self.local_key
            #print('preMd5String %r' % preMd5String)
            m = md5()
            m.update(preMd5String)
            #print(repr(m.digest()))
            hexdigest = m.hexdigest()
            #print(hexdigest)
            #print(hexdigest[8:][:16])
            json_payload = str(self.version).encode('latin1') + hexdigest[8:][:16].encode('latin1') + json_payload
            #print('data_to_send')
            #print(json_payload)
            #print('crypted json_payload (%d) %r' % (len(json_payload), json_payload))
            #print('json_payload  %r' % repr(json_payload))
            #print('json_payload len %r' % len(json_payload))
            #print(bin2hex(json_payload))
            self.cipher = None  # expect to connect and then disconnect to set new


        postfix_payload = hex2bin(bin2hex(json_payload) + payload_dict[self.dev_type][command]['suffix'])
        #print('postfix_payload %r' % postfix_payload)
        #print('postfix_payload %r' % len(postfix_payload))
        #print('postfix_payload %x' % len(postfix_payload))
        #print('postfix_payload %r' % hex(len(postfix_payload)))
        assert len(postfix_payload) <= 0xff
        postfix_payload_hex_len = '%x' % len(postfix_payload)  # TODO this assumes a single byte 0-255 (0x00-0xff)
        #print((payload_dict[self.dev_type][command]['prefix'] + postfix_payload_hex_len))
        buffer = hex2bin(payload_dict[self.dev_type][command]['prefix'] + postfix_payload_hex_len) + postfix_payload
        #print('command', command)
        #print('prefix')
        #print(payload_dict[self.dev_type][command]['prefix'])
        #print(repr(buffer))
        #print(bin2hex(buffer, pretty=True))
        #print(bin2hex(buffer, pretty=False))
        #print('full buffer(%d) %r' % (len(buffer), buffer))
        return buffer


class OutletDevice(XenonDevice):
    def __init__(self, dev_id, address, local_key=None, dev_type=None):
        dev_type = dev_type or 'outlet'
        super(OutletDevice, self).__init__(dev_id, address, local_key, dev_type)

    def status(self):
        # open device, send request, then close connection
        payload = self.generate_payload('status')

        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect((self.address, self.port))
        s.send(payload)
        data = s.recv(1024)
        s.close()

        result = data[20:-8]  # hard coded offsets
        #result = data[data.find('{'):data.rfind('}')+1]  # naive marker search, hope neither { nor } occur in header/footer
        #print('result %r' % result)
        result = json.loads(result)
        return result

    def set_status(self, on, switch=1):
        # open device, send request, then close connection
        command = ON if on else OFF
        if isinstance(switch, int):
            switch = str(switch)  # index and payload is a string
        payload = self.generate_payload(command, dps_id=switch)
        #print('payload %r' % payload)

        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect((self.address, self.port))
        s.send(payload)
        data = s.recv(1024)
        s.close()
        return data

    def set_timer(self, num_secs):
        """num_secs should be an integer
        """
        # FIXME / TODO replace and refactor, this duplicates alot of generate_payload()

        # Query status, pick last device id as that is probably the timer
        status = self.status()
        #print(status)
        devices = status['dps']
        #print(devices)
        devices_numbers = list(devices.keys())
        #print(devices_numbers)
        devices_numbers.sort()
        #print(devices_numbers)
        dps_id = devices_numbers[-1]
        #print(dps_id)

        command = ON  # same for setting timer as for on
        # generate_payload() code
        if 'gwId' in payload_dict[self.dev_type][command]['command']:
            payload_dict[self.dev_type][command]['command']['gwId'] = self.id
        if 'devId' in payload_dict[self.dev_type][command]['command']:
            payload_dict[self.dev_type][command]['command']['devId'] = self.id
        if 'uid' in payload_dict[self.dev_type][command]['command']:
            payload_dict[self.dev_type][command]['command']['uid'] = self.id  # still use id, no seperate uid
        if 't' in payload_dict[self.dev_type][command]['command']:
            payload_dict[self.dev_type][command]['command']['t'] = str(int(time.time()))
        if 'dps' in payload_dict[self.dev_type][command]['command']:
            payload_dict[self.dev_type][command]['command']['dps'] = {}

        payload_dict[self.dev_type][command]['command']['dps'][dps_id] = num_secs

        # Create byte buffer from hex data
        json_payload = json.dumps(payload_dict[self.dev_type][command]['command'])
        #print(json_payload)
        json_payload = json_payload.replace(' ', '')  # if spaces are not removed device does not respond!
        json_payload = json_payload.encode('utf-8')
        #print('json_payload %r' % json_payload)

        if command in (ON, OFF):
            # need to encrypt
            #print('json_payload %r' % json_payload)
            self.cipher = AESCipher(self.local_key)  # expect to connect and then disconnect to set new
            json_payload = self.cipher.encrypt(json_payload)
            #print('crypted json_payload %r' % json_payload)
            preMd5String = b'data=' + json_payload + b'||lpv=' + str(self.version).encode('latin1') + b'||' + self.local_key
            #print('preMd5String %r' % preMd5String)
            m = md5()
            m.update(preMd5String)
            #print(repr(m.digest()))
            hexdigest = m.hexdigest()
            #print(hexdigest)
            #print(hexdigest[8:][:16])
            json_payload = str(self.version).encode('latin1') + hexdigest[8:][:16].encode('latin1') + json_payload
            #print('data_to_send')
            #print(json_payload)
            #print('json_payload  %r' % repr(json_payload))
            #print('json_payload len %r' % len(json_payload))
            #print(bin2hex(json_payload))
            self.cipher = None  # expect to connect and then disconnect to set new


        postfix_payload = hex2bin(bin2hex(json_payload) + payload_dict[self.dev_type][command]['suffix'])
        assert len(postfix_payload) <= 0xff
        postfix_payload_hex_len = '%x' % len(postfix_payload)  # TODO this assumes a single byte 0-255 (0x00-0xff)
        buffer = hex2bin(payload_dict[self.dev_type][command]['prefix'] + postfix_payload_hex_len) + postfix_payload

        #print('command', command)
        #print('prefix')
        #print(payload_dict[self.dev_type][command]['prefix'])
        #print(repr(buffer))
        #print(bin2hex(buffer, pretty=True))
        #print(bin2hex(buffer, pretty=False))

        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect((self.address, self.port))
        s.send(buffer)
        data = s.recv(1024)
        s.close()
        return data
