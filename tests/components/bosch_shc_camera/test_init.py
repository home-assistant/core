"""Integration tests for config entry setup/unload.

The coordinator's `_async_update_data` is the integration's sole network
boundary (GET /v11/video_inputs et al. against Bosch's cloud) — patched
here instead of mocking aiohttp directly, since cloud_ssl.py builds its own
pinned-TLS ClientSession outside of `async_create_clientsession` and so
isn't reachable via the standard `aioclient_mock` fixture.
"""

from unittest.mock import patch

from homeassistant.components.bosch_shc_camera.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

CAM_ID = "AABBCCDD-1122-3344-5566-778899001122"

FAKE_COORDINATOR_DATA = {
    CAM_ID: {
        "info": {
            "title": "Front Door",
            "hardwareVersion": "HOME_Eyes_Outdoor",
            "firmwareVersion": "9.40.104",
            "macAddress": "aa:bb:cc:dd:ee:ff",
        },
        "status": "ONLINE",
        "events": [],
    }
}


def _mock_config_entry() -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id=DOMAIN,
        data={
            "bearer_token": "test-bearer-token",
            "refresh_token": "test-refresh-token",
        },
        options={},
    )


async def test_setup_and_unload_entry(hass: HomeAssistant) -> None:
    """A config entry with a mocked coordinator refresh loads a camera entity and unloads cleanly."""
    entry = _mock_config_entry()
    entry.add_to_hass(hass)

    coordinator_path = (
        "homeassistant.components.bosch_shc_camera.coordinator.BoschCameraCoordinator"
    )
    with (
        patch(
            f"{coordinator_path}._async_update_data",
            return_value=FAKE_COORDINATOR_DATA,
        ),
        # The camera entity fires a background snapshot refresh on startup —
        # these are the coordinator's real network-touching snapshot methods,
        # stubbed here so the test never opens a real socket.
        patch(f"{coordinator_path}.async_fetch_live_snapshot", return_value=None),
        patch(f"{coordinator_path}.async_fetch_live_snapshot_local", return_value=None),
        patch(
            f"{coordinator_path}.async_fetch_fresh_event_snapshot", return_value=None
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        assert entry.state is ConfigEntryState.LOADED

        state = hass.states.get("camera.bosch_front_door")
        assert state is not None

        assert await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()

        assert entry.state is ConfigEntryState.NOT_LOADED
        # Unloading marks the entity unavailable — it does not remove it from
        # hass.states (that only happens on config entry *removal*).
        state = hass.states.get("camera.bosch_front_door")
        assert state is not None
        assert state.state == "unavailable"


async def test_setup_entry_without_any_token_fails(hass: HomeAssistant) -> None:
    """A config entry with no bearer/refresh token needs re-authentication.

    ConfigEntryAuthFailed (not UpdateFailed) so HA starts the native reauth
    flow instead of retrying a non-transient condition forever
    (bug-hunt 2026-07-27, Copilot review round 3).
    """
    entry = MockConfigEntry(domain=DOMAIN, unique_id=DOMAIN, data={}, options={})
    entry.add_to_hass(hass)

    assert not await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_ERROR
