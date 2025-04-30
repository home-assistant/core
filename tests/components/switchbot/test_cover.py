"""Test the switchbot covers."""

from collections.abc import Callable
from unittest.mock import AsyncMock, patch

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
)
from homeassistant.core import HomeAssistant, State

from . import (
    ROLLER_SHADE_SERVICE_INFO,
    WOBLINDTILT_SERVICE_INFO,
    WOCURTAIN3_SERVICE_INFO,
    make_advertisement,
)

from tests.common import MockConfigEntry, mock_restore_cache
from tests.components.bluetooth import inject_bluetooth_service_info


async def test_curtain3_setup(
    hass: HomeAssistant, mock_entry_factory: Callable[[str], MockConfigEntry]
) -> None:
    """Test setting up the Curtain3."""
    inject_bluetooth_service_info(hass, WOCURTAIN3_SERVICE_INFO)

    entry = mock_entry_factory(sensor_type="curtain")

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

    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state.state == CoverState.OPEN
    assert state.attributes[ATTR_CURRENT_POSITION] == 50


async def test_curtain3_controlling(
    hass: HomeAssistant, mock_entry_factory: Callable[[str], MockConfigEntry]
) -> None:
    """Test Curtain3 controlling."""
    inject_bluetooth_service_info(hass, WOCURTAIN3_SERVICE_INFO)

    entry = mock_entry_factory(sensor_type="curtain")
    entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.switchbot.cover.switchbot.SwitchbotCurtain.open",
            new=AsyncMock(return_value=True),
        ) as mock_open,
        patch(
            "homeassistant.components.switchbot.cover.switchbot.SwitchbotCurtain.close",
            new=AsyncMock(return_value=True),
        ) as mock_close,
        patch(
            "homeassistant.components.switchbot.cover.switchbot.SwitchbotCurtain.stop",
            new=AsyncMock(return_value=True),
        ) as mock_stop,
        patch(
            "homeassistant.components.switchbot.cover.switchbot.SwitchbotCurtain.set_position",
            new=AsyncMock(return_value=True),
        ) as mock_set_position,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        entity_id = "cover.test_name"
        address = "AA:BB:CC:DD:EE:FF"
        service_data = b"{\xc06\x00\x11D"

        # Test open
        manufacturer_data = b"\xcf;Zwu\x0c\x19\x0b\x05\x11D\x006"
        await hass.services.async_call(
            COVER_DOMAIN, SERVICE_OPEN_COVER, {ATTR_ENTITY_ID: entity_id}, blocking=True
        )
        inject_bluetooth_service_info(
            hass, make_advertisement(address, manufacturer_data, service_data)
        )
        await hass.async_block_till_done()

        mock_open.assert_awaited_once()
        state = hass.states.get(entity_id)
        assert state.state == CoverState.OPEN
        assert state.attributes[ATTR_CURRENT_POSITION] == 95

        # Test close
        manufacturer_data = b"\xcf;Zwu\x0c\x19\x0b\x58\x11D\x006"
        await hass.services.async_call(
            COVER_DOMAIN,
            SERVICE_CLOSE_COVER,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )
        inject_bluetooth_service_info(
            hass, make_advertisement(address, manufacturer_data, service_data)
        )
        await hass.async_block_till_done()

        mock_close.assert_awaited_once()
        state = hass.states.get(entity_id)
        assert state.state == CoverState.CLOSED
        assert state.attributes[ATTR_CURRENT_POSITION] == 12

        # Test stop
        manufacturer_data = b"\xcf;Zwu\x0c\x19\x0b\x3c\x11D\x006"
        await hass.services.async_call(
            COVER_DOMAIN, SERVICE_STOP_COVER, {ATTR_ENTITY_ID: entity_id}, blocking=True
        )
        inject_bluetooth_service_info(
            hass, make_advertisement(address, manufacturer_data, service_data)
        )
        await hass.async_block_till_done()

        mock_stop.assert_awaited_once()
        state = hass.states.get(entity_id)
        assert state.state == CoverState.OPEN
        assert state.attributes[ATTR_CURRENT_POSITION] == 40

        # Test set position
        manufacturer_data = b"\xcf;Zwu\x0c\x19\x0b(\x11D\x006"
        await hass.services.async_call(
            COVER_DOMAIN,
            SERVICE_SET_COVER_POSITION,
            {ATTR_ENTITY_ID: entity_id, ATTR_POSITION: 50},
            blocking=True,
        )
        inject_bluetooth_service_info(
            hass, make_advertisement(address, manufacturer_data, service_data)
        )
        await hass.async_block_till_done()

        mock_set_position.assert_awaited_once()
        state = hass.states.get(entity_id)
        assert state.state == CoverState.OPEN
        assert state.attributes[ATTR_CURRENT_POSITION] == 60


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
