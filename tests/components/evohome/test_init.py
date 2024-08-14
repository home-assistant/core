"""The tests for evohome."""

from __future__ import annotations

import pytest
from syrupy import SnapshotAssertion

from homeassistant.core import HomeAssistant

from .conftest import setup_evohome
from .const import TEST_INSTALLS


@pytest.mark.parametrize("install", TEST_INSTALLS)
async def test_vendor_json(
    hass: HomeAssistant,
    evo_config: dict[str, str],
    install: str,
    snapshot: SnapshotAssertion,
) -> None:
    """Test setup of a Honeywell TCC-compatible system."""

    await setup_evohome(hass, evo_config, install=install)

    assert hass.states.async_all() == snapshot
