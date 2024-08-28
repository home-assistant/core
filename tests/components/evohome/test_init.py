"""The tests for evohome."""

from __future__ import annotations

from datetime import datetime

import pytest
from syrupy import SnapshotAssertion

from homeassistant.core import HomeAssistant

from .conftest import setup_evohome
from .const import TEST_INSTALLS

from tests.common import async_fire_time_changed


@pytest.mark.parametrize("install", TEST_INSTALLS)
async def test_entities(
    hass: HomeAssistant,
    evo_config: dict[str, str],
    install: str,
    snapshot: SnapshotAssertion,
) -> None:
    """Test entities and state after setup of a Honeywell TCC-compatible system."""

    # some of the extended state attrs are relative the current time
    async_fire_time_changed(hass, datetime(2024, 7, 10, 12, 0, 0))

    await setup_evohome(hass, evo_config, install=install)

    assert hass.states.async_all() == snapshot
