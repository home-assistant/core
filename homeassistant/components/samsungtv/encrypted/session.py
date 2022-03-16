"""SamsungTV Encrypted."""
import binascii

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

from .command import SamsungTVEncryptedCommand


# Padding for the input string --not related to encryption itself.
class Padding:
    BLOCK_SIZE = 16  # Bytes

    @staticmethod
    def pad(text: str) -> str:
        return text + (Padding.BLOCK_SIZE - len(text) % Padding.BLOCK_SIZE) * chr(
            Padding.BLOCK_SIZE - len(text) % Padding.BLOCK_SIZE
        )

    @staticmethod
    def unpad(text: bytes) -> str:
        return text[: -ord(text[len(text) - 1 :])].decode()


class SamsungTVEncryptedSession:
    def __init__(self, token: str, session_id: str) -> None:
        self._token = binascii.unhexlify(token)
        self._session_id = session_id
        self._cipher = Cipher(algorithms.AES(self._token), modes.ECB())

    def _decrypt(self, enc: bytes) -> str:
        decryptor = self._cipher.decryptor()
        return Padding.unpad(
            decryptor.update(binascii.unhexlify(enc)) + decryptor.finalize()
        )

    def _encrypt(self, raw: str) -> bytes:
        encryptor = self._cipher.encryptor()
        return (  # type:ignore[no-any-return]
            encryptor.update(bytes(Padding.pad(raw), encoding="utf8"))
            + encryptor.finalize()
        )

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
