import base64  # noqa: D100
import hashlib

from cryptography.hazmat.primitives import padding, serialization
from cryptography.hazmat.primitives.asymmetric import padding as asymmetric_padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes


def encrypt_aes128cbc_buffer_to_base64_str(data, key, iv):  # noqa: D103
    padder = padding.PKCS7(128).padder()
    padded_data = padder.update(data) + padder.finalize()
    cipher = Cipher(algorithms.AES(key.encode("ascii")), modes.CBC(iv.encode("ascii")))
    encryptor = cipher.encryptor()
    encrypted = encryptor.update(padded_data) + encryptor.finalize()
    return base64.b64encode(encrypted).decode("utf-8")


def decrypt_aes128cbc_buffer_to_str(data, key, iv):  # noqa: D103
    cipher = Cipher(algorithms.AES(key.encode("ascii")), modes.CBC(iv.encode("ascii")))
    decryptor = cipher.decryptor()
    decrypted = decryptor.update(data) + decryptor.finalize()
    unpadder = padding.PKCS7(128).unpadder()
    return unpadder.update(decrypted) + unpadder.finalize()


def encrypt_rsaecbpkcs1_padding(data, public_key):  # noqa: D103
    public_key = serialization.load_der_public_key(base64.b64decode(public_key))
    return public_key.encrypt(data.encode("utf-8"), asymmetric_padding.PKCS1v15())


def generate_uuid_from_seed(seed):  # noqa: D103
    hash = hashlib.sha256(seed.encode()).hexdigest().upper()
    return (
        hash[0:8]
        + "-"
        + hash[8:12]
        + "-"
        + hash[12:16]
        + "-"
        + hash[16:20]
        + "-"
        + hash[20:32]
    )


def generate_usher_device_id_from_seed(seed):  # noqa: D103
    hash = hashlib.sha256(seed.encode()).hexdigest().upper()
    id = int(hash[0:8], 16)
    return "ACCT" + str(id)
