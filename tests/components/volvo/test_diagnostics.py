"""Test Volvo diagnostics."""

from collections.abc import Awaitable, Callable

import pytest
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.components.diagnostics import get_diagnostics_for_config_entry
from pytest_homeassistant.typing import ClientSessionGenerator
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import CONF_TOKEN
from homeassistant.core import HomeAssistant


@pytest.mark.usefixtures("mock_api")
async def test_entry_diagnostics(
    hass: HomeAssistant,
    setup_integration: Callable[[], Awaitable[bool]],
    hass_client: ClientSessionGenerator,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test config entry diagnostics."""

    assert await setup_integration()
    await hass.async_block_till_done()

    # Give it a fixed timestamp so it won't change with every test run
    mock_config_entry.data[CONF_TOKEN]["expires_at"] = 1759919745.7328658

    assert (
        await get_diagnostics_for_config_entry(hass, hass_client, mock_config_entry)
        == snapshot
    )
