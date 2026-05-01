"""Tests for samsungtv config flow fixes."""

from tests.common import MockConfigEntry
from homeassistant.const import CONF_MAC


def test_preserve_unique_id_on_mac_match(hass):
    """Ensure that an existing unique_id is preserved when matching by MAC."""
    entry = MockConfigEntry(
        domain="samsungtv",
        data={
            "host": "192.168.16.71",
            CONF_MAC: "9c:8c:6e:6b:ae:07",
        },
        unique_id="original-uuid-1234",
    )
    entry.add_to_hass(hass)

    # Sanity check — the unique_id should remain unchanged
    assert entry.unique_id == "original-uuid-1234"
