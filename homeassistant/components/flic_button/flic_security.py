"""Cryptographic operations for Flic 2 protocol."""

from __future__ import annotations

import hashlib
import hmac
import logging
import struct

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from cryptography.hazmat.primitives.asymmetric.x25519 import (
    X25519PrivateKey,
    X25519PublicKey,
)

_LOGGER = logging.getLogger(__name__)


def verify_ed25519_signature_with_variant(
    public_key_bytes: bytes, message: bytes, signature: bytes
) -> int | None:
    """Verify an Ed25519 signature trying all 4 twist variants.

    The Flic 2 protocol uses signature variants related to the twist security
    parameter in Ed25519. This function tries all 4 variants (0-3) by modifying
    signature[32] and returns the successful variant.
    """
    try:
        public_key = Ed25519PublicKey.from_public_bytes(public_key_bytes)
    except Exception:  # noqa: BLE001
        return None

    # Try all 4 signature variants (bits 0-1 of signature[32])
    for variant in range(4):
        modified_signature = bytearray(signature)
        # Set bits 0-1 to variant, preserve bits 2-7
        modified_signature[32] = (modified_signature[32] & 0xFC) | variant

        try:
            public_key.verify(bytes(modified_signature), message)
        except Exception:  # noqa: BLE001
            continue
        else:
            return variant

    return None  # All variants failed


def x25519_key_exchange(private_key_bytes: bytes, public_key_bytes: bytes) -> bytes:
    """Perform X25519 Diffie-Hellman key exchange."""
    private_key = X25519PrivateKey.from_private_bytes(private_key_bytes)
    public_key = X25519PublicKey.from_public_bytes(public_key_bytes)
    return private_key.exchange(public_key)


def generate_x25519_keypair() -> tuple[bytes, bytes]:
    """Generate an X25519 keypair for ECDH."""
    private_key = X25519PrivateKey.generate()
    public_key = private_key.public_key()
    return (
        private_key.private_bytes_raw(),
        public_key.public_bytes_raw(),
    )


def chaskey_generate_subkeys(key: bytes) -> list[int]:
    """Generate Chaskey subkeys from a 16-byte key."""
    if len(key) != 16:
        msg = "Chaskey key must be 16 bytes"
        raise ValueError(msg)

    # Load key as 4 little-endian 32-bit integers
    v0, v1, v2, v3 = struct.unpack("<4I", key)

    ret = [0] * 12
    ret[0] = v0
    ret[1] = v1
    ret[2] = v2
    ret[3] = v3

    # Generate k1 (times2 in GF(2^128))
    c = ((v3 >> 31) & 1) * 0x87
    v3 = ((v3 << 1) | (v2 >> 31)) & 0xFFFFFFFF
    v2 = ((v2 << 1) | (v1 >> 31)) & 0xFFFFFFFF
    v1 = ((v1 << 1) | (v0 >> 31)) & 0xFFFFFFFF
    v0 = ((v0 << 1) ^ c) & 0xFFFFFFFF
    ret[4] = v0
    ret[5] = v1
    ret[6] = v2
    ret[7] = v3

    # Generate k2 (times2 again)
    c = ((v3 >> 31) & 1) * 0x87
    v3 = ((v3 << 1) | (v2 >> 31)) & 0xFFFFFFFF
    v2 = ((v2 << 1) | (v1 >> 31)) & 0xFFFFFFFF
    v1 = ((v1 << 1) | (v0 >> 31)) & 0xFFFFFFFF
    v0 = ((v0 << 1) ^ c) & 0xFFFFFFFF
    ret[8] = v0
    ret[9] = v1
    ret[10] = v2
    ret[11] = v3

    return ret


def _load_int(data: bytes, offset: int) -> int:
    """Load a little-endian 32-bit integer from bytes."""
    return struct.unpack("<I", data[offset : offset + 4])[0]


def chaskey_with_dir_and_counter(
    keys: list[int], direction: int, counter: int, data: bytes
) -> bytes:
    """Compute Chaskey MAC with direction and packet counter."""
    if not data:
        msg = "Data must not be empty"
        raise ValueError(msg)

    # Initialize state: XOR key with counter and direction
    # v0 = keys[0] xor counter_low32
    # v1 = keys[1] xor counter_high32
    # v2 = keys[2] xor direction
    # v3 = keys[3]
    v0 = keys[0] ^ (counter & 0xFFFFFFFF)
    v1 = keys[1] ^ ((counter >> 32) & 0xFFFFFFFF)
    v2 = keys[2] ^ direction
    v3 = keys[3]

    offset = 0
    length = len(data)
    first = True

    while True:
        keys_offset = 0

        if not first:
            if length >= 16:
                # Full block
                v0 ^= _load_int(data, offset)
                v1 ^= _load_int(data, offset + 4)
                v2 ^= _load_int(data, offset + 8)
                v3 ^= _load_int(data, offset + 12)
                offset += 16
                length -= 16
                if length == 0:
                    keys_offset = 4  # Use k1
            else:
                # Partial block - pad with 0x01 then zeros
                tmp = bytearray(16)
                tmp[:length] = data[offset : offset + length]
                tmp[length] = 0x01
                v0 ^= _load_int(bytes(tmp), 0)
                v1 ^= _load_int(bytes(tmp), 4)
                v2 ^= _load_int(bytes(tmp), 8)
                v3 ^= _load_int(bytes(tmp), 12)
                keys_offset = 8  # Use k2

            if keys_offset != 0:
                v0 ^= keys[keys_offset]
                v1 ^= keys[keys_offset + 1]
                v2 ^= keys[keys_offset + 2]
                v3 ^= keys[keys_offset + 3]
        else:
            first = False

        # Pre-rotate v2
        v2 = ((v2 >> 16) | (v2 << 16)) & 0xFFFFFFFF

        # 16 rounds
        for _ in range(16):
            v0 = (v0 + v1) & 0xFFFFFFFF
            v1 = (v0 ^ (((v1 >> 27) | (v1 << 5)) & 0xFFFFFFFF)) & 0xFFFFFFFF
            v2 = (v3 + (((v2 >> 16) | (v2 << 16)) & 0xFFFFFFFF)) & 0xFFFFFFFF
            v3 = (v2 ^ (((v3 >> 24) | (v3 << 8)) & 0xFFFFFFFF)) & 0xFFFFFFFF
            v2 = (v2 + v1) & 0xFFFFFFFF
            v0 = (v3 + (((v0 >> 16) | (v0 << 16)) & 0xFFFFFFFF)) & 0xFFFFFFFF
            v1 = (v2 ^ (((v1 >> 25) | (v1 << 7)) & 0xFFFFFFFF)) & 0xFFFFFFFF
            v3 = (v0 ^ (((v3 >> 19) | (v3 << 13)) & 0xFFFFFFFF)) & 0xFFFFFFFF

        # Post-rotate v2
        v2 = ((v2 >> 16) | (v2 << 16)) & 0xFFFFFFFF

        if keys_offset != 0:
            # Final XOR and return 5-byte MAC
            v0 ^= keys[keys_offset]
            v1 ^= keys[keys_offset + 1]
            # Return first 5 bytes: 4 bytes of v0 + 1 byte of v1
            return struct.pack("<IB", v0, v1 & 0xFF)


def chaskey_16_bytes(keys: list[int], data: bytes) -> bytes:
    """Compute Chaskey MAC for exactly 16 bytes of data."""
    if len(data) != 16:
        msg = "Data must be exactly 16 bytes"
        raise ValueError(msg)

    # Initialize state: XOR key with k1 and data
    v0 = keys[0] ^ keys[4] ^ _load_int(data, 0)
    v1 = keys[1] ^ keys[5] ^ _load_int(data, 4)
    v2 = keys[2] ^ keys[6] ^ _load_int(data, 8)
    v3 = keys[3] ^ keys[7] ^ _load_int(data, 12)

    # Pre-rotate v2
    v2 = ((v2 >> 16) | (v2 << 16)) & 0xFFFFFFFF

    # 16 rounds
    for _ in range(16):
        v0 = (v0 + v1) & 0xFFFFFFFF
        v1 = (v0 ^ (((v1 >> 27) | (v1 << 5)) & 0xFFFFFFFF)) & 0xFFFFFFFF
        v2 = (v3 + (((v2 >> 16) | (v2 << 16)) & 0xFFFFFFFF)) & 0xFFFFFFFF
        v3 = (v2 ^ (((v3 >> 24) | (v3 << 8)) & 0xFFFFFFFF)) & 0xFFFFFFFF
        v2 = (v2 + v1) & 0xFFFFFFFF
        v0 = (v3 + (((v0 >> 16) | (v0 << 16)) & 0xFFFFFFFF)) & 0xFFFFFFFF
        v1 = (v2 ^ (((v1 >> 25) | (v1 << 7)) & 0xFFFFFFFF)) & 0xFFFFFFFF
        v3 = (v0 ^ (((v3 >> 19) | (v3 << 13)) & 0xFFFFFFFF)) & 0xFFFFFFFF

    # Post-rotate v2
    v2 = ((v2 >> 16) | (v2 << 16)) & 0xFFFFFFFF

    # Final XOR with k1
    v0 ^= keys[4]
    v1 ^= keys[5]
    v2 ^= keys[6]
    v3 ^= keys[7]

    # Return 16-byte result
    return struct.pack("<4I", v0, v1, v2, v3)


def derive_full_verify_keys(
    shared_secret: bytes,
    signature_variant: int,
    device_random: bytes,
    client_random: bytes,
    *,
    is_twist: bool = False,
) -> tuple[bytes, bytes, bytes, int, bytes]:
    """Derive all cryptographic keys for FullVerify pairing."""
    # Build flags byte for key derivation
    # Flic 2/Duo: supportsDuo=true (0x80)
    # Twist: clientVariantByte=0x00 (per PROTOCOL.md)
    flags = bytes([0x00]) if is_twist else bytes([0x80])

    _LOGGER.debug("Deriving full verify keys (is_twist=%s)", is_twist)

    # Compute fullVerifySecret = SHA256(sharedSecret + variant + device_random + client_random + flags)
    concatenated = (
        shared_secret
        + bytes([signature_variant])
        + device_random
        + client_random
        + flags
    )
    full_verify_secret = hashlib.sha256(concatenated).digest()

    # Derive keys using HMAC-SHA256(fullVerifySecret, label)
    verifier = hmac.new(full_verify_secret, b"AT", hashlib.sha256).digest()[:16]
    session_key = hmac.new(full_verify_secret, b"SK", hashlib.sha256).digest()[:16]
    pairing_material = hmac.new(full_verify_secret, b"PK", hashlib.sha256).digest()

    # Extract pairing credentials from pairing_material
    pairing_id = struct.unpack("<I", pairing_material[:4])[0]
    pairing_key = pairing_material[4:20]  # 16 bytes

    return verifier, session_key, pairing_key, pairing_id, full_verify_secret
