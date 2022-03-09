"""SamsungTV Encrypted."""
# flake8: noqa
# mypy: ignore-errors
# pylint: disable=[missing-function-docstring,no-self-use]
import binascii

from Crypto.Cipher import AES

# Padding for the input string --not
# related to encryption itself.
BLOCK_SIZE = 16  # Bytes
pad = lambda s: s + (BLOCK_SIZE - len(s) % BLOCK_SIZE) * chr(
    BLOCK_SIZE - len(s) % BLOCK_SIZE
)
unpad = lambda s: s[: -ord(s[len(s) - 1 :])]


class AESCipher:
    """
    Usage:
            c = AESCipher('password').encrypt('message')
            m = AESCipher('password').decrypt(c)
    Tested under Python 3 and PyCrypto 2.6.1.
    """

    def __init__(self, key, session_id):
        self.key = binascii.unhexlify(key)
        self.session_id = session_id

    def decrypt(self, enc):
        cipher = AES.new(self.key, AES.MODE_ECB)
        return unpad(cipher.decrypt(binascii.unhexlify(enc)))

    def encrypt(self, raw):
        cipher = AES.new(self.key, AES.MODE_ECB)
        return cipher.encrypt(bytes(pad(raw), encoding="utf8"))

    def generate_command(self, key_press):
        command_bytes = self.encrypt(self.generate_json(key_press))

        int_array = ",".join(list(map(str, command_bytes)))
        return (
            '5::/com.samsung.companion:{"name":"callCommon","args":[{"Session_Id":'
            + str(self.session_id)
            + ',"body":"['
            + int_array
            + ']"}]}'
        )

    def generate_json(self, key_press):
        return (
            '{"method":"POST","body":{"plugin":"RemoteControl","param1":"uuid:12345","param2":"Click","param3":"'
            + key_press
            + '","param4":false,"api":"SendRemoteKey","version":"1.000"}}'
        )
