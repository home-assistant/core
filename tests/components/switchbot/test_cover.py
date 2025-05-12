"""Test the switchbot covers."""

from collections.abc import Callable
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from switchbot import SwitchbotModel
from switchbot.devices.device import SwitchbotOperationError
from syrupy import SnapshotAssertion

from homeassistant.components.bluetooth import BluetoothServiceInfoBleak
from homeassistant.components.cover import (
    ATTR_CURRENT_POSITION,
    ATTR_CURRENT_TILT_POSITION,
    ATTR_POSITION,
    ATTR_TILT_POSITION,
    DOMAIN as COVER_DOMAIN,
    CoverState,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_CLOSE_COVER,
    SERVICE_CLOSE_COVER_TILT,
    SERVICE_OPEN_COVER,
    SERVICE_OPEN_COVER_TILT,
    SERVICE_SET_COVER_POSITION,
    SERVICE_SET_COVER_TILT_POSITION,
    SERVICE_STOP_COVER,
    SERVICE_STOP_COVER_TILT,
    STATE_UNKNOWN,
    Platform,
)
from homeassistant.core import HomeAssistant, State
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from . import (
    ROLLER_SHADE_SERVICE_INFO,
    WOBLINDTILT_SERVICE_INFO,
    WOCURTAIN3_SERVICE_INFO,
    make_advertisement,
    setup_integration,
    snapshot_switchbot_entities,
)

from tests.common import MockConfigEntry, mock_restore_cache
from tests.components.bluetooth import inject_bluetooth_service_info


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_entities(
    hass: HomeAssistant,
    switchbot_device: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the Switchbot entities."""
    await setup_integration(hass, mock_config_entry)

    snapshot_switchbot_entities(hass, entity_registry, snapshot, Platform.COVER)


@pytest.mark.parametrize("switchbot_model", [SwitchbotModel.CURTAIN])
async def test_curtain3_setup(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test setting up the Curtain3."""

    entity_id = "cover.test_name"
    mock_restore_cache(
        hass,
        [
            State(
                entity_id,
                CoverState.OPEN,
                {ATTR_CURRENT_POSITION: 50},
            )
        ],
    )

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get(entity_id)
    assert state.state == CoverState.OPEN
    assert state.attributes[ATTR_CURRENT_POSITION] == 50


@pytest.mark.parametrize("switchbot_model", [SwitchbotModel.CURTAIN])
@pytest.mark.parametrize(
    ("manufacturer_data", "expected_state", "current_position"),
    [
        (
            b"\xcf;Zwu\x0c\x19\x0b\x05\x11D\x006",
            CoverState.OPEN,
            95,
        ),
        (
            b"\xcf;Zwu\x0c\x19\x0b\x58\x11D\x006",
            CoverState.CLOSED,
            12,
        ),
        (
            b"\xcf;Zwu\x0c\x19\x0b\x3c\x11D\x006",
            CoverState.OPEN,
            40,
        ),
        (
            b"\xcf;Zwu\x0c\x19\x0b(\x11D\x006",
            CoverState.OPEN,
            60,
        ),
    ],
)
async def test_curtain3_state_updates(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    manufacturer_data: bytes,
    expected_state: CoverState,
    current_position: int,
) -> None:
    """Test Curtain3 controlling."""

    await setup_integration(hass, mock_config_entry)

    entity_id = "cover.test_name"
    address = "AA:BB:CC:DD:EE:FF"
    service_data = b"{\xc06\x00\x11D"

    state = hass.states.get(entity_id)
    assert state.state == STATE_UNKNOWN
    assert ATTR_CURRENT_POSITION not in state.attributes

    inject_bluetooth_service_info(
        hass, make_advertisement(address, manufacturer_data, service_data)
    )
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state.state == expected_state
    assert state.attributes[ATTR_CURRENT_POSITION] == current_position


@pytest.mark.parametrize("switchbot_model", [SwitchbotModel.CURTAIN])
@pytest.mark.parametrize(
    ("service", "extra_service_data", "method", "args"),
    [
        (SERVICE_OPEN_COVER, {}, "open", []),
        (SERVICE_CLOSE_COVER, {}, "close", []),
        (SERVICE_STOP_COVER, {}, "stop", []),
        (
            SERVICE_SET_COVER_POSITION,
            {ATTR_POSITION: 50},
            "set_position",
            [50],
        ),
    ],
)
async def test_curtain3_controlling(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_switchbot_curtain: dict[str, AsyncMock],
    service: str,
    extra_service_data: dict[str, Any],
    method: str,
    args: list[Any],
) -> None:
    """Test Curtain3 controlling."""

    await setup_integration(hass, mock_config_entry)
    entity_id = "cover.test_name"

    await hass.services.async_call(
        COVER_DOMAIN,
        service,
        {ATTR_ENTITY_ID: entity_id} | extra_service_data,
        blocking=True,
    )
    mock_switchbot_curtain[method].assert_awaited_once_with(*args)


async def test_blindtilt_setup(
    hass: HomeAssistant, mock_entry_factory: Callable[[str], MockConfigEntry]
) -> None:
    """Test setting up the blindtilt."""
    inject_bluetooth_service_info(hass, WOBLINDTILT_SERVICE_INFO)

    entry = mock_entry_factory(sensor_type="blind_tilt")
    entity_id = "cover.test_name"
    mock_restore_cache(
        hass,
        [
            State(
                entity_id,
                CoverState.OPEN,
                {ATTR_CURRENT_TILT_POSITION: 40},
            )
        ],
    )

    entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.switchbot.cover.switchbot.SwitchbotBlindTilt.update",
        new=AsyncMock(return_value=True),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        state = hass.states.get(entity_id)
        assert state.state == CoverState.OPEN
        assert state.attributes[ATTR_CURRENT_TILT_POSITION] == 40


async def test_blindtilt_controlling(
    hass: HomeAssistant, mock_entry_factory: Callable[[str], MockConfigEntry]
) -> None:
    """Test blindtilt controlling."""
    inject_bluetooth_service_info(hass, WOBLINDTILT_SERVICE_INFO)

    entry = mock_entry_factory(sensor_type="blind_tilt")
    entry.add_to_hass(hass)
    info = {
        "motionDirection": {
            "opening": False,
            "closing": False,
            "up": False,
            "down": False,
        },
    }
    with (
        patch(
            "homeassistant.components.switchbot.cover.switchbot.SwitchbotBlindTilt.get_basic_info",
            new=AsyncMock(return_value=info),
        ),
        patch(
            "homeassistant.components.switchbot.cover.switchbot.SwitchbotBlindTilt.open",
            new=AsyncMock(return_value=True),
        ) as mock_open,
        patch(
            "homeassistant.components.switchbot.cover.switchbot.SwitchbotBlindTilt.close",
            new=AsyncMock(return_value=True),
        ) as mock_close,
        patch(
            "homeassistant.components.switchbot.cover.switchbot.SwitchbotBlindTilt.stop",
            new=AsyncMock(return_value=True),
        ) as mock_stop,
        patch(
            "homeassistant.components.switchbot.cover.switchbot.SwitchbotBlindTilt.set_position",
            new=AsyncMock(return_value=True),
        ) as mock_set_position,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        entity_id = "cover.test_name"
        address = "AA:BB:CC:DD:EE:FF"
        service_data = b"x\x00*"

        # Test open
        manufacturer_data = b"\xfbgA`\x98\xe8\x1d%F\x12\x85"
        await hass.services.async_call(
            COVER_DOMAIN,
            SERVICE_OPEN_COVER_TILT,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )
        with patch(
            "homeassistant.components.switchbot.cover.switchbot.SwitchbotBlindTilt.get_basic_info",
            return_value=info,
        ):
            inject_bluetooth_service_info(
                hass, make_advertisement(address, manufacturer_data, service_data)
            )
            await hass.async_block_till_done()

            mock_open.assert_awaited_once()

            state = hass.states.get(entity_id)
            assert state.state == CoverState.OPEN
            assert state.attributes[ATTR_CURRENT_TILT_POSITION] == 70

        # Test close
        manufacturer_data = b"\xfbgA`\x98\xe8\x1d%\x0f\x12\x85"
        await hass.services.async_call(
            COVER_DOMAIN,
            SERVICE_CLOSE_COVER_TILT,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )
        with patch(
            "homeassistant.components.switchbot.cover.switchbot.SwitchbotBlindTilt.get_basic_info",
            return_value=info,
        ):
            inject_bluetooth_service_info(
                hass, make_advertisement(address, manufacturer_data, service_data)
            )
            await hass.async_block_till_done()

            mock_close.assert_awaited_once()
            state = hass.states.get(entity_id)
            assert state.state == CoverState.CLOSED
            assert state.attributes[ATTR_CURRENT_TILT_POSITION] == 15

        # Test stop
        manufacturer_data = b"\xfbgA`\x98\xe8\x1d%\n\x12\x85"
        await hass.services.async_call(
            COVER_DOMAIN,
            SERVICE_STOP_COVER_TILT,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )
        with patch(
            "homeassistant.components.switchbot.cover.switchbot.SwitchbotBlindTilt.get_basic_info",
            return_value=info,
        ):
            inject_bluetooth_service_info(
                hass, make_advertisement(address, manufacturer_data, service_data)
            )
            await hass.async_block_till_done()

            mock_stop.assert_awaited_once()
            state = hass.states.get(entity_id)
            assert state.state == CoverState.CLOSED
            assert state.attributes[ATTR_CURRENT_TILT_POSITION] == 10

        # Test set position
        manufacturer_data = b"\xfbgA`\x98\xe8\x1d%2\x12\x85"
        await hass.services.async_call(
            COVER_DOMAIN,
            SERVICE_SET_COVER_TILT_POSITION,
            {ATTR_ENTITY_ID: entity_id, ATTR_TILT_POSITION: 50},
            blocking=True,
        )
        with patch(
            "homeassistant.components.switchbot.cover.switchbot.SwitchbotBlindTilt.get_basic_info",
            return_value=info,
        ):
            inject_bluetooth_service_info(
                hass, make_advertisement(address, manufacturer_data, service_data)
            )
            await hass.async_block_till_done()

            mock_set_position.assert_awaited_once()
            state = hass.states.get(entity_id)
            assert state.state == CoverState.OPEN
            assert state.attributes[ATTR_CURRENT_TILT_POSITION] == 50


async def test_roller_shade_setup(
    hass: HomeAssistant, mock_entry_factory: Callable[[str], MockConfigEntry]
) -> None:
    """Test setting up the RollerShade."""
    inject_bluetooth_service_info(hass, WOCURTAIN3_SERVICE_INFO)

    entry = mock_entry_factory(sensor_type="roller_shade")

    entity_id = "cover.test_name"
    mock_restore_cache(
        hass,
        [
            State(
                entity_id,
                CoverState.OPEN,
                {ATTR_CURRENT_POSITION: 60},
            )
        ],
    )

    entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.switchbot.cover.switchbot.SwitchbotRollerShade.update",
        new=AsyncMock(return_value=True),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        state = hass.states.get(entity_id)
        assert state.state == CoverState.OPEN
        assert state.attributes[ATTR_CURRENT_POSITION] == 60


async def test_roller_shade_controlling(
    hass: HomeAssistant, mock_entry_factory: Callable[[str], MockConfigEntry]
) -> None:
    """Test Roller Shade controlling."""
    inject_bluetooth_service_info(hass, ROLLER_SHADE_SERVICE_INFO)

    entry = mock_entry_factory(sensor_type="roller_shade")
    entry.add_to_hass(hass)
    info = {"battery": 39}
    with (
        patch(
            "homeassistant.components.switchbot.cover.switchbot.SwitchbotRollerShade.get_basic_info",
            new=AsyncMock(return_value=info),
        ),
        patch(
            "homeassistant.components.switchbot.cover.switchbot.SwitchbotRollerShade.open",
            new=AsyncMock(return_value=True),
        ) as mock_open,
        patch(
            "homeassistant.components.switchbot.cover.switchbot.SwitchbotRollerShade.close",
            new=AsyncMock(return_value=True),
        ) as mock_close,
        patch(
            "homeassistant.components.switchbot.cover.switchbot.SwitchbotRollerShade.stop",
            new=AsyncMock(return_value=True),
        ) as mock_stop,
        patch(
            "homeassistant.components.switchbot.cover.switchbot.SwitchbotRollerShade.set_position",
            new=AsyncMock(return_value=True),
        ) as mock_set_position,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        entity_id = "cover.test_name"
        address = "AA:BB:CC:DD:EE:FF"
        service_data = b",\x00'\x9f\x11\x04"

        # Test open
        manufacturer_data = b"\xb0\xe9\xfeT\x90\x1b,\x08\xa0\x11\x04'\x00"
        await hass.services.async_call(
            COVER_DOMAIN,
            SERVICE_OPEN_COVER,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )
        with patch(
            "homeassistant.components.switchbot.cover.switchbot.SwitchbotRollerShade.get_basic_info",
            new=AsyncMock(return_value=info),
        ):
            inject_bluetooth_service_info(
                hass, make_advertisement(address, manufacturer_data, service_data)
            )
            await hass.async_block_till_done()

            mock_open.assert_awaited_once()
            state = hass.states.get(entity_id)
            assert state.state == CoverState.OPEN
            assert state.attributes[ATTR_CURRENT_POSITION] == 68

        # Test close
        manufacturer_data = b"\xb0\xe9\xfeT\x90\x1b,\x08\x5a\x11\x04'\x00"
        await hass.services.async_call(
            COVER_DOMAIN,
            SERVICE_CLOSE_COVER,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )
        with patch(
            "homeassistant.components.switchbot.cover.switchbot.SwitchbotRollerShade.get_basic_info",
            return_value=info,
        ):
            inject_bluetooth_service_info(
                hass, make_advertisement(address, manufacturer_data, service_data)
            )
            await hass.async_block_till_done()

            mock_close.assert_awaited_once()
            state = hass.states.get(entity_id)
            assert state.state == CoverState.CLOSED
            assert state.attributes[ATTR_CURRENT_POSITION] == 10

        # Test stop
        manufacturer_data = b"\xb0\xe9\xfeT\x90\x1b,\x08\x5f\x11\x04'\x00"
        await hass.services.async_call(
            COVER_DOMAIN,
            SERVICE_STOP_COVER,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )
        with patch(
            "homeassistant.components.switchbot.cover.switchbot.SwitchbotRollerShade.get_basic_info",
            return_value=info,
        ):
            inject_bluetooth_service_info(
                hass, make_advertisement(address, manufacturer_data, service_data)
            )
            await hass.async_block_till_done()

            mock_stop.assert_awaited_once()
            state = hass.states.get(entity_id)
            assert state.state == CoverState.CLOSED
            assert state.attributes[ATTR_CURRENT_POSITION] == 5

        # Test set position
        manufacturer_data = b"\xb0\xe9\xfeT\x90\x1b,\x08\x32\x11\x04'\x00"
        await hass.services.async_call(
            COVER_DOMAIN,
            SERVICE_SET_COVER_POSITION,
            {ATTR_ENTITY_ID: entity_id, ATTR_POSITION: 50},
            blocking=True,
        )
        with patch(
            "homeassistant.components.switchbot.cover.switchbot.SwitchbotRollerShade.get_basic_info",
            return_value=info,
        ):
            inject_bluetooth_service_info(
                hass, make_advertisement(address, manufacturer_data, service_data)
            )
            await hass.async_block_till_done()

            mock_set_position.assert_awaited_once()
            state = hass.states.get(entity_id)
            assert state.state == CoverState.OPEN
            assert state.attributes[ATTR_CURRENT_POSITION] == 50


@pytest.mark.parametrize(
    ("exception", "error_message"),
    [
        (
            SwitchbotOperationError("Operation failed"),
            "An error occurred while performing the action: Operation failed",
        ),
    ],
)
@pytest.mark.parametrize(
    (
        "sensor_type",
        "service_info",
        "class_name",
        "service",
        "service_data",
        "mock_method",
    ),
    [
        (
            "curtain",
            WOCURTAIN3_SERVICE_INFO,
            "SwitchbotCurtain",
            SERVICE_CLOSE_COVER,
            {},
            "close",
        ),
        (
            "curtain",
            WOCURTAIN3_SERVICE_INFO,
            "SwitchbotCurtain",
            SERVICE_OPEN_COVER,
            {},
            "open",
        ),
        (
            "curtain",
            WOCURTAIN3_SERVICE_INFO,
            "SwitchbotCurtain",
            SERVICE_STOP_COVER,
            {},
            "stop",
        ),
        (
            "curtain",
            WOCURTAIN3_SERVICE_INFO,
            "SwitchbotCurtain",
            SERVICE_SET_COVER_POSITION,
            {ATTR_POSITION: 50},
            "set_position",
        ),
        (
            "roller_shade",
            ROLLER_SHADE_SERVICE_INFO,
            "SwitchbotRollerShade",
            SERVICE_SET_COVER_POSITION,
            {ATTR_POSITION: 50},
            "set_position",
        ),
        (
            "roller_shade",
            ROLLER_SHADE_SERVICE_INFO,
            "SwitchbotRollerShade",
            SERVICE_OPEN_COVER,
            {},
            "open",
        ),
        (
            "roller_shade",
            ROLLER_SHADE_SERVICE_INFO,
            "SwitchbotRollerShade",
            SERVICE_CLOSE_COVER,
            {},
            "close",
        ),
        (
            "roller_shade",
            ROLLER_SHADE_SERVICE_INFO,
            "SwitchbotRollerShade",
            SERVICE_STOP_COVER,
            {},
            "stop",
        ),
        (
            "blind_tilt",
            WOBLINDTILT_SERVICE_INFO,
            "SwitchbotBlindTilt",
            SERVICE_SET_COVER_TILT_POSITION,
            {ATTR_TILT_POSITION: 50},
            "set_position",
        ),
        (
            "blind_tilt",
            WOBLINDTILT_SERVICE_INFO,
            "SwitchbotBlindTilt",
            SERVICE_OPEN_COVER_TILT,
            {},
            "open",
        ),
        (
            "blind_tilt",
            WOBLINDTILT_SERVICE_INFO,
            "SwitchbotBlindTilt",
            SERVICE_CLOSE_COVER_TILT,
            {},
            "close",
        ),
        (
            "blind_tilt",
            WOBLINDTILT_SERVICE_INFO,
            "SwitchbotBlindTilt",
            SERVICE_STOP_COVER_TILT,
            {},
            "stop",
        ),
    ],
)
async def test_exception_handling_cover_service(
    hass: HomeAssistant,
    mock_entry_factory: Callable[[str], MockConfigEntry],
    sensor_type: str,
    service_info: BluetoothServiceInfoBleak,
    class_name: str,
    service: str,
    service_data: dict,
    mock_method: str,
    exception: Exception,
    error_message: str,
) -> None:
    """Test exception handling for cover service with exception."""
    inject_bluetooth_service_info(hass, service_info)

    entry = mock_entry_factory(sensor_type=sensor_type)
    entry.add_to_hass(hass)
    entity_id = "cover.test_name"

    with patch.multiple(
        f"homeassistant.components.switchbot.cover.switchbot.{class_name}",
        update=AsyncMock(return_value=None),
        **{mock_method: AsyncMock(side_effect=exception)},
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        with pytest.raises(HomeAssistantError, match=error_message):
            await hass.services.async_call(
                COVER_DOMAIN,
                service,
                {**service_data, ATTR_ENTITY_ID: entity_id},
                blocking=True,
            )
