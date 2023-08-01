"""Test the Advantage Air Diagnostics."""
from syrupy.assertion import SnapshotAssertion

from homeassistant.core import HomeAssistant

from . import (
    TEST_SYSTEM_DATA,
    TEST_SYSTEM_URL,
    add_mock_config,
)

from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.test_util.aiohttp import AiohttpClientMocker
from tests.typing import ClientSessionGenerator


async def test_select_async_setup_entry(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    snapshot: SnapshotAssertion,
) -> None:
    """Test select platform."""

    aioclient_mock.get(
        TEST_SYSTEM_URL,
        text=TEST_SYSTEM_DATA,
    )

    entry = await add_mock_config(hass)
    diag = await get_diagnostics_for_config_entry(hass, hass_client, entry)
    assert diag == snapshot
