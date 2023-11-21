"""Tests for the La Marzocco coordinator."""
from unittest.mock import MagicMock

import pytest

from homeassistant.components.lamarzocco.const import DOMAIN
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

pytestmark = pytest.mark.usefixtures("init_integration")


async def test_data_pushed(
    hass: HomeAssistant,
    mock_lamarzocco: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the La Marzocco Coffee Boiler."""
    coordinator = hass.data[DOMAIN][mock_config_entry.entry_id]
    assert coordinator.data
    coordinator._on_data_received()
