"""Test Rako Utils."""

from homeassistant.components.rako.util import create_unique_id, hash_dict

from tests.components.rako import MOCK_ENTITY_ID


def test_create_unique_id():
    """Test creating unique id."""
    assert f"b:{MOCK_ENTITY_ID}r:1c:1" == create_unique_id(MOCK_ENTITY_ID, 1, 1)


def test_hash_bridge_info():
    """Test hashing a dict."""
    bi = {
        "version": "2.4.0 RA",
        "buildDate": "Nov 17 2017 10:01:01",
        "hostName": "RAKOBRIDGE",
        "hostIP": "someip",
        "hostMAC": "somemac",
        "hwStatus": "05",
        "dbVersion": "-31",
        "requirepassword": None,
        "passhash": "NAN",
        "charset": "UTF-8",
    }

    res = hash_dict(bi)
    assert res == "58154ddb52"
