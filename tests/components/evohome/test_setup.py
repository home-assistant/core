"""The tests for evohome."""

from __future__ import annotations

import pytest

from homeassistant.core import HomeAssistant

from .conftest import setup_evohome


@pytest.mark.parametrize("installation", ["minimal", "default", "h032585"])
async def test_vendor_json(hass: HomeAssistant, installation: str) -> None:
    """Test loading/saving authentication tokens when no cached tokens in the store."""

    await setup_evohome(hass, installation=installation)
