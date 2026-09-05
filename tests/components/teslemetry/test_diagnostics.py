"""Test the Telemetry Diagnostics."""

import logging
from unittest.mock import AsyncMock

from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.teslemetry.coordinator import VEHICLE_INTERVAL
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from . import setup_platform

from tests.common import async_fire_time_changed
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    snapshot: SnapshotAssertion,
    freezer: FrozenDateTimeFactory,
    mock_legacy: AsyncMock,
) -> None:
    """Test diagnostics."""

    entry = await setup_platform(hass)

    # Wait for coordinator refresh
    freezer.tick(VEHICLE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    diag = await get_diagnostics_for_config_entry(hass, hass_client, entry)
    assert diag == snapshot

    # Enabled polling entities are what keep the vehicle coordinator polling.
    assert diag["vehicles"][0]["polling_entities"]


@pytest.mark.usefixtures("mock_legacy")
async def test_diagnostics_no_polling_entities(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
) -> None:
    """Test diagnostics when no enabled entities keep the coordinator polling."""

    entry = await setup_platform(hass, platforms=[])

    diag = await get_diagnostics_for_config_entry(hass, hass_client, entry)
    assert diag["vehicles"]
    for vehicle in diag["vehicles"]:
        assert vehicle["polling_entities"] == []


@pytest.mark.usefixtures("mock_legacy")
async def test_polling_entities_logged(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test the enabled polling entities are logged at setup."""

    with caplog.at_level(logging.DEBUG, logger="homeassistant.components.teslemetry"):
        await setup_platform(hass, platforms=[Platform.SENSOR])

    assert "polling for enabled entities" in caplog.text
    assert "sensor." in caplog.text
