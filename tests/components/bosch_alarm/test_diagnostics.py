"""Test the Bosch Alarm diagnostics."""

from typing import Any
from unittest.mock import AsyncMock

from bosch_alarm_mode2.const import PanelModel
from syrupy.assertion import SnapshotAssertion

from homeassistant.core import HomeAssistant

from . import setup_integration

from tests.common import MockConfigEntry
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_panel: AsyncMock,
    area: AsyncMock,
    panel_model: PanelModel,
    serial_number: str,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
    config_flow_data: dict[str, Any],
) -> None:
    """Test generating diagnostics for bosch alarm."""
    await setup_integration(hass, mock_config_entry)

    diag = await get_diagnostics_for_config_entry(hass, hass_client, mock_config_entry)
    assert diag == snapshot
