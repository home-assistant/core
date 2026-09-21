"""Tests for the Bosch SHC sensor platform."""

from collections.abc import Generator
from unittest.mock import MagicMock, patch

import pytest

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_component import async_update_entity

from .conftest import setup_integration

from tests.common import MockConfigEntry


@pytest.fixture(autouse=True)
def platforms() -> Generator[None]:
    """Restrict bosch_shc setup to the sensor platform."""
    with patch("homeassistant.components.bosch_shc.PLATFORMS", [Platform.SENSOR]):
        yield


@pytest.mark.usefixtures("mock_session")
async def test_open_windows_doors_sensor(
    hass: HomeAssistant,
    mock_session: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """The whole-home open-doors/open-windows summary is exposed and polled."""
    mock_session.api.get_open_windows.return_value = {
        "openDoors": [{"name": "Front Door"}],
        "openWindows": [{"name": "Kitchen Window"}, {"name": "Bedroom Window"}],
        "openOthers": [],
    }
    await setup_integration(hass, mock_config_entry)
    await async_update_entity(hass, "sensor.mock_title_open_doors_and_windows")
    await hass.async_block_till_done()

    state = hass.states.get("sensor.mock_title_open_doors_and_windows")
    assert state is not None
    assert state.state == "3"
    assert state.attributes["open_doors"] == ["Front Door"]
    assert state.attributes["open_windows"] == ["Kitchen Window", "Bedroom Window"]
    assert state.attributes["open_others"] == []
