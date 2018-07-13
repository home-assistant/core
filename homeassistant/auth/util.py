"""Auth utils."""
import binascii
import os


def generate_secret(entropy: int = 32) -> str:
    """Generate a secret.

    Backport of secrets.token_hex from Python 3.6

    Event loop friendly.
    """
    return binascii.hexlify(os.urandom(entropy)).decode('ascii')
