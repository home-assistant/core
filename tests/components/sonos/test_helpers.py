"""Test the sonos config flow."""
from __future__ import annotations

from homeassistant.components.sonos.helpers import hostname_to_uid


async def test_uid_to_hostname():
    """Test we can convert a hostname to a uid."""
    assert hostname_to_uid("Sonos-347E5C0CF1E3.local.") == "RINCON_347E5C0CF1E301400"
