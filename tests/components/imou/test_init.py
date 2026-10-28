"""Tests for the Imou init."""

import contextlib
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, call, patch

from freezegun.api import FrozenDateTimeFactory
from pyimouapi.const import PARAM_STATE, PARAM_STATUS
from pyimouapi.exceptions import ImouException, InvalidAppIdOrSecretException
from pyimouapi.ha_device import DeviceStatus, ImouHaDevice
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed

from homeassistant.components.imou import async_remove_config_entry_device
from homeassistant.components.imou.button import PARAM_MUTE, PARAM_PTZ_UP
from homeassistant.components.imou.const import DOMAIN, PLATFORMS
from homeassistant.components.imou.coordinator import SCAN_INTERVAL
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .const import create_offline_device, create_online_device, default_mock_devices

EXPECTED_TRANSLATION_KEYS = {
    "mute": PARAM_MUTE,
    "camera_sd": "camera_sd",
    "camera_hd": "camera_hd",
    "status": PARAM_STATUS,
}


@pytest.mark.usefixtures("init_integration")
async def test_setup_and_unload_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test loading and unloading the config entry."""
    assert mock_config_entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.parametrize(
    ("exception", "expected_state", "translation_key"),
    [
        (
            InvalidAppIdOrSecretException("bad credentials"),
            ConfigEntryState.SETUP_ERROR,
            "invalid_auth",
        ),
        (
            ImouException("cloud failure"),
            ConfigEntryState.SETUP_RETRY,
            "fetch_devices_failed",
        ),
        (
            ImouException("OP1013:monthly quota exceeded"),
            ConfigEntryState.SETUP_RETRY,
            "quota_exceeded",
        ),
        (TimeoutError("timeout"), ConfigEntryState.SETUP_RETRY, "update_timeout"),
    ],
)
@pytest.mark.usefixtures("mock_imou_openapi_client", "mock_imou_ha_device_manager")
async def test_setup_entry_exceptions(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_imou_ha_device_manager: AsyncMock,
    exception: Exception,
    expected_state: ConfigEntryState,
    translation_key: str,
) -> None:
    """Test the coordinator errors while listing devices during setup."""
    mock_imou_ha_device_manager.async_get_devices.side_effect = exception
    mock_config_entry.add_to_hass(hass)

    assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is expected_state
    assert mock_config_entry.error_reason_translation_domain == DOMAIN
    assert mock_config_entry.error_reason_translation_key == translation_key


@pytest.mark.usefixtures("init_integration")
async def test_device_registry_identifiers(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Device registry uses channel-aware identifiers from the default mock devices."""
    devices = dr.async_entries_for_config_entry(
        device_registry, mock_config_entry.entry_id
    )
    assert len(devices) == 1
    assert (DOMAIN, "d1") in devices[0].identifiers


@pytest.mark.parametrize(
    "imou_mock_devices",
    [
        [
            create_online_device(
                "dev-1",
                "Cam",
                channel_id="ch9",
                button_keys=(PARAM_MUTE,),
            ),
            create_online_device(
                "dev-1",
                "Cam",
                channel_id="ch10",
                button_keys=(PARAM_MUTE,),
            ),
        ]
    ],
    indirect=True,
)
@pytest.mark.usefixtures("init_integration")
async def test_multiple_channels_create_separate_devices(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Each channel gets its own device and button entities in the registries."""
    devices = dr.async_entries_for_config_entry(
        device_registry, mock_config_entry.entry_id
    )
    device_ids_by_key = {
        next(iter(device.identifiers))[1]: device.id for device in devices
    }
    assert set(device_ids_by_key) == {"dev-1_ch9", "dev-1_ch10"}

    entries = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    assert len(entries) == 8
    assert {entry.unique_id for entry in entries} == {
        "dev-1_ch9$mute",
        "dev-1_ch10$mute",
        "dev-1_ch9$camera_sd",
        "dev-1_ch9$camera_hd",
        "dev-1_ch10$camera_sd",
        "dev-1_ch10$camera_hd",
        "dev-1_ch9$status",
        "dev-1_ch10$status",
    }
    for entry in entries:
        device_key, entity_type = entry.unique_id.split("$", 1)
        assert entry.device_id == device_ids_by_key[device_key]
        assert entry.translation_key == EXPECTED_TRANSLATION_KEYS[entity_type]


@pytest.mark.parametrize(
    "unique_id",
    [
        "dev-1_ch9$mute",
        "dev-1_ch10$mute",
        "dev-1_ch9$camera_sd",
        "dev-1_ch10$camera_sd",
        "dev-1_ch9$status",
        "dev-1_ch10$status",
    ],
)
@pytest.mark.parametrize(
    "imou_mock_devices",
    [
        [
            create_online_device(
                "dev-1",
                "Cam",
                channel_id="ch9",
                button_keys=(PARAM_MUTE,),
            ),
            create_online_device(
                "dev-1",
                "Cam",
                channel_id="ch10",
                button_keys=(PARAM_MUTE,),
            ),
        ]
    ],
    indirect=True,
)
@pytest.mark.usefixtures("init_integration")
async def test_multiple_channels_enabled_entities_have_state(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    unique_id: str,
) -> None:
    """Enabled entities on multi-channel devices report a live state."""
    entry = next(
        registry_entry
        for registry_entry in er.async_entries_for_config_entry(
            entity_registry, mock_config_entry.entry_id
        )
        if registry_entry.unique_id == unique_id
    )
    state = hass.states.get(entry.entity_id)
    assert state is not None
    assert state.state != STATE_UNAVAILABLE


@pytest.mark.parametrize("imou_mock_devices", [[]], indirect=True)
@pytest.mark.usefixtures("init_integration")
async def test_coordinator_adds_entities_after_initial_empty_device_list(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_imou_ha_device_manager: MagicMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Devices added after an empty first refresh still get entities via callbacks."""
    assert (
        len(
            er.async_entries_for_config_entry(
                entity_registry, mock_config_entry.entry_id
            )
        )
        == 0
    )

    mock_imou_ha_device_manager.async_get_devices.return_value = default_mock_devices()
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    entries = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    assert len(entries) == 4
    assert {entry.unique_id for entry in entries} == {
        "d1$status",
        "d1$mute",
        "d1$ptz_up",
        "d1$restart_device",
    }


@pytest.mark.usefixtures("init_integration")
async def test_coordinator_adds_entities_for_new_device(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_imou_ha_device_manager: MagicMock,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """A device added to the Imou account is discovered on the next coordinator refresh."""
    assert (
        len(
            er.async_entries_for_config_entry(
                entity_registry, mock_config_entry.entry_id
            )
        )
        == 4
    )

    mock_imou_ha_device_manager.async_get_devices.return_value = [
        *default_mock_devices(),
        create_online_device("d2", "Device 2", button_keys=(PARAM_PTZ_UP,)),
    ]
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    entries = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    assert len(entries) == 6
    assert "d2$ptz_up" in {entry.unique_id for entry in entries}
    ptz_entry = next(entry for entry in entries if entry.unique_id == "d2$ptz_up")
    assert hass.states.get(ptz_entry.entity_id).state != STATE_UNAVAILABLE

    devices = dr.async_entries_for_config_entry(
        device_registry, mock_config_entry.entry_id
    )
    assert len(devices) == 2
    device_keys = {next(iter(device.identifiers))[1] for device in devices}
    assert device_keys == {"d1", "d2"}


@pytest.mark.usefixtures("init_integration")
async def test_known_device_refresh_skips_ability_refs(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_imou_ha_device_manager: MagicMock,
) -> None:
    """A later listing of the same devices does not fetch ability refs again."""
    mock_imou_ha_device_manager.async_get_devices.reset_mock()

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    mock_imou_ha_device_manager.async_get_devices.assert_awaited_once_with(
        fetch_ability_refs=False
    )


@pytest.mark.usefixtures("init_integration")
async def test_new_device_fetches_ability_refs_for_that_device(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_imou_ha_device_manager: MagicMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Only a device that just appeared gets an ability-ref request."""
    known = default_mock_devices()
    shallow = create_online_device("d2", "Device 2", button_keys=())
    detailed = create_online_device("d2", "Device 2", button_keys=(PARAM_PTZ_UP,))

    async def list_devices(
        *, fetch_ability_refs: bool | set[str] = True
    ) -> list[ImouHaDevice]:
        if fetch_ability_refs is False:
            return [*known, shallow]
        if fetch_ability_refs == {"d2"}:
            return [detailed]
        raise AssertionError(fetch_ability_refs)

    mock_imou_ha_device_manager.async_get_devices.reset_mock()
    mock_imou_ha_device_manager.async_get_devices.side_effect = list_devices
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    entries = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    assert "d2$ptz_up" in {entry.unique_id for entry in entries}
    assert mock_imou_ha_device_manager.async_get_devices.await_args_list == [
        call(fetch_ability_refs=False),
        call(fetch_ability_refs={"d2"}),
    ]


@pytest.mark.parametrize(
    ("error", "translation_key", "starts_reauth"),
    [
        (TimeoutError("timeout"), "update_timeout", False),
        (ImouException("cloud failure"), "fetch_devices_failed", False),
        (InvalidAppIdOrSecretException("bad credentials"), "invalid_auth", True),
    ],
)
@pytest.mark.usefixtures("init_integration")
async def test_new_device_ability_ref_failure(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_imou_ha_device_manager: MagicMock,
    error: Exception,
    translation_key: str,
    starts_reauth: bool,
) -> None:
    """A failed ability-ref fetch for a new device does not load that device."""
    known = default_mock_devices()
    shallow = create_online_device("d2", "Device 2", button_keys=())
    seen: list[bool | set[str]] = []

    async def list_devices(
        *, fetch_ability_refs: bool | set[str] = True
    ) -> list[ImouHaDevice]:
        seen.append(fetch_ability_refs)
        if fetch_ability_refs is False:
            return [*known, shallow]
        raise error

    mock_imou_ha_device_manager.async_get_devices.reset_mock()
    mock_imou_ha_device_manager.async_get_devices.side_effect = list_devices
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert seen == [False, {"d2"}]
    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_config_entry.runtime_data.last_exception is not None
    assert (
        mock_config_entry.runtime_data.last_exception.translation_key == translation_key
    )
    flows = mock_config_entry.async_get_active_flows(hass, {SOURCE_REAUTH})
    if starts_reauth:
        assert any(flows)
    else:
        assert not any(flows)
        assert hass.states.get("button.device_1_mute").state == STATE_UNAVAILABLE


@pytest.mark.usefixtures("init_integration")
async def test_new_device_missing_from_ability_detail_is_not_added(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_imou_ha_device_manager: MagicMock,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """A new device omitted from the ability-ref result is not registered."""
    known = default_mock_devices()
    shallow = create_online_device("d2", "Device 2", button_keys=(PARAM_PTZ_UP,))

    async def list_devices(
        *, fetch_ability_refs: bool | set[str] = True
    ) -> list[ImouHaDevice]:
        if fetch_ability_refs is False:
            return [*known, shallow]
        if fetch_ability_refs == {"d2"}:
            return []
        raise AssertionError(fetch_ability_refs)

    mock_imou_ha_device_manager.async_get_devices.reset_mock()
    mock_imou_ha_device_manager.async_get_devices.side_effect = list_devices
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    entries = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    assert "d2$ptz_up" not in {entry.unique_id for entry in entries}
    devices = dr.async_entries_for_config_entry(
        device_registry, mock_config_entry.entry_id
    )
    assert len(devices) == 1
    assert hass.states.get("button.device_1_mute").state != STATE_UNAVAILABLE


@pytest.mark.usefixtures("mock_imou_openapi_client")
async def test_failed_ability_ref_is_retried_before_the_device_is_added(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_imou_ha_device_manager: MagicMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """A device whose ability-ref read failed is asked again on the next poll."""
    camera = create_online_device("d1", "Device 1", button_keys=(PARAM_MUTE,))
    pending = create_online_device("d2", "Device 2", button_keys=(PARAM_PTZ_UP,))
    raw = SimpleNamespace(device_id="d2")
    seen: list[bool | set[str]] = []
    attempts = 0

    async def fail_once(_imou_device: SimpleNamespace) -> None:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise ImouException("detail failed")

    async def list_devices(
        *, fetch_ability_refs: bool | set[str] = True
    ) -> list[ImouHaDevice]:
        seen.append(fetch_ability_refs)
        if fetch_ability_refs is not False:
            with contextlib.suppress(ImouException):
                await mock_imou_ha_device_manager.delegate._async_update_device_ability_refs(
                    raw
                )
        return [camera, pending]

    mock_imou_ha_device_manager.delegate._async_update_device_ability_refs = fail_once
    mock_imou_ha_device_manager.async_get_devices.side_effect = list_devices
    mock_config_entry.add_to_hass(hass)
    with patch("homeassistant.components.imou.PLATFORMS", PLATFORMS):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    entries = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    assert "d1$mute" in {entry.unique_id for entry in entries}
    assert "d2$ptz_up" not in {entry.unique_id for entry in entries}
    assert hass.states.get("button.device_1_mute").state != STATE_UNAVAILABLE

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    entries = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    assert "d2$ptz_up" in {entry.unique_id for entry in entries}
    assert seen == [True, {"d2"}]
    assert attempts == 2


@pytest.mark.parametrize(
    "imou_mock_devices",
    [
        [
            create_online_device("d1", "Device 1", button_keys=(PARAM_MUTE,)),
            create_online_device("d2", "Device 2", button_keys=(PARAM_PTZ_UP,)),
        ]
    ],
    indirect=True,
)
@pytest.mark.usefixtures("init_integration")
async def test_coordinator_removes_device_updates_registries(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_imou_ha_device_manager: MagicMock,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """A removed device is dropped from the device and entity registries."""
    assert (
        len(
            dr.async_entries_for_config_entry(
                device_registry, mock_config_entry.entry_id
            )
        )
        == 2
    )
    entries_before = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    assert {entry.unique_id for entry in entries_before} == {
        "d1$mute",
        "d1$status",
        "d2$ptz_up",
        "d2$status",
    }

    mock_imou_ha_device_manager.async_get_devices.return_value = default_mock_devices()
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    devices = dr.async_entries_for_config_entry(
        device_registry, mock_config_entry.entry_id
    )
    assert len(devices) == 1
    assert (DOMAIN, "d1") in devices[0].identifiers

    entries_after = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    assert {entry.unique_id for entry in entries_after} == {"d1$mute", "d1$status"}
    mute_entry = next(entry for entry in entries_after if entry.unique_id == "d1$mute")
    assert hass.states.get(mute_entry.entity_id).state != STATE_UNAVAILABLE


@pytest.mark.parametrize(
    "imou_mock_devices",
    [
        [
            create_online_device(
                "d1",
                "Device 1",
                button_keys=(PARAM_MUTE,),
            )
        ]
    ],
    indirect=True,
)
@pytest.mark.usefixtures("init_integration")
async def test_offline_device_marked_unavailable_after_refresh(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_imou_ha_device_manager: MagicMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """An offline device reported on refresh marks button entities unavailable."""
    mute_entry = next(
        entry
        for entry in er.async_entries_for_config_entry(
            entity_registry, mock_config_entry.entry_id
        )
        if entry.unique_id == "d1$mute"
    )
    assert hass.states.get(mute_entry.entity_id).state != STATE_UNAVAILABLE

    async def set_devices_offline(devices: list[ImouHaDevice]) -> None:
        for device in devices:
            device._sensors[PARAM_STATUS] = {PARAM_STATE: DeviceStatus.OFFLINE.value}

    mock_imou_ha_device_manager.async_update_devices_status.side_effect = (
        set_devices_offline
    )
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert hass.states.get(mute_entry.entity_id).state == STATE_UNAVAILABLE


@pytest.mark.usefixtures("init_integration")
async def test_coordinator_update_fails_when_all_devices_fail(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_imou_ha_device_manager: MagicMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """When every device status update fails, the coordinator update fails."""
    mute_entry = next(
        entry
        for entry in er.async_entries_for_config_entry(
            entity_registry, mock_config_entry.entry_id
        )
        if entry.unique_id == "d1$mute"
    )
    assert hass.states.get(mute_entry.entity_id).state != STATE_UNAVAILABLE

    mock_imou_ha_device_manager.async_update_devices_status.side_effect = ImouException(
        "cloud failure"
    )
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_config_entry.runtime_data.last_update_success is False
    assert hass.states.get(mute_entry.entity_id).state == STATE_UNAVAILABLE


@pytest.mark.parametrize(
    "side_effect",
    [TimeoutError("timeout"), ImouException("cloud failure")],
)
@pytest.mark.usefixtures("init_integration")
async def test_coordinator_poll_list_devices_keeps_entry_loaded(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_imou_ha_device_manager: MagicMock,
    side_effect: Exception,
) -> None:
    """A later device-list failure leaves the entry loaded and entities unavailable."""
    mock_imou_ha_device_manager.async_get_devices.side_effect = side_effect
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert hass.states.get("button.device_1_mute").state == STATE_UNAVAILABLE


@pytest.mark.usefixtures("init_integration")
async def test_coordinator_poll_status_refresh_timeout_translation(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_imou_ha_device_manager: MagicMock,
) -> None:
    """A later status-refresh timeout leaves the entry loaded and entities unavailable."""
    mock_imou_ha_device_manager.async_update_devices_status.side_effect = TimeoutError(
        "timeout"
    )
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert hass.states.get("button.device_1_mute").state == STATE_UNAVAILABLE


@pytest.mark.usefixtures("init_integration")
async def test_coordinator_status_refresh_invalid_auth(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_imou_ha_device_manager: MagicMock,
) -> None:
    """Invalid credentials during status refresh start reauthentication."""
    mock_imou_ha_device_manager.async_update_devices_status.side_effect = (
        InvalidAppIdOrSecretException("bad credentials")
    )
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert any(mock_config_entry.async_get_active_flows(hass, {SOURCE_REAUTH}))


@pytest.mark.parametrize(
    "imou_mock_devices",
    [
        [
            create_offline_device(
                "d1",
                "Device 1",
                button_keys=(PARAM_MUTE,),
            )
        ]
    ],
    indirect=True,
)
@pytest.mark.usefixtures("init_integration")
async def test_offline_device_unavailable_at_setup(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """An offline device marks button entities unavailable via the state machine."""
    mute_entry = next(
        entry
        for entry in er.async_entries_for_config_entry(
            entity_registry, mock_config_entry.entry_id
        )
        if entry.unique_id == "d1$mute"
    )
    assert hass.states.get(mute_entry.entity_id).state == STATE_UNAVAILABLE


@pytest.mark.parametrize(
    "imou_mock_devices",
    [
        [
            create_online_device("d1", "Device 1", button_keys=(PARAM_MUTE,)),
            create_online_device("d2", "Device 2", button_keys=(PARAM_PTZ_UP,)),
        ]
    ],
    indirect=True,
)
@pytest.mark.usefixtures("init_integration")
async def test_remove_config_entry_device_rejects_active_device(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Devices still on the account cannot be removed manually."""
    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, "d1"), mock_config_entry.entry_id
    )
    assert device is not None
    assert not await async_remove_config_entry_device(hass, mock_config_entry, device)


@pytest.mark.parametrize(
    "imou_mock_devices",
    [[create_online_device("d1", "Device 1", button_keys=(PARAM_MUTE,))]],
    indirect=True,
)
@pytest.mark.usefixtures("init_integration")
async def test_remove_config_entry_device_allows_stale_device(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Devices no longer on the account can be removed manually."""
    stale_device = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={(DOMAIN, "ghost")},
        name="Removed gateway",
        manufacturer="Imou",
        model="Test",
    )
    assert await async_remove_config_entry_device(hass, mock_config_entry, stale_device)
