"""Regression tests closing coverage gaps in `bosch_shc_camera/__init__.py`.

Targets specific setup/unload/migration code paths not already exercised by
`test_init.py`: registry-rehydration branches, the v11.0.0 doubled-prefix and
v12.4.10 stale-entity migrations, persisted-cache loading, hw_version
registry rehydration, the true-first-install `ConfigEntryNotReady` re-raise,
HA-stop teardown, and `_async_options_updated`'s reload-vs-skip decision.
"""

import base64
import json
import time
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.bosch_shc_camera import (
    OPTIONS_SNAPSHOT_KEY,
    _async_options_updated,
)
from homeassistant.components.bosch_shc_camera.const import DOMAIN
from homeassistant.components.bosch_shc_camera.coordinator import get_options
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import (
    device_registry as dr,
    entity_registry as er,
    issue_registry as ir,
)
from homeassistant.helpers.storage import Store

from tests.common import MockConfigEntry

CAM_ID = "AABBCCDD-1122-3344-5566-778899001122"
OTHER_CAM_ID = "11223344-5566-7788-99AA-BBCCDDEEFF00"

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

COORDINATOR_PATH = (
    "homeassistant.components.bosch_shc_camera.coordinator.BoschCameraCoordinator"
)


def _fake_jwt(expires_in: int = 3600) -> str:
    """Build a minimal (unsigned) JWT-shaped token with a real `exp` claim.

    `schedule_token_refresh` only arms its proactive-refresh timer when
    `self.token` parses as a 2+-part base64 JWT with a decodable payload.
    """
    payload = (
        base64.urlsafe_b64encode(json.dumps({"exp": time.time() + expires_in}).encode())
        .decode()
        .rstrip("=")
    )
    return f"header.{payload}.signature"


def _mock_config_entry() -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id=DOMAIN,
        data={
            "bearer_token": _fake_jwt(),
            "refresh_token": "test-refresh-token",
        },
        options={},
    )


async def _setup_healthy_entry(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    """Set up `entry` with a healthy, mocked coordinator refresh."""
    with (
        patch(
            f"{COORDINATOR_PATH}._async_update_data",
            return_value=FAKE_COORDINATOR_DATA,
        ),
        patch(f"{COORDINATOR_PATH}.async_fetch_live_snapshot", return_value=None),
        patch(f"{COORDINATOR_PATH}.async_fetch_live_snapshot_local", return_value=None),
        patch(
            f"{COORDINATOR_PATH}.async_fetch_fresh_event_snapshot", return_value=None
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()


async def test_rehydrate_name_by_user_wins_and_repairs_uuid_placeholder(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """`name_by_user` wins over a UUID-placeholder `device.name`, which gets repaired.

    Covers `_rehydrate_cams_from_registry`'s name_by_user branch and the
    stale-`Bosch <UUID>`-placeholder repair, both only reachable on a
    cloud-degraded cold start.
    """
    entry = _mock_config_entry()
    entry.add_to_hass(hass)

    dreg = device_registry
    device = dreg.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, CAM_ID)},
        name=f"Bosch {CAM_ID}",
    )
    dreg.async_update_device(device.id, name_by_user="Bosch Terrasse")

    ereg = entity_registry
    ereg.async_get_or_create(
        domain="camera",
        platform=DOMAIN,
        unique_id=f"bosch_shc_cam_{CAM_ID.lower()}",
        config_entry=entry,
        device_id=device.id,
    )

    with (
        patch(
            f"{COORDINATOR_PATH}.async_config_entry_first_refresh",
            side_effect=ConfigEntryNotReady("cloud down"),
        ),
        patch(f"{COORDINATOR_PATH}.async_outage_ping_all", return_value=None),
        patch(
            f"{COORDINATOR_PATH}.spawn_tracked", side_effect=lambda c, **_: c.close()
        ),
        patch(f"{COORDINATOR_PATH}.async_fetch_live_snapshot", return_value=None),
        patch(f"{COORDINATOR_PATH}.async_fetch_live_snapshot_local", return_value=None),
        patch(
            f"{COORDINATOR_PATH}.async_fetch_fresh_event_snapshot", return_value=None
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert entry.runtime_data.data[CAM_ID]["info"]["title"] == "Terrasse"

    repaired = dreg.async_get(device.id)
    assert repaired is not None
    assert repaired.name == "Bosch Terrasse"


async def test_rehydrate_derives_title_from_camera_entity_slug(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """No device exists — title falls back to the camera entity_id's slug."""
    entry = _mock_config_entry()
    entry.add_to_hass(hass)

    ereg = entity_registry
    ereg.async_get_or_create(
        domain="camera",
        platform=DOMAIN,
        unique_id=f"bosch_shc_cam_{CAM_ID.lower()}",
        config_entry=entry,
        suggested_object_id="bosch_garten",
    )

    with (
        patch(
            f"{COORDINATOR_PATH}.async_config_entry_first_refresh",
            side_effect=ConfigEntryNotReady("cloud down"),
        ),
        patch(f"{COORDINATOR_PATH}.async_outage_ping_all", return_value=None),
        patch(
            f"{COORDINATOR_PATH}.spawn_tracked", side_effect=lambda c, **_: c.close()
        ),
        patch(f"{COORDINATOR_PATH}.async_fetch_live_snapshot", return_value=None),
        patch(f"{COORDINATOR_PATH}.async_fetch_live_snapshot_local", return_value=None),
        patch(
            f"{COORDINATOR_PATH}.async_fetch_fresh_event_snapshot", return_value=None
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.runtime_data.data[CAM_ID]["info"]["title"] == "Garten"


async def test_first_install_reraises_when_no_registry_to_fall_back_to(
    hass: HomeAssistant,
) -> None:
    """A truly first-time install with a cloud outage has nothing to rehydrate from.

    `_async_first_refresh_with_fallback` must re-raise `ConfigEntryNotReady`
    (HA then retries setup) instead of silently continuing with zero
    cameras.
    """
    entry = _mock_config_entry()
    entry.add_to_hass(hass)

    with patch(
        f"{COORDINATOR_PATH}.async_config_entry_first_refresh",
        side_effect=ConfigEntryNotReady("cloud down"),
    ):
        assert not await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_doubled_prefix_migration_renames_and_skips_collision(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
) -> None:
    """The v11.0.0 doubled-prefix migration renames a clean match.

    A second buggy entity whose corrected target entity_id is already taken
    is left untouched instead of raising, and the migration issue is
    created describing the rename.
    """
    entry = _mock_config_entry()
    entry.add_to_hass(hass)

    ereg = entity_registry
    ereg.async_get_or_create(
        domain="light",
        platform=DOMAIN,
        unique_id="bosch_shc_cam_garten_light",
        config_entry=entry,
        suggested_object_id="bosch_garten_bosch_garten_camera_light",
    )
    # Collision: the corrected target id is already registered by something
    # else, so the rename must be skipped rather than raising.
    ereg.async_get_or_create(
        domain="button",
        platform=DOMAIN,
        unique_id="bosch_shc_cam_est_refresh",
        config_entry=entry,
        suggested_object_id="bosch_est_refresh_snapshot",
    )
    ereg.async_get_or_create(
        domain="button",
        platform=DOMAIN,
        unique_id="bosch_shc_cam_est_refresh_buggy",
        config_entry=entry,
        suggested_object_id="bosch_est_bosch_est_refresh_snapshot",
    )

    await _setup_healthy_entry(hass, entry)

    assert entry.state is ConfigEntryState.LOADED
    assert ereg.async_get("light.bosch_garten_camera_light") is not None
    assert ereg.async_get("light.bosch_garten_bosch_garten_camera_light") is None
    # Collision case: buggy entity survives untouched.
    assert ereg.async_get("button.bosch_est_bosch_est_refresh_snapshot") is not None

    issue = issue_registry.async_get_issue(DOMAIN, "doubled_prefix_entity_ids_migrated")
    assert issue is not None


async def test_doubled_prefix_migration_truncates_examples_beyond_five(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
) -> None:
    """More than 5 renamed entities truncate the issue's example list with an ellipsis."""
    entry = _mock_config_entry()
    entry.add_to_hass(hass)

    ereg = entity_registry
    for i in range(6):
        ereg.async_get_or_create(
            domain="button",
            platform=DOMAIN,
            unique_id=f"bosch_shc_cam_cam{i}_refresh",
            config_entry=entry,
            suggested_object_id=f"bosch_cam{i}_bosch_cam{i}_refresh_snapshot",
        )

    await _setup_healthy_entry(hass, entry)

    assert entry.state is ConfigEntryState.LOADED

    issue = issue_registry.async_get_issue(DOMAIN, "doubled_prefix_entity_ids_migrated")
    assert issue is not None
    assert issue.translation_placeholders is not None
    assert issue.translation_placeholders["count"] == "6"
    assert issue.translation_placeholders["examples"].endswith(", …")


async def test_persisted_caches_loaded_and_malformed_local_creds_skipped(
    hass: HomeAssistant,
) -> None:
    """Persisted cloud-alert / LAN-IP / hw-version caches load onto the coordinator.

    Also covers a malformed (non-dict) persisted LOCAL-creds record being
    skipped instead of crashing setup.
    """
    entry = _mock_config_entry()
    entry.add_to_hass(hass)

    await Store(hass, version=1, key=f"{DOMAIN}_cloud_alert_state").async_save(
        {"outage_notified": True}
    )
    await Store(hass, version=1, key=f"{DOMAIN}_lan_ips").async_save(
        {CAM_ID: "192.168.1.42"}
    )
    await Store(hass, version=1, key=f"{DOMAIN}_hw_versions").async_save(
        {CAM_ID: "HOME_Eyes_Indoor"}
    )
    await Store(hass, version=1, key=f"{DOMAIN}_local_creds").async_save(
        {CAM_ID: "not-a-dict"}
    )

    await _setup_healthy_entry(hass, entry)

    coordinator = entry.runtime_data
    assert coordinator.cloud_outage_notified is True
    assert coordinator.rcp_lan_ip_cache[CAM_ID.upper()] == "192.168.1.42"
    assert coordinator.hw_version[CAM_ID.upper()] == "HOME_Eyes_Indoor"
    assert CAM_ID.upper() not in coordinator.local_creds_cache


async def test_indoor_ii_orphan_entities_removed_only_for_indoor_cams(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """v12.5.1 migration removes Indoor-II-only orphan entities, scoped per camera.

    An orphan-suffixed entity belonging to a non-Indoor-II camera is left
    alone.
    """
    entry = _mock_config_entry()
    entry.add_to_hass(hass)

    await Store(hass, version=1, key=f"{DOMAIN}_hw_versions").async_save(
        {CAM_ID: "HOME_Eyes_Indoor"}
    )

    ereg = entity_registry
    ereg.async_get_or_create(
        domain="light",
        platform=DOMAIN,
        unique_id=f"{CAM_ID.lower()}_front_light_entity",
        config_entry=entry,
        suggested_object_id="bosch_indoor_front_light",
    )
    ereg.async_get_or_create(
        domain="number",
        platform=DOMAIN,
        unique_id=f"{OTHER_CAM_ID.lower()}_top_led_brightness",
        config_entry=entry,
        suggested_object_id="bosch_outdoor_top_led_brightness",
    )

    await _setup_healthy_entry(hass, entry)

    assert ereg.async_get("light.bosch_indoor_front_light") is None
    assert ereg.async_get("number.bosch_outdoor_top_led_brightness") is not None


async def test_stale_doubled_lan_reachable_entity_removed(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """v12.4.10 migration removes a stale doubled-prefix `_lan_reachable` entity."""
    entry = _mock_config_entry()
    entry.add_to_hass(hass)

    ereg = entity_registry
    ereg.async_get_or_create(
        domain="binary_sensor",
        platform=DOMAIN,
        unique_id="bosch_shc_cam_stale_lan",
        config_entry=entry,
        suggested_object_id="bosch_terrasse_bosch_garten_lan_reachable",
    )

    await _setup_healthy_entry(hass, entry)

    assert (
        ereg.async_get("binary_sensor.bosch_terrasse_bosch_garten_lan_reachable")
        is None
    )


async def test_hw_rehydrate_skips_foreign_domain_and_already_populated_cam(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
) -> None:
    """`_async_rehydrate_hw_from_registry` skips foreign-domain identifiers.

    Also skips a camera whose hw_version is already populated (from the
    persisted store), instead of overwriting it from the device registry.
    """
    entry = _mock_config_entry()
    entry.add_to_hass(hass)

    await Store(hass, version=1, key=f"{DOMAIN}_hw_versions").async_save(
        {CAM_ID: "HOME_Eyes_Outdoor"}
    )

    dreg = device_registry
    dreg.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, CAM_ID), ("other_domain", "unrelated-id")},
        model="Eyes Innenkamera II",
    )

    await _setup_healthy_entry(hass, entry)

    # Persisted value must survive untouched — the registry model
    # ("Eyes Innenkamera II") is never consulted for this cam_id.
    assert entry.runtime_data.hw_version[CAM_ID.upper()] == "HOME_Eyes_Outdoor"


async def test_hw_rehydrate_from_registry_tolerates_registry_exception(
    hass: HomeAssistant,
) -> None:
    """A device-registry lookup failure during hw_version rehydrate is best-effort.

    Must not block setup — only the rehydrate step is skipped.
    """
    entry = _mock_config_entry()
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.bosch_shc_camera.dr.async_get",
        side_effect=RuntimeError("registry unavailable"),
    ):
        await _setup_healthy_entry(hass, entry)

    assert entry.state is ConfigEntryState.LOADED


async def test_ha_stop_event_cancels_coordinator_background_tasks(
    hass: HomeAssistant,
) -> None:
    """Firing `EVENT_HOMEASSISTANT_STOP` cancels the proactive token-refresh timer.

    Without the stop listener, the timer would still be pending at HA's
    final-writes shutdown stage.
    """
    entry = _mock_config_entry()
    entry.add_to_hass(hass)

    await _setup_healthy_entry(hass, entry)
    coordinator = entry.runtime_data
    assert coordinator.token_refresh_handle is not None

    hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
    await hass.async_block_till_done()

    assert coordinator.token_refresh_handle is None


async def test_unload_tolerates_token_refresh_handle_cancel_raising(
    hass: HomeAssistant,
) -> None:
    """A `RuntimeError` from `token_refresh_handle.cancel()` is swallowed, not raised."""
    entry = _mock_config_entry()
    entry.add_to_hass(hass)

    await _setup_healthy_entry(hass, entry)
    coordinator = entry.runtime_data

    broken_handle = MagicMock()
    broken_handle.cancel.side_effect = RuntimeError("already cancelled")
    coordinator.token_refresh_handle = broken_handle

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert coordinator.token_refresh_handle is None


@pytest.mark.parametrize(
    ("snapshot_delta", "expect_reload"),
    [
        pytest.param({}, False, id="options-unchanged"),
        pytest.param({"stream_connection_type": "changed"}, True, id="options-changed"),
    ],
)
async def test_options_updated_reloads_only_on_real_change(
    hass: HomeAssistant,
    snapshot_delta: dict[str, Any],
    expect_reload: bool,
) -> None:
    """`_async_options_updated` reloads only when the options snapshot actually differs."""
    entry = _mock_config_entry()
    entry.add_to_hass(hass)
    await _setup_healthy_entry(hass, entry)

    prev_snapshot = {**get_options(entry), **snapshot_delta}
    hass.data[OPTIONS_SNAPSHOT_KEY][entry.entry_id] = prev_snapshot

    with patch.object(
        hass.config_entries, "async_reload", AsyncMock(return_value=True)
    ) as mock_reload:
        await _async_options_updated(hass, entry)

    assert mock_reload.called is expect_reload
    if expect_reload:
        mock_reload.assert_awaited_once_with(entry.entry_id)
        assert hass.data[OPTIONS_SNAPSHOT_KEY][entry.entry_id] == get_options(entry)


async def test_options_updated_falls_back_to_coordinator_snapshot(
    hass: HomeAssistant,
) -> None:
    """With no hass.data snapshot yet, the coordinator's own snapshot is used."""
    entry = _mock_config_entry()
    entry.add_to_hass(hass)
    await _setup_healthy_entry(hass, entry)

    # Simulate the brief post-setup window before a snapshot exists for this
    # entry_id (e.g. a test that only populates runtime_data).
    hass.data[OPTIONS_SNAPSHOT_KEY].pop(entry.entry_id, None)
    entry.runtime_data._options_snapshot = get_options(entry)

    with patch.object(
        hass.config_entries, "async_reload", AsyncMock(return_value=True)
    ) as mock_reload:
        await _async_options_updated(hass, entry)

    mock_reload.assert_not_called()


async def test_unload_entry_cancels_coordinator_tasks_only_after_platforms_unload(
    hass: HomeAssistant,
) -> None:
    """Coordinator tasks are cancelled ONLY when async_unload_platforms succeeds.

    Regression for Copilot review round 15: cancelling the coordinator's
    timers/background tasks BEFORE unloading platforms leaves a loaded
    integration whose entities never update again if the platform unload
    itself fails (returns False) — the config entry stays LOADED either way,
    but the old ordering guaranteed the coordinator was already dead.

    Goes through `hass.config_entries.async_unload` (not a direct
    `async_unload_entry` call) per HA-core's own test convention.
    """
    entry = _mock_config_entry()
    entry.add_to_hass(hass)
    await _setup_healthy_entry(hass, entry)

    init_mod = "homeassistant.components.bosch_shc_camera"
    with (
        patch.object(
            hass.config_entries,
            "async_unload_platforms",
            AsyncMock(return_value=False),
        ) as mock_unload_platforms,
        patch(
            f"{init_mod}._async_cancel_coordinator_tasks", AsyncMock()
        ) as mock_cancel_tasks,
    ):
        result = await hass.config_entries.async_unload(entry.entry_id)

    assert result is False
    mock_unload_platforms.assert_awaited_once()
    mock_cancel_tasks.assert_not_called()


async def test_unload_entry_cancels_coordinator_tasks_when_platforms_unload_succeeds(
    hass: HomeAssistant,
) -> None:
    """A successful platform unload DOES cancel the coordinator's background tasks."""
    entry = _mock_config_entry()
    entry.add_to_hass(hass)
    await _setup_healthy_entry(hass, entry)
    coord = entry.runtime_data

    init_mod = "homeassistant.components.bosch_shc_camera"
    with (
        patch.object(
            hass.config_entries,
            "async_unload_platforms",
            AsyncMock(return_value=True),
        ),
        patch(
            f"{init_mod}._async_cancel_coordinator_tasks", AsyncMock()
        ) as mock_cancel_tasks,
    ):
        result = await hass.config_entries.async_unload(entry.entry_id)

    assert result is True
    mock_cancel_tasks.assert_awaited_once_with(coord)
