"""General utilities."""

import binascii
import hashlib

from Crypto.Cipher import AES


def md5sum(value: str):
    """Return a MD5 hash of a string."""
    m = hashlib.md5()
    m.update(value.encode("UTF-8"))
    return m.digest()


def encrypt(key: str, value: str):
    """Encrypt a value."""
    cipher = AES.new(md5sum(key), AES.MODE_ECB)
    return binascii.b2a_hex(cipher.encrypt(binascii.a2b_hex(value))).upper()
