"""Tests for Imou button platform."""

from unittest.mock import MagicMock

from freezegun.api import FrozenDateTimeFactory
from pyimouapi.exceptions import ImouException
from pyimouapi.ha_device import DeviceStatus, ImouHaDevice
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.components.imou.button import PARAM_MUTE, PARAM_PTZ_UP
from homeassistant.components.imou.const import (
    PARAM_STATE,
    PARAM_STATUS,
    PTZ_MOVE_DURATION_MS,
)
from homeassistant.components.imou.coordinator import SCAN_INTERVAL
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from .const import UNKNOWN_BUTTON_KEY, create_online_device

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform


@pytest.mark.parametrize("platforms", [[Platform.BUTTON]], indirect=True)
@pytest.mark.usefixtures("init_integration")
async def test_button_entities_snapshot(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Snapshot button entities created from the default mock device list."""
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize("platforms", [[Platform.BUTTON]], indirect=True)
@pytest.mark.parametrize(
    "imou_mock_devices",
    [
        [
            create_online_device(
                "d1",
                "Device 1",
                button_keys=(UNKNOWN_BUTTON_KEY, PARAM_MUTE),
            )
        ]
    ],
    indirect=True,
)
@pytest.mark.usefixtures("init_integration")
async def test_setup_ignores_unknown_button_types(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Unknown button keys from the API are not turned into entities."""
    registry = er.async_get(hass)
    entries = er.async_entries_for_config_entry(registry, mock_config_entry.entry_id)
    assert len(entries) == 1
    assert entries[0].translation_key == PARAM_MUTE


@pytest.mark.usefixtures("init_integration")
async def test_press_button_via_service(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    init_integration: MagicMock,
) -> None:
    """Pressing a button calls the vendor library through the coordinator."""
    entries = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    mute_entry = next(e for e in entries if e.translation_key == PARAM_MUTE)
    entity_id = mute_entry.entity_id

    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )

    init_integration.async_press_button.assert_awaited_once()
    call = init_integration.async_press_button.await_args
    assert call is not None
    assert call.args[1] == PARAM_MUTE
    assert call.args[2] == 0


@pytest.mark.usefixtures("init_integration")
async def test_press_ptz_button_passes_move_duration(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    init_integration: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """PTZ buttons pass the configured move duration to the vendor library."""
    entries = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    ptz_entry = next(e for e in entries if e.translation_key == PARAM_PTZ_UP)

    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: ptz_entry.entity_id},
        blocking=True,
    )

    init_integration.async_press_button.assert_awaited_once()
    call = init_integration.async_press_button.await_args
    assert call is not None
    assert call.args[1] == PARAM_PTZ_UP
    assert call.args[2] == PTZ_MOVE_DURATION_MS


@pytest.mark.usefixtures("init_integration")
async def test_press_button_service_propagates_api_error(
    hass: HomeAssistant,
    init_integration: MagicMock,
) -> None:
    """Imou API errors from async_press_button surface to the service call."""
    init_integration.async_press_button.side_effect = ImouException("cloud failure")

    entity_id = hass.states.async_all("button")[0].entity_id

    with pytest.raises(HomeAssistantError, match="cloud failure"):
        await hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )


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
async def test_press_unavailable_offline_device_via_service(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    mock_imou_ha_device_manager: MagicMock,
    init_integration: MagicMock,
) -> None:
    """Pressing an offline device does not call the vendor library."""
    mute_entry = next(
        entry
        for entry in er.async_entries_for_config_entry(
            entity_registry, mock_config_entry.entry_id
        )
        if entry.unique_id == "d1$mute"
    )

    async def set_device_offline(device: ImouHaDevice) -> None:
        device._sensors[PARAM_STATUS] = {PARAM_STATE: DeviceStatus.OFFLINE.value}

    mock_imou_ha_device_manager.async_update_device_status.side_effect = (
        set_device_offline
    )
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert hass.states.get(mute_entry.entity_id).state == STATE_UNAVAILABLE

    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: mute_entry.entity_id},
        blocking=True,
    )

    init_integration.async_press_button.assert_not_called()


@pytest.mark.usefixtures("init_integration")
async def test_entities_removed_when_device_leaves_account(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    mock_imou_ha_device_manager: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Button entities are removed when the device is no longer on the account."""
    mute_entry = next(
        entry
        for entry in er.async_entries_for_config_entry(
            entity_registry, mock_config_entry.entry_id
        )
        if entry.unique_id == "d1$mute"
    )
    assert hass.states.get(mute_entry.entity_id).state != STATE_UNAVAILABLE

    mock_imou_ha_device_manager.async_get_devices.return_value = []

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert (
        er.async_entries_for_config_entry(entity_registry, mock_config_entry.entry_id)
        == []
    )
    assert hass.states.get(mute_entry.entity_id) is None
