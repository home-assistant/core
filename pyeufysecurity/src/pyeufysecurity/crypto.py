"""Cryptography utilities for Eufy Security API."""

from __future__ import annotations

import base64

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes


def encrypt_api_data(data: str, key: bytes) -> str:
    """Encrypt data using AES-256-CBC with key[:16] as IV."""
    iv = key[:16]
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
    encryptor = cipher.encryptor()

    # PKCS7 padding
    padder = padding.PKCS7(128).padder()
    padded_data = padder.update(data.encode("utf-8")) + padder.finalize()

    encrypted = encryptor.update(padded_data) + encryptor.finalize()
    return base64.b64encode(encrypted).decode("utf-8")


def decrypt_api_data(data: str, key: bytes) -> str:
    """Decrypt data using AES-256-CBC with key[:16] as IV."""
    iv = key[:16]
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
    decryptor = cipher.decryptor()

    encrypted = base64.b64decode(data)
    decrypted = decryptor.update(encrypted) + decryptor.finalize()

    # Remove PKCS7 padding
    unpadder = padding.PKCS7(128).unpadder()
    unpadded = unpadder.update(decrypted) + unpadder.finalize()

    # Remove null terminator if present
    return unpadded.rstrip(b"\x00").decode("utf-8")
