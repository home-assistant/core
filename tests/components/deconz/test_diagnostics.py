"""Test deCONZ diagnostics."""
from pydeconz.websocket import State
from syrupy import SnapshotAssertion

from homeassistant.core import HomeAssistant

from .test_gateway import setup_deconz_integration

from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.test_util.aiohttp import AiohttpClientMocker
from tests.typing import ClientSessionGenerator


async def test_entry_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    mock_deconz_websocket,
    snapshot: SnapshotAssertion,
) -> None:
    """Test config entry diagnostics."""
    config_entry = await setup_deconz_integration(hass, aioclient_mock)

    await mock_deconz_websocket(state=State.RUNNING)
    await hass.async_block_till_done()

    assert (
        await get_diagnostics_for_config_entry(hass, hass_client, config_entry)
        == snapshot
    )
