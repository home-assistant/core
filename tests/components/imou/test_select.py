"""Tests for Imou select platform."""

from unittest.mock import MagicMock

from freezegun.api import FrozenDateTimeFactory
from pyimouapi.const import PARAM_CURRENT_OPTION, PARAM_OPTIONS
from pyimouapi.exceptions import ImouException
from pyimouapi.ha_device import DeviceStatus, ImouHaDevice
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.imou.const import (
    PARAM_MODE,
    PARAM_NIGHT_VISION_MODE,
    PARAM_STATE,
    PARAM_STATUS,
)
from homeassistant.components.imou.coordinator import SCAN_INTERVAL
from homeassistant.components.select import DOMAIN as SELECT_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_OPTION,
    SERVICE_SELECT_OPTION,
    STATE_UNAVAILABLE,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from .const import DEFAULT_SELECTS, UNKNOWN_SELECT_KEY, create_online_device

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform


async def _apply_select_option(
    device: ImouHaDevice, select_type: str, option: str
) -> None:
    """Simulate the vendor API updating select state after a command."""
    device.selects[select_type][PARAM_CURRENT_OPTION] = option


SELECT_MOCK_DEVICES = [
    create_online_device(
        "d1",
        "Device 1",
        button_keys=(),
        selects=DEFAULT_SELECTS,
    ),
]


@pytest.mark.parametrize(
    "imou_mock_devices",
    [
        [
            create_online_device(
                "d1",
                "Device 1",
                button_keys=(),
                selects={
                    UNKNOWN_SELECT_KEY: {
                        PARAM_CURRENT_OPTION: "0",
                        PARAM_OPTIONS: ["0", "1"],
                    },
                    PARAM_NIGHT_VISION_MODE: {
                        PARAM_CURRENT_OPTION: "0",
                        PARAM_OPTIONS: ["0", "1", "2", "3"],
                    },
                },
            )
        ]
    ],
    indirect=True,
)
@pytest.mark.usefixtures("init_integration")
async def test_setup_ignores_unknown_select_types(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Unknown select keys from the API are not turned into entities."""
    registry = er.async_get(hass)  # pylint: disable=home-assistant-tests-registry-fixtures
    entries = er.async_entries_for_config_entry(registry, mock_config_entry.entry_id)
    select_entries = [entry for entry in entries if entry.domain == SELECT_DOMAIN]
    assert len(select_entries) == 1
    assert select_entries[0].translation_key == PARAM_NIGHT_VISION_MODE


@pytest.mark.parametrize("imou_mock_devices", [SELECT_MOCK_DEVICES], indirect=True)
@pytest.mark.usefixtures("init_integration")
async def test_select_option_via_domain_service(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    init_integration: MagicMock,
) -> None:
    """Selecting an option calls the vendor library through the coordinator."""
    init_integration.async_select_option.side_effect = _apply_select_option
    mode_entry = next(
        entry
        for entry in er.async_entries_for_config_entry(
            entity_registry, mock_config_entry.entry_id
        )
        if entry.unique_id == "d1$mode"
    )

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: mode_entry.entity_id, ATTR_OPTION: "1"},
        blocking=True,
    )

    init_integration.async_select_option.assert_awaited_once()
    call = init_integration.async_select_option.await_args
    assert call is not None
    assert call.args[1] == PARAM_MODE
    assert call.args[2] == "1"
    assert hass.states.get(mode_entry.entity_id).state == "1"


@pytest.mark.parametrize("imou_mock_devices", [SELECT_MOCK_DEVICES], indirect=True)
@pytest.mark.usefixtures("init_integration")
async def test_select_option_propagates_api_error(
    hass: HomeAssistant,
    init_integration: MagicMock,
) -> None:
    """Imou API errors from async_select_option surface to the service call."""
    init_integration.async_select_option.side_effect = ImouException("cloud failure")

    entity_id = hass.states.async_all("select")[0].entity_id

    with pytest.raises(HomeAssistantError, match="cloud failure"):
        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {ATTR_ENTITY_ID: entity_id, ATTR_OPTION: "1"},
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
                selects={
                    PARAM_NIGHT_VISION_MODE: {
                        PARAM_CURRENT_OPTION: "0",
                        PARAM_OPTIONS: ["0", "1", "2", "3"],
                    }
                },
            )
        ]
    ],
    indirect=True,
)
@pytest.mark.usefixtures("init_integration")
async def test_select_option_unavailable_offline_device(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    mock_imou_ha_device_manager: MagicMock,
    init_integration: MagicMock,
) -> None:
    """Selecting an option on an offline device does not call the vendor library."""
    night_entry = next(
        entry
        for entry in er.async_entries_for_config_entry(
            entity_registry, mock_config_entry.entry_id
        )
        if entry.unique_id == "d1$night_vision_mode"
    )

    async def set_device_offline(device: ImouHaDevice) -> None:
        device._sensors[PARAM_STATUS] = {PARAM_STATE: DeviceStatus.OFFLINE.value}

    mock_imou_ha_device_manager.async_update_device_status.side_effect = (
        set_device_offline
    )
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert hass.states.get(night_entry.entity_id).state == STATE_UNAVAILABLE

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: night_entry.entity_id, ATTR_OPTION: "1"},
        blocking=True,
    )

    init_integration.async_select_option.assert_not_called()


@pytest.mark.parametrize("imou_mock_devices", [SELECT_MOCK_DEVICES], indirect=True)
@pytest.mark.usefixtures("init_integration")
async def test_entities_removed_when_device_leaves_account(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    mock_imou_ha_device_manager: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Select entities are removed when the device is no longer on the account."""
    mode_entry = next(
        entry
        for entry in er.async_entries_for_config_entry(
            entity_registry, mock_config_entry.entry_id
        )
        if entry.unique_id == "d1$mode"
    )
    assert hass.states.get(mode_entry.entity_id).state != STATE_UNAVAILABLE

    mock_imou_ha_device_manager.async_get_devices.return_value = []

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert (
        er.async_entries_for_config_entry(entity_registry, mock_config_entry.entry_id)
        == []
    )
    assert hass.states.get(mode_entry.entity_id) is None
