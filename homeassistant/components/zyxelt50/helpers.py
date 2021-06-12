
import base64
import json
import logging

from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad

_LOGGER = logging.getLogger(__name__)

def encrypt_request(aes_key, data):
    iv = b'\x42'*16

    cipher = AES.new(aes_key, AES.MODE_CBC, iv)
    content = cipher.encrypt(pad(json.dumps(data).encode('ascii'), 16))

    request = {
        "content": base64.b64encode(content).decode('ascii'),
        "iv": base64.b64encode(iv).decode('ascii'),
        "key": ""
    }

    return request


def decrypt_response(aes_key, data):
    if not 'iv' in data or not 'content' in data:
        _LOGGER.error("Response not encrypted! Response: %s", data)
        return None

    iv = base64.b64decode(data['iv'])[:16]
    content = data['content']

    cipher = AES.new(aes_key, AES.MODE_CBC, iv)

    return unpad(cipher.decrypt(base64.b64decode(content)), 16)
