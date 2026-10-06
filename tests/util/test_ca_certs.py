"""Test the CA certificates helper."""

import ssl

import certifi

from homeassistant.util.ca_certs import certifi_ca_data


def test_certifi_ca_data() -> None:
    """Test the certifi CA data matches the certifi bundle and is cached."""
    expected = ssl.create_default_context(cafile=certifi.where())
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.load_verify_locations(cadata=certifi_ca_data())

    assert context.cert_store_stats() == expected.cert_store_stats()
    assert certifi_ca_data() is certifi_ca_data()
