"""Test the Advantage Air Diagnostics."""

from unittest.mock import AsyncMock

from pytest_homeassistant.components.diagnostics import get_diagnostics_for_config_entry
from pytest_homeassistant.typing import ClientSessionGenerator
from syrupy.assertion import SnapshotAssertion

from homeassistant.core import HomeAssistant

from . import TEST_SYSTEM_DATA_NO_RID, add_mock_config, patch_get


async def test_select_async_setup_entry(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    snapshot: SnapshotAssertion,
    mock_get: AsyncMock,
) -> None:
    """Test select platform."""

    entry = await add_mock_config(hass)
    diag = await get_diagnostics_for_config_entry(hass, hass_client, entry)
    assert diag == snapshot


async def test_diagnostics_redacts_mid(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
) -> None:
    """Test the mid is redacted when the tablet reports no rid."""

    with patch_get(return_value=TEST_SYSTEM_DATA_NO_RID):
        entry = await add_mock_config(hass)
    diag = await get_diagnostics_for_config_entry(hass, hass_client, entry)

    assert diag["system"]["mid"] == "**REDACTED**"
