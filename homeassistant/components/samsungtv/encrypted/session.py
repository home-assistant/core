"""SamsungTV Encrypted."""
# flake8: noqa
# pylint: disable=[missing-class-docstring,missing-function-docstring]
import binascii

from Crypto.Cipher import AES

from .command import SamsungTVEncryptedCommand

# Padding for the input string --not related to encryption itself.
_BLOCK_SIZE = 16  # Bytes


def _pad(text: str) -> str:
    return text + (_BLOCK_SIZE - len(text) % _BLOCK_SIZE) * chr(
        _BLOCK_SIZE - len(text) % _BLOCK_SIZE
    )


def _unpad(text: bytes) -> str:
    return text[: -ord(text[len(text) - 1 :])].decode()


class SamsungTVEncryptedSession:
    def __init__(self, token: str, session_id: str) -> None:
        self._token = binascii.unhexlify(token)
        self._session_id = session_id

    def _decrypt(self, enc: bytes) -> str:
        cipher = AES.new(self._token, AES.MODE_ECB)
        return _unpad(cipher.decrypt(binascii.unhexlify(enc)))

    def _encrypt(self, raw: str) -> bytes:
        cipher = AES.new(self._token, AES.MODE_ECB)
        return cipher.encrypt(bytes(_pad(raw), encoding="utf8"))

    def encrypt_command(self, command: SamsungTVEncryptedCommand) -> str:
        command_bytes = self._encrypt(command.get_payload())

        int_array = ",".join(list(map(str, command_bytes)))
        return (
            '5::/com.samsung.companion:{"name":"callCommon","args":[{"Session_Id":'
            + self._session_id
            + ',"body":"['
            + int_array
            + ']"}]}'
        )
