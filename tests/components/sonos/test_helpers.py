"""Test the sonos config flow."""

from __future__ import annotations

import pytest

from homeassistant.components.sonos.helpers import hostname_to_uid


async def test_uid_to_hostname() -> None:
    """Test we can convert a hostname to a uid."""
    assert hostname_to_uid("Sonos-347E5C0CF1E3.local.") == "RINCON_347E5C0CF1E301400"
    assert hostname_to_uid("sonos5CAAFDE47AC8.local.") == "RINCON_5CAAFDE47AC801400"

    with pytest.raises(ValueError):
        assert hostname_to_uid("notsonos5CAAFDE47AC8.local.")
