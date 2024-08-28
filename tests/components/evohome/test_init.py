"""The tests for evohome."""

from __future__ import annotations

from freezegun import freeze_time
import pytest
from syrupy import SnapshotAssertion

from homeassistant.core import HomeAssistant

from .conftest import setup_evohome
from .const import TEST_INSTALLS


@freeze_time("2024-07-10 12:00:00")  # some state attrs are relative the current time
@pytest.mark.parametrize("install", TEST_INSTALLS)
async def test_entities(
    hass: HomeAssistant,
    evo_config: dict[str, str],
    install: str,
    snapshot: SnapshotAssertion,
) -> None:
    """Test entities and state after setup of a Honeywell TCC-compatible system."""

    await setup_evohome(hass, evo_config, install=install)

    assert hass.states.async_all() == snapshot
