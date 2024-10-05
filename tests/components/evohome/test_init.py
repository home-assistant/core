"""The tests for evohome."""

from __future__ import annotations

from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy import SnapshotAssertion

from homeassistant.core import HomeAssistant

from .conftest import setup_evohome
from .const import TEST_INSTALLS


@pytest.mark.parametrize("install", [*TEST_INSTALLS, "botched"])
async def test_entities(
    hass: HomeAssistant,
    config: dict[str, str],
    install: str,
    snapshot: SnapshotAssertion,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test entities and state after setup of a Honeywell TCC-compatible system."""

    # some extended state attrs are relative the current time
    freezer.move_to("2024-07-10T12:00:00Z")

    async for _ in setup_evohome(hass, config, install=install):
        pass

    assert hass.states.async_all() == snapshot
