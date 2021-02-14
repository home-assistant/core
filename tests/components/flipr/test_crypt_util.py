"""Test the crypt util methods."""

from homeassistant.components.flipr.crypt_util import decrypt_data, encrypt_data

TEST_DATA = "MY_Pas$word!6_:)"


async def test_encrypt_and_decrypt():
    """Test normal case."""
    encrypted = encrypt_data(TEST_DATA)
    print("Encrypted data = " + encrypted)
    decrypted = decrypt_data(encrypted)
    print("Decrypted data = " + decrypted)
    assert decrypted == TEST_DATA


async def test_encrypt_and_decrypt_custom_key():
    """Test normal case custom key."""
    key = "TOTO_est_rigolo"
    encrypted = encrypt_data(TEST_DATA, key)
    decrypted = decrypt_data(encrypted, key)
    assert decrypted == TEST_DATA
    key = "small"
    encrypted = encrypt_data(TEST_DATA, key)
    decrypted = decrypt_data(encrypted, key)
    assert decrypted == TEST_DATA
