"""Test coordinator behavior for madVR Envy."""

from __future__ import annotations

from madvr_envy.adapter import AdapterEvent, EnvySnapshot
from tests.common import async_capture_events

from homeassistant.components.madvr.coordinator import MadvrEnvyCoordinator


async def test_coordinator_start_stop(hass, mock_envy_client):
    """Test coordinator startup and shutdown lifecycle."""
    coordinator = MadvrEnvyCoordinator(hass, mock_envy_client, sync_timeout=5.0)

    await coordinator.async_start()

    mock_envy_client.register_adapter_callback.assert_called_once()
    mock_envy_client.register_callback.assert_called_once()
    mock_envy_client.start.assert_called_once()
    mock_envy_client.wait_synced.assert_called_once_with(timeout=5.0)
    mock_envy_client.get_mac_address.assert_awaited_once()
    mock_envy_client.get_temperatures.assert_awaited_once()
    mock_envy_client.enum_profile_groups_collect.assert_awaited_once()
    mock_envy_client.enum_profiles_collect.assert_awaited_once_with("1")

    assert coordinator.data is not None
    assert coordinator.data["available"] is True
    assert coordinator.data["power_state"] == "on"

    await coordinator.async_shutdown()

    mock_envy_client.deregister_adapter_callback.assert_called_once()
    mock_envy_client.deregister_callback.assert_called_once()
    mock_envy_client.stop.assert_called_once()


async def test_coordinator_push_update_and_event_forwarding(hass, mock_envy_client):
    """Test bridge updates update coordinator state and emit events."""
    captured = async_capture_events(hass, "madvr.system_action")

    coordinator = MadvrEnvyCoordinator(hass, mock_envy_client)
    await coordinator.async_start()

    callback = mock_envy_client._test_callbacks["adapter"]
    snapshot = EnvySnapshot(
        synced=True,
        version="1.0.1",
        is_on=True,
        standby=False,
        signal_present=True,
        mac_address="00:11:22:33:44:55",
        active_profile_group="1",
        active_profile_index=1,
        current_menu=None,
        aspect_ratio_mode=None,
        incoming_signal=None,
        outgoing_signal=None,
        aspect_ratio=None,
        masking_ratio=None,
        tone_map_enabled=False,
        temperatures=(45, 40, 47, 39),
        settings_pages=(),
        config_pages=(),
        profile_groups=(("1", "Cinema"),),
        profiles=(("1_1", "Day"),),
        options=(),
        last_system_action="Restart",
        last_button_event=None,
        last_inherit_option_path=None,
        last_inherit_option_effective=None,
        last_uploaded_3dlut=None,
        last_renamed_3dlut=None,
        last_deleted_3dlut=None,
        last_store_settings=None,
        last_restore_settings=None,
        temporary_reset_count=0,
        display_changed_count=0,
        settings_upload_count=0,
    )

    callback(snapshot, [], [AdapterEvent(kind="system_action", payload={"action": "Restart"})])
    await hass.async_block_till_done()

    assert coordinator.data is not None
    assert coordinator.data["version"] == "1.0.1"
    assert coordinator.data["tone_map_enabled"] is False
    assert captured[-1].data == {"action": "Restart"}

    await coordinator.async_shutdown()


async def test_coordinator_marks_unavailable_on_disconnect(hass, mock_envy_client):
    """Test disconnect events force availability false."""
    coordinator = MadvrEnvyCoordinator(hass, mock_envy_client)
    await coordinator.async_start()

    client_callback = mock_envy_client._test_callbacks["client"]
    client_callback("disconnected", None)
    assert coordinator.data is not None
    assert coordinator.data["available"] is False

    client_callback("connected", None)
    assert coordinator.data["available"] is True

    await coordinator.async_shutdown()


async def test_coordinator_prime_failure_is_non_fatal(hass, mock_envy_client):
    """Test startup continues when priming commands fail."""
    mock_envy_client.enum_profile_groups_collect.side_effect = TimeoutError
    coordinator = MadvrEnvyCoordinator(hass, mock_envy_client)

    await coordinator.async_start()
    assert coordinator.data is not None
    assert coordinator.data["available"] is True

    await coordinator.async_shutdown()
