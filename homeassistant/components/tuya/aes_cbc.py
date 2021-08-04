#!/usr/bin/env python3
"""AES-CBC encryption and decryption for account info."""

import base64 as b64
from binascii import a2b_hex, b2a_hex
import json
import secrets

from Crypto.Cipher import AES

AES_ACCOUNT_KEY = "o0o0o0"
XOR_KEY = "00oo00"
KEY_KEY = "oo00oo"


class AesCBC:
    """AES helper."""

    @classmethod
    def random_16(cls):
        """Return random 16."""
        return "".join(
            secrets.choice("abcdefghijklmnopqrstuvwxyz!@#$%^&*1234567890")
            for i in range(16)
        )

    @classmethod
    def add_to_16(cls, text):
        """Add to 16."""
        if len(text.encode("utf-8")) % 16:
            add = 16 - (len(text.encode("utf-8")) % 16)
        else:
            add = 0
        text = text + ("\0" * add)
        return text.encode("utf-8")

    @classmethod
    def cbc_encrypt(cls, key, offset, text):
        """Cbc encrypt."""
        key = key.encode("utf-8")
        mode = AES.MODE_CBC
        offset = bytes(offset, encoding="utf8")
        text = cls.add_to_16(text)
        cryptos = AES.new(key, mode, offset)
        cipher_text = cryptos.encrypt(text)
        return str(b2a_hex(cipher_text), encoding="utf-8")

    @classmethod
    def cbc_decrypt(cls, key, offset, text):
        """Cbc decrypt."""
        key = key.encode("utf-8")
        offset = bytes(offset, encoding="utf8")
        mode = AES.MODE_CBC
        cryptos = AES.new(key, mode, offset)
        plain_text = cryptos.decrypt(a2b_hex(text))
        return bytes.decode(plain_text).rstrip("\0")

    @classmethod
    def xor_encrypt(cls, data, key):
        """Xor encrypt."""
        lkey = len(key)
        secret = []
        num = 0
        for each in data:
            if num >= lkey:
                num = num % lkey
            secret.append(chr(ord(each) ^ ord(key[num])))
            num += 1
        return b64.b64encode("".join(secret).encode()).decode()

    @classmethod
    def xor_decrypt(cls, secret, key):
        """Xor decrypt."""
        tips = b64.b64decode(secret.encode()).decode()
        lkey = len(key)
        secret = []
        num = 0
        for each in tips:
            if num >= lkey:
                num = num % lkey
            secret.append(chr(ord(each) ^ ord(key[num])))
            num += 1
        return "".join(secret)

    @classmethod
    def json_to_dict(cls, json_str):
        """Json to dict."""
        return json.loads(json_str)

    @classmethod
    def b64_encrypt(cls, text):
        """Base64 encrypt."""
        return b64.b64encode(text.encode()).decode()

    @classmethod
    def b64_decrypt(cls, text):
        """Base64 decrypt."""
        return b64.b64decode(text).decode()
