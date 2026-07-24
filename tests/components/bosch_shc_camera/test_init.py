"""Test the Bosch Smart Home Camera setup/unload/migration lifecycle."""

from homeassistant.components.bosch_shc_camera.const import CLOUD_API, DOMAIN
from homeassistant.components.bosch_shc_camera.coordinator import BoschCameraCoordinator
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from . import setup_integration

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker


def _mock_bootstrap_endpoints(
    aioclient_mock: AiohttpClientMocker,
    *,
    video_inputs_status: int = 200,
    video_inputs: list[dict[str, object]] | None = None,
) -> None:
    """Register the mocks every coordinator first-tick unconditionally needs.

    `GET /v11/video_inputs`, `GET /v11/feature_flags` and
    `GET /protocol_support` all fire on the very first coordinator tick
    (`tick_bootstrap.py` + `camera_list.py`) — any test that reaches
    `setup_integration()` needs all three mocked or the tick raises
    `AssertionError` from `AiohttpClientMocker.match_request`.
    """
    aioclient_mock.get(
        f"{CLOUD_API}/v11/video_inputs",
        status=video_inputs_status,
        json=video_inputs if video_inputs is not None else [],
    )
    aioclient_mock.get(f"{CLOUD_API}/v11/feature_flags", json={})
    aioclient_mock.get(f"{CLOUD_API}/protocol_support", json={"state": "SUPPORTED"})


async def test_setup_entry_success(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """A clean setup reaches LOADED and stores a coordinator on runtime_data."""
    _mock_bootstrap_endpoints(aioclient_mock)

    await setup_integration(hass, config_entry)

    assert config_entry.state is ConfigEntryState.LOADED
    assert isinstance(config_entry.runtime_data, BoschCameraCoordinator)


async def test_unload_entry(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Unloading tears the entry back down to NOT_LOADED and clears runtime_data."""
    _mock_bootstrap_endpoints(aioclient_mock)
    await setup_integration(hass, config_entry)
    assert config_entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.NOT_LOADED
    # HA-core clears `entry.runtime_data` automatically once every platform
    # has unloaded (Bronze quality-scale `runtime-data` rule) — the attribute
    # itself is removed (not merely set to None), so getattr is required
    # here. Asserting via this public attribute avoids poking at coordinator
    # internals.
    assert getattr(config_entry, "runtime_data", None) is None


async def test_reload_entry(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """A reload tears down and re-creates the coordinator, ending up LOADED."""
    _mock_bootstrap_endpoints(aioclient_mock)
    await setup_integration(hass, config_entry)
    first_coordinator = config_entry.runtime_data

    assert await hass.config_entries.async_reload(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED
    assert isinstance(config_entry.runtime_data, BoschCameraCoordinator)
    assert config_entry.runtime_data is not first_coordinator


async def test_setup_entry_cloud_error_no_registry_fallback(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """A first-ever setup with no cached entities re-raises ConfigEntryNotReady.

    `async_setup_entry` (`__init__.py`) tolerates a first-refresh cloud
    failure by rehydrating cameras from the entity registry so LAN-fallback
    entities still come up — but a truly first-time install (nothing in the
    registry yet) has nothing to rehydrate from and must fall through to
    HA-core's standard setup-failed/retry handling instead of silently
    loading with zero entities.
    """
    _mock_bootstrap_endpoints(aioclient_mock, video_inputs_status=500)

    await setup_integration(hass, config_entry)

    assert config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_migrate_entry_v1_to_v3(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """A v1 entry is migrated to v3, preserving auto stream type + clearing legacy FCM."""
    _mock_bootstrap_endpoints(aioclient_mock)
    old_entry = MockConfigEntry(
        domain=DOMAIN,
        title="Bosch Smart Home Camera",
        unique_id=DOMAIN,
        version=1,
        data={
            "bearer_token": "test-bearer-token",
            "refresh_token": "test-refresh-token",
            "fcm_credentials": {"token": "stale"},
            "fcm_registered_token": "stale-token",
        },
        options={"fcm_push_mode": "ios"},
    )

    await setup_integration(hass, old_entry)

    assert old_entry.state is ConfigEntryState.LOADED
    assert old_entry.version == 3
    assert old_entry.options["stream_connection_type"] == "auto"
    assert old_entry.options["fcm_push_mode"] == "auto"
    assert "fcm_credentials" not in old_entry.data
    assert "fcm_registered_token" not in old_entry.data


async def test_migrate_entry_v2_to_v3_preserves_non_legacy_fcm_mode(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """A v2 entry already on the current fcm_push_mode='polling' is left untouched by the FCM rewrite."""
    _mock_bootstrap_endpoints(aioclient_mock)
    old_entry = MockConfigEntry(
        domain=DOMAIN,
        title="Bosch Smart Home Camera",
        unique_id=DOMAIN,
        version=2,
        data={
            "bearer_token": "test-bearer-token",
            "refresh_token": "test-refresh-token",
        },
        options={"fcm_push_mode": "polling", "stream_connection_type": "local"},
    )

    await setup_integration(hass, old_entry)

    assert old_entry.state is ConfigEntryState.LOADED
    assert old_entry.version == 3
    assert old_entry.options["fcm_push_mode"] == "polling"
    assert old_entry.options["stream_connection_type"] == "local"
