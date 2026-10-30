"""Test the Helty Flow Cloud diagnostics."""

from dataclasses import replace
from unittest.mock import AsyncMock

from pyheltycloud import HeltyCloudNoDataError
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.components.diagnostics import get_diagnostics_for_config_entry
from pytest_homeassistant.typing import ClientSessionGenerator
from syrupy.assertion import SnapshotAssertion

from homeassistant.core import HomeAssistant

from . import setup_integration
from .conftest import make_state


async def test_entry_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_helty_cloud: AsyncMock,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test config entry diagnostics."""
    mock_helty_cloud.get_last_telemetry.side_effect = None
    mock_helty_cloud.get_last_telemetry.return_value = replace(
        make_state(), timestamp=1792756800000
    )
    await setup_integration(hass, mock_config_entry)

    assert (
        await get_diagnostics_for_config_entry(hass, hass_client, mock_config_entry)
        == snapshot
    )


async def test_entry_diagnostics_no_data(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_helty_cloud: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test diagnostics of a unit whose panel has not reported yet."""
    mock_helty_cloud.get_last_telemetry.side_effect = HeltyCloudNoDataError
    await setup_integration(hass, mock_config_entry)

    result = await get_diagnostics_for_config_entry(
        hass, hass_client, mock_config_entry
    )

    assert result["devices"][0]["last_update_success"] is False
    assert result["devices"][0]["state"] is None
