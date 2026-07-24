"""Test the Bosch Smart Home Camera diagnostics."""

from syrupy.assertion import SnapshotAssertion

from homeassistant.components.bosch_shc_camera.const import CLOUD_API
from homeassistant.core import HomeAssistant

from . import TEST_BEARER_TOKEN, TEST_REFRESH_TOKEN, setup_integration

from tests.common import MockConfigEntry
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.test_util.aiohttp import AiohttpClientMocker
from tests.typing import ClientSessionGenerator


async def test_entry_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
    snapshot: SnapshotAssertion,
) -> None:
    """A config-entry diagnostics dump matches the snapshot, tokens redacted."""
    aioclient_mock.get(
        f"{CLOUD_API}/v11/video_inputs",
        json=[
            {
                "id": "aabbccdd-1122-3344-5566-778899001122",
                "title": "Terrasse",
                "hardwareVersion": "HOME_Eyes_Outdoor",
                "firmwareVersion": "9.40.104",
                "privacyMode": "OFF",
                "mac": "aa:bb:cc:dd:ee:ff",
            }
        ],
    )
    aioclient_mock.get(f"{CLOUD_API}/v11/feature_flags", json={})
    aioclient_mock.get(f"{CLOUD_API}/protocol_support", json={"state": "SUPPORTED"})

    await setup_integration(hass, config_entry)

    diag = await get_diagnostics_for_config_entry(hass, hass_client, config_entry)

    assert diag == snapshot

    # Tokens must never appear verbatim anywhere in the exported diagnostics —
    # `diagnostics.py`'s `TO_REDACT` set is the actual security boundary here,
    # not just the snapshot equality check above (a stale/regenerated
    # snapshot could otherwise silently re-bake a leak into the fixture).
    raw = repr(diag)
    assert TEST_BEARER_TOKEN not in raw
    assert TEST_REFRESH_TOKEN not in raw
    assert diag["entry"]["data"]["bearer_token"] == "**REDACTED**"
    assert diag["entry"]["data"]["refresh_token"] == "**REDACTED**"
