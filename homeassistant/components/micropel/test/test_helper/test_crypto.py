"""Test of cryptography."""
from ...helper.crypto import Crypto


def test_encrypt_decrypt_test():
    """Test encoding and decoding."""

    original_str = "Sww=BRDqXPgX5ytH"
    exp_str_pass1 = "Ffz7WCI{MAjR hyB"
    exp_str_pass999999 = 'Mgf"\\BUnF@vG+ieW'

    cryptography = Crypto()

    cryptography.crypt_init(1)
    encoded_str = cryptography.code_string(original_str)
    assert exp_str_pass1 == encoded_str
    decoded_str = cryptography.decode_string(encoded_str)
    assert original_str == decoded_str

    cryptography.crypt_init(999999)
    encoded_str = cryptography.code_string(original_str)
    assert exp_str_pass999999 == encoded_str
    decoded_str = cryptography.decode_string(encoded_str)
    assert original_str == decoded_str

    cryptography.crypt_init(0)
    encoded_str = cryptography.code_string(original_str)
    assert original_str == encoded_str
    decoded_str = cryptography.decode_string(encoded_str)
    assert original_str == decoded_str

    cryptography.crypt_init(-1)
    encoded_str = cryptography.code_string(original_str)
    assert original_str == encoded_str
    decoded_str = cryptography.decode_string(encoded_str)
    assert original_str == decoded_str
