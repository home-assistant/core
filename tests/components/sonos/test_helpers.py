"""Test the sonos config flow."""
from __future__ import annotations

from homeassistant.components.sonos.helpers import (
    hostname_to_uid,
    uid_to_short_hostname,
)


async def test_uid_to_short_hostname():
    """Test we can convert a uid to a short hostname."""
    assert uid_to_short_hostname("RINCON_347E5C0CF1E301400") == "Sonos-347E5C0CF1E3"


async def test_uid_to_hostname():
    """Test we can convert a hostname to a uid."""
    assert hostname_to_uid("Sonos-347E5C0CF1E3.local.") == "RINCON_347E5C0CF1E301400"
