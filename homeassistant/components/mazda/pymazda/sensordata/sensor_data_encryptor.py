import base64  # noqa: D100
import random
import secrets

from cryptography.hazmat.primitives import hashes, hmac, padding, serialization
from cryptography.hazmat.primitives.asymmetric import padding as asymmetric_padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

RSA_PUBLIC_KEY = "MIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQKBgQC4sA7vA7N/t1SRBS8tugM2X4bByl0jaCZLqxPOql+qZ3sP4UFayqJTvXjd7eTjMwg1T70PnmPWyh1hfQr4s12oSVphTKAjPiWmEBvcpnPPMjr5fGgv0w6+KM9DLTxcktThPZAGoVcoyM/cTO/YsAMIxlmTzpXBaxddHRwi8S2NvwIDAQAB"


def to_base64_str(bytes):  # noqa: D103
    return base64.b64encode(bytes).decode("utf-8")


class SensorDataEncryptor:  # noqa: D101
    def __init__(self):  # noqa: D107
        self.aes_key = secrets.token_bytes(16)
        self.aes_iv = secrets.token_bytes(16)
        self.hmac_sha256_key = secrets.token_bytes(32)

        public_key = serialization.load_der_public_key(base64.b64decode(RSA_PUBLIC_KEY))
        self.encrypted_aes_key = public_key.encrypt(
            self.aes_key, asymmetric_padding.PKCS1v15()
        )
        self.encrypted_hmac_sha256_key = public_key.encrypt(
            self.hmac_sha256_key, asymmetric_padding.PKCS1v15()
        )

    def encrypt_sensor_data(self, sensor_data):  # noqa: D102
        padder = padding.PKCS7(128).padder()
        padded_data = padder.update(sensor_data.encode()) + padder.finalize()
        cipher = Cipher(algorithms.AES(self.aes_key), modes.CBC(self.aes_iv))
        encryptor = cipher.encryptor()
        encrypted_sensor_data = encryptor.update(padded_data) + encryptor.finalize()

        iv_and_encrypted_sensor_data = self.aes_iv + encrypted_sensor_data

        hmac_obj = hmac.HMAC(self.hmac_sha256_key, hashes.SHA256())
        hmac_obj.update(iv_and_encrypted_sensor_data)
        hmac_result = hmac_obj.finalize()

        result = iv_and_encrypted_sensor_data + hmac_result

        aes_timestamp = random.randrange(0, 3) * 1000
        hmac_timestamp = random.randrange(0, 3) * 1000
        base64_timestamp = random.randrange(0, 3) * 1000

        return f"1,a,{to_base64_str(self.encrypted_aes_key)},{to_base64_str(self.encrypted_hmac_sha256_key)}${to_base64_str(result)}${aes_timestamp},{hmac_timestamp},{base64_timestamp}"
