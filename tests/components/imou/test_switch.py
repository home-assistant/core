"""Tests for Imou switch platform."""

from unittest.mock import MagicMock

from freezegun.api import FrozenDateTimeFactory
from pyimouapi.exceptions import ImouException
from pyimouapi.ha_device import DeviceStatus, ImouHaDevice
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.imou.const import (
    PARAM_HEADER_DETECT,
    PARAM_MOTION_DETECT,
    PARAM_STATE,
    PARAM_STATUS,
)
from homeassistant.components.imou.coordinator import SCAN_INTERVAL
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_UNAVAILABLE,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from .const import DEFAULT_SWITCHES, UNKNOWN_SWITCH_KEY, create_online_device

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform


async def _apply_switch_operation(
    device: ImouHaDevice, switch_type: str, enable: bool
) -> None:
    """Simulate the vendor API updating switch state after a command."""
    device.switches[switch_type][PARAM_STATE] = enable


SWITCH_MOCK_DEVICES = [
    create_online_device(
        "d1",
        "Device 1",
        button_keys=(),
        switches=DEFAULT_SWITCHES,
    ),
]


@pytest.mark.parametrize("platforms", [[Platform.SWITCH]], indirect=True)
@pytest.mark.parametrize("imou_mock_devices", [SWITCH_MOCK_DEVICES], indirect=True)
@pytest.mark.usefixtures("init_integration")
async def test_switch_entities_snapshot(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Snapshot switch entities created from the mock device list."""
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize(
    "imou_mock_devices",
    [
        [
            create_online_device(
                "d1",
                "Device 1",
                button_keys=(),
                switches={
                    UNKNOWN_SWITCH_KEY: {PARAM_STATE: False},
                    PARAM_MOTION_DETECT: {PARAM_STATE: False},
                },
            )
        ]
    ],
    indirect=True,
)
@pytest.mark.usefixtures("init_integration")
async def test_setup_ignores_unknown_switch_types(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Unknown switch keys from the API are not turned into entities."""
    registry = er.async_get(hass)
    entries = er.async_entries_for_config_entry(registry, mock_config_entry.entry_id)
    switch_entries = [entry for entry in entries if entry.domain == SWITCH_DOMAIN]
    assert len(switch_entries) == 1
    assert switch_entries[0].translation_key == PARAM_MOTION_DETECT


@pytest.mark.parametrize("imou_mock_devices", [SWITCH_MOCK_DEVICES], indirect=True)
@pytest.mark.usefixtures("init_integration")
async def test_turn_on_via_service(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    init_integration: MagicMock,
) -> None:
    """Turning on a switch calls the vendor library through the coordinator."""
    init_integration.async_switch_operation.side_effect = _apply_switch_operation
    motion_entry = next(
        entry
        for entry in er.async_entries_for_config_entry(
            entity_registry, mock_config_entry.entry_id
        )
        if entry.unique_id == "d1$motion_detect"
    )

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: motion_entry.entity_id},
        blocking=True,
    )

    init_integration.async_switch_operation.assert_awaited_once()
    call = init_integration.async_switch_operation.await_args
    assert call is not None
    assert call.args[1] == PARAM_MOTION_DETECT
    assert call.args[2] is True
    assert hass.states.get(motion_entry.entity_id).state == "on"


@pytest.mark.parametrize("imou_mock_devices", [SWITCH_MOCK_DEVICES], indirect=True)
@pytest.mark.usefixtures("init_integration")
async def test_turn_off_via_service(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    init_integration: MagicMock,
) -> None:
    """Turning off a switch calls the vendor library through the coordinator."""
    init_integration.async_switch_operation.side_effect = _apply_switch_operation
    header_entry = next(
        entry
        for entry in er.async_entries_for_config_entry(
            entity_registry, mock_config_entry.entry_id
        )
        if entry.unique_id == "d1$header_detect"
    )

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: header_entry.entity_id},
        blocking=True,
    )

    init_integration.async_switch_operation.assert_awaited_once()
    call = init_integration.async_switch_operation.await_args
    assert call is not None
    assert call.args[1] == PARAM_HEADER_DETECT
    assert call.args[2] is False
    assert hass.states.get(header_entry.entity_id).state == "off"


@pytest.mark.parametrize("imou_mock_devices", [SWITCH_MOCK_DEVICES], indirect=True)
@pytest.mark.usefixtures("init_integration")
async def test_turn_on_service_propagates_api_error(
    hass: HomeAssistant,
    init_integration: MagicMock,
) -> None:
    """Imou API errors from async_switch_operation surface to the service call."""
    init_integration.async_switch_operation.side_effect = ImouException("cloud failure")

    entity_id = hass.states.async_all("switch")[0].entity_id

    with pytest.raises(HomeAssistantError, match="cloud failure"):
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_ON,
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
                button_keys=(),
                switches={PARAM_MOTION_DETECT: {PARAM_STATE: False}},
            )
        ]
    ],
    indirect=True,
)
@pytest.mark.usefixtures("init_integration")
async def test_turn_off_unavailable_offline_device_via_service(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    mock_imou_ha_device_manager: MagicMock,
    init_integration: MagicMock,
) -> None:
    """Turning off an offline device does not call the vendor library."""
    motion_entry = next(
        entry
        for entry in er.async_entries_for_config_entry(
            entity_registry, mock_config_entry.entry_id
        )
        if entry.unique_id == "d1$motion_detect"
    )

    async def set_device_offline(device: ImouHaDevice) -> None:
        device._sensors[PARAM_STATUS] = {PARAM_STATE: DeviceStatus.OFFLINE.value}

    mock_imou_ha_device_manager.async_update_device_status.side_effect = (
        set_device_offline
    )
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert hass.states.get(motion_entry.entity_id).state == STATE_UNAVAILABLE

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: motion_entry.entity_id},
        blocking=True,
    )

    init_integration.async_switch_operation.assert_not_called()


@pytest.mark.parametrize("imou_mock_devices", [SWITCH_MOCK_DEVICES], indirect=True)
@pytest.mark.usefixtures("init_integration")
async def test_entities_removed_when_device_leaves_account(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    mock_imou_ha_device_manager: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Switch entities are removed when the device is no longer on the account."""
    motion_entry = next(
        entry
        for entry in er.async_entries_for_config_entry(
            entity_registry, mock_config_entry.entry_id
        )
        if entry.unique_id == "d1$motion_detect"
    )
    assert hass.states.get(motion_entry.entity_id).state != STATE_UNAVAILABLE

    mock_imou_ha_device_manager.async_get_devices.return_value = []

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert (
        er.async_entries_for_config_entry(entity_registry, mock_config_entry.entry_id)
        == []
    )
    assert hass.states.get(motion_entry.entity_id) is None
