"""Tests for the Imou init."""

from unittest.mock import AsyncMock, MagicMock

from freezegun.api import FrozenDateTimeFactory
from pyimouapi.ha_device import DeviceStatus, ImouHaDevice
import pytest

from homeassistant.components.imou.const import (
    DOMAIN,
    PARAM_MUTE,
    PARAM_PTZ_UP,
    PARAM_STATE,
    PARAM_STATUS,
)
from homeassistant.components.imou.coordinator import SCAN_INTERVAL
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .const import DEFAULT_MOCK_DEVICES, create_offline_device, create_online_device

from tests.common import MockConfigEntry, async_fire_time_changed


@pytest.mark.usefixtures("mock_imou_openapi_client", "mock_imou_ha_device_manager")
async def test_setup_and_unload_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    init_integration: MagicMock,
) -> None:
    """Test loading and unloading the config entry."""
    assert mock_config_entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.usefixtures("mock_imou_openapi_client", "mock_imou_ha_device_manager")
async def test_setup_entry_failed_on_refresh(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_imou_ha_device_manager: AsyncMock,
) -> None:
    """Device fetch failure during coordinator setup surfaces as setup retry."""
    mock_imou_ha_device_manager.async_get_devices.side_effect = RuntimeError(
        "Setup failed"
    )
    mock_config_entry.add_to_hass(hass)

    assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.usefixtures("init_integration")
async def test_device_registry_identifiers(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Device registry uses channel-aware identifiers from the default mock devices."""
    registry = dr.async_get(hass)
    devices = dr.async_entries_for_config_entry(registry, mock_config_entry.entry_id)
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
) -> None:
    """Each channel gets its own device and button entities in the registries."""
    device_registry = dr.async_get(hass)
    devices = dr.async_entries_for_config_entry(
        device_registry, mock_config_entry.entry_id
    )
    device_ids_by_key = {
        next(iter(device.identifiers))[1]: device.id for device in devices
    }
    assert set(device_ids_by_key) == {"dev-1_ch9", "dev-1_ch10"}

    entity_registry = er.async_get(hass)
    entries = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    assert len(entries) == 2
    assert {entry.unique_id for entry in entries} == {
        "dev-1_ch9$mute",
        "dev-1_ch10$mute",
    }
    for entry in entries:
        assert entry.translation_key == PARAM_MUTE
        device_key = entry.unique_id.split("$", 1)[0]
        assert entry.device_id == device_ids_by_key[device_key]
        state = hass.states.get(entry.entity_id)
        assert state is not None
        assert state.state != STATE_UNAVAILABLE


@pytest.mark.usefixtures("init_integration")
async def test_coordinator_adds_entities_for_new_device(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_imou_ha_device_manager: MagicMock,
) -> None:
    """A device added to the Imou account is discovered on the next coordinator refresh."""
    entity_registry = er.async_get(hass)
    assert (
        len(
            er.async_entries_for_config_entry(
                entity_registry, mock_config_entry.entry_id
            )
        )
        == 3
    )

    mock_imou_ha_device_manager.async_get_devices.return_value = [
        *DEFAULT_MOCK_DEVICES,
        create_online_device("d2", "Device 2", button_keys=(PARAM_PTZ_UP,)),
    ]
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    entries = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    assert len(entries) == 4
    assert "d2$ptz_up" in {entry.unique_id for entry in entries}
    ptz_entry = next(entry for entry in entries if entry.unique_id == "d2$ptz_up")
    assert hass.states.get(ptz_entry.entity_id).state != STATE_UNAVAILABLE

    device_registry = dr.async_get(hass)
    devices = dr.async_entries_for_config_entry(
        device_registry, mock_config_entry.entry_id
    )
    assert len(devices) == 2
    device_keys = {next(iter(device.identifiers))[1] for device in devices}
    assert device_keys == {"d1", "d2"}


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
) -> None:
    """A removed device is dropped from the device and entity registries."""
    device_registry = dr.async_get(hass)
    entity_registry = er.async_get(hass)
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
        "d2$ptz_up",
    }

    mock_imou_ha_device_manager.async_get_devices.return_value = DEFAULT_MOCK_DEVICES
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
    assert {entry.unique_id for entry in entries_after} == {"d1$mute"}
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
) -> None:
    """An offline device reported on refresh marks button entities unavailable."""
    entity_registry = er.async_get(hass)
    mute_entry = next(
        entry
        for entry in er.async_entries_for_config_entry(
            entity_registry, mock_config_entry.entry_id
        )
        if entry.unique_id == "d1$mute"
    )
    assert hass.states.get(mute_entry.entity_id).state != STATE_UNAVAILABLE

    async def set_device_offline(device: ImouHaDevice) -> None:
        device._sensors[PARAM_STATUS] = {PARAM_STATE: DeviceStatus.OFFLINE.value}

    mock_imou_ha_device_manager.async_update_device_status.side_effect = (
        set_device_offline
    )
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert hass.states.get(mute_entry.entity_id).state == STATE_UNAVAILABLE


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
) -> None:
    """An offline device marks button entities unavailable via the state machine."""
    entity_registry = er.async_get(hass)
    mute_entry = next(
        entry
        for entry in er.async_entries_for_config_entry(
            entity_registry, mock_config_entry.entry_id
        )
        if entry.unique_id == "d1$mute"
    )
    assert hass.states.get(mute_entry.entity_id).state == STATE_UNAVAILABLE
