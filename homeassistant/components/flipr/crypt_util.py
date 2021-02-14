"""Utility functions to encrypt and decrypt."""

import base64

from Crypto.Cipher import AES
from Crypto.Util.Padding import pad

# AES key must be either 16, 24, or 32 bytes long
COMMON_ENCRYPTION_KEY = "asdjk@15r32r1234asdsaeqwe314SEFT"

ENCODING = "utf-8"


def encrypt_data(raw_data: str, crypt_key: str = COMMON_ENCRYPTION_KEY) -> str:
    """Encrypts a string str with optional crypt_key key.

    Args:
        raw_data: the string to be encrypted
        crypt_key: the optional key to encrypt
    Return:
        the encrypted string to be used with method decrypt_data only
    """
    cipher = AES.new(_get_padded_key(crypt_key), AES.MODE_CFB)
    cipher_data = cipher.encrypt(raw_data.encode(ENCODING))
    cipher_iv = cipher.iv
    return str(base64.b64encode(cipher_iv + cipher_data), ENCODING)


def decrypt_data(crypted_data: str, crypt_key: str = COMMON_ENCRYPTION_KEY) -> str:
    """Decrypts a string str encrypted by encrypt_data function.

    Args:
        raw_data: the string to be decrypted
        crypt_key: the optional key to decrypt. Must be the same as the one used for encrypt_data.
    Return:
        the decrypted string.
    """
    crypted_buffer = base64.b64decode(crypted_data.encode(ENCODING))
    cfb_iv = crypted_buffer[0:16]
    crypted_raw = crypted_buffer[16 : len(crypted_buffer)]
    cipher = AES.new(_get_padded_key(crypt_key), AES.MODE_CFB, iv=cfb_iv)
    deciphered_bytes = cipher.decrypt(crypted_raw)
    return str(deciphered_bytes, ENCODING)


def _get_padded_key(crypt_key: str) -> bytearray:
    return pad(str.encode(ENCODING), 16)
