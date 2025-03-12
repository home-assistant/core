"""Test the switchbot covers."""

from unittest.mock import AsyncMock, Mock, patch

import pytest

from homeassistant.components.cover import (
    ATTR_CURRENT_POSITION,
    ATTR_CURRENT_TILT_POSITION,
    ATTR_POSITION,
    ATTR_TILT_POSITION,
    DOMAIN as COVER_DOMAIN,
    CoverState,
)
from homeassistant.components.switchbot.const import DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_ADDRESS,
    CONF_NAME,
    CONF_SENSOR_TYPE,
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
from homeassistant.setup import async_setup_component

from . import WOBLINDTILT_SERVICE_INFO, WOCURTAIN3_SERVICE_INFO

from tests.common import MockConfigEntry, mock_restore_cache
from tests.components.bluetooth import inject_bluetooth_service_info


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_curtain3_setup(hass: HomeAssistant) -> None:
    """Test setting up the Curtain3."""
    await async_setup_component(hass, DOMAIN, {})
    inject_bluetooth_service_info(hass, WOCURTAIN3_SERVICE_INFO)

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_ADDRESS: "aa:bb:cc:dd:ee:ff",
            CONF_NAME: "test-name",
            CONF_SENSOR_TYPE: "curtain",
        },
        unique_id="aabbccddeeff",
    )

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

    assert hass.states.get(entity_id).state == CoverState.OPEN
    assert hass.states.get(entity_id).attributes[ATTR_CURRENT_POSITION] == 50


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_curtain3_controlling(hass: HomeAssistant) -> None:
    """Test Curtain3 controlling."""
    await async_setup_component(hass, DOMAIN, {})
    inject_bluetooth_service_info(hass, WOCURTAIN3_SERVICE_INFO)

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_ADDRESS: "aa:bb:cc:dd:ee:ff",
            CONF_NAME: "test-name",
            CONF_SENSOR_TYPE: "curtain",
        },
        unique_id="aabbccddeeff",
    )
    entry.add_to_hass(hass)

    with (
        patch(
            "switchbot.SwitchbotCurtain.open", new=AsyncMock(return_value=True)
        ) as mock_open,
        patch(
            "switchbot.SwitchbotCurtain.close", new=AsyncMock(return_value=True)
        ) as mock_close,
        patch(
            "switchbot.SwitchbotCurtain.stop", new=AsyncMock(return_value=True)
        ) as mock_stop,
        patch(
            "switchbot.SwitchbotCurtain.set_position", new=AsyncMock(return_value=True)
        ) as mock_set_position,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        entity_id = "cover.test_name"
        coordinator = entry.runtime_data

        # Test open
        await hass.services.async_call(
            COVER_DOMAIN, SERVICE_OPEN_COVER, {ATTR_ENTITY_ID: entity_id}, blocking=True
        )
        coordinator.device.parsed_data["position"] = 100
        coordinator.async_update_listeners()
        mock_open.assert_awaited_once()
        assert hass.states.get(entity_id).state == CoverState.OPEN
        assert hass.states.get(entity_id).attributes[ATTR_CURRENT_POSITION] == 100

        # Test close
        await hass.services.async_call(
            COVER_DOMAIN,
            SERVICE_CLOSE_COVER,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )
        coordinator.device.parsed_data["position"] = 0
        coordinator.async_update_listeners()
        mock_close.assert_awaited_once()
        assert hass.states.get(entity_id).state == CoverState.CLOSED
        assert hass.states.get(entity_id).attributes[ATTR_CURRENT_POSITION] == 0

        # Test stop
        await hass.services.async_call(
            COVER_DOMAIN, SERVICE_STOP_COVER, {ATTR_ENTITY_ID: entity_id}, blocking=True
        )
        coordinator.device.parsed_data["position"] = 40
        coordinator.async_update_listeners()
        mock_stop.assert_awaited_once()
        assert hass.states.get(entity_id).state == CoverState.OPEN
        assert hass.states.get(entity_id).attributes[ATTR_CURRENT_POSITION] == 40

        # Test set position
        await hass.services.async_call(
            COVER_DOMAIN,
            SERVICE_SET_COVER_POSITION,
            {ATTR_ENTITY_ID: entity_id, ATTR_POSITION: 50},
            blocking=True,
        )
        coordinator.device.parsed_data["position"] = 60
        coordinator.async_update_listeners()
        mock_set_position.assert_awaited_once()
        assert hass.states.get(entity_id).state == CoverState.OPEN
        assert hass.states.get(entity_id).attributes[ATTR_CURRENT_POSITION] == 60


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_blindtilt_setup(hass: HomeAssistant) -> None:
    """Test setting up the blindtilt."""
    await async_setup_component(hass, DOMAIN, {})
    inject_bluetooth_service_info(hass, WOBLINDTILT_SERVICE_INFO)

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_ADDRESS: "aa:bb:cc:dd:ee:ff",
            CONF_NAME: "test-name",
            CONF_SENSOR_TYPE: "blind_tilt",
        },
        unique_id="aabbccddeeff",
    )

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
    with patch("switchbot.SwitchbotDevice.update", new=Mock(return_value=True)):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        assert hass.states.get(entity_id).state == CoverState.OPEN
        assert hass.states.get(entity_id).attributes[ATTR_CURRENT_TILT_POSITION] == 40


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_blindtilt_controlling(hass: HomeAssistant) -> None:
    """Test blindtilt controlling."""
    await async_setup_component(hass, DOMAIN, {})
    inject_bluetooth_service_info(hass, WOBLINDTILT_SERVICE_INFO)

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_ADDRESS: "aa:bb:cc:dd:ee:ff",
            CONF_NAME: "test-name",
            CONF_SENSOR_TYPE: "blind_tilt",
        },
        unique_id="aabbccddeeff",
    )
    entry.add_to_hass(hass)

    with (
        patch("switchbot.SwitchbotDevice.update", new=Mock(return_value=True)),
        patch(
            "switchbot.SwitchbotBlindTilt.open", new=AsyncMock(return_value=True)
        ) as mock_open,
        patch(
            "switchbot.SwitchbotBlindTilt.close", new=AsyncMock(return_value=True)
        ) as mock_close,
        patch(
            "switchbot.SwitchbotBlindTilt.stop", new=AsyncMock(return_value=True)
        ) as mock_stop,
        patch(
            "switchbot.SwitchbotBlindTilt.set_position",
            new=AsyncMock(return_value=True),
        ) as mock_set_position,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        entity_id = "cover.test_name"
        coordinator = entry.runtime_data

        # Test open
        await hass.services.async_call(
            COVER_DOMAIN,
            SERVICE_OPEN_COVER_TILT,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )
        coordinator.device.parsed_data["tilt"] = 70

        coordinator.device.parsed_data["motionDirection"] = {}
        motionDirection = coordinator.device.parsed_data["motionDirection"]
        motionDirection["opening"] = True
        motionDirection["closing"] = False
        coordinator.device.parsed_data["tilt"] = 70
        coordinator.async_update_listeners()

        mock_open.assert_awaited_once()
        assert hass.states.get(entity_id).state == CoverState.OPENING
        assert hass.states.get(entity_id).attributes[ATTR_CURRENT_TILT_POSITION] == 70

        # Test close
        await hass.services.async_call(
            COVER_DOMAIN,
            SERVICE_CLOSE_COVER_TILT,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )
        coordinator.device.parsed_data["tilt"] = 15
        motionDirection["opening"] = False
        motionDirection["closing"] = True
        coordinator.async_update_listeners()
        mock_close.assert_awaited_once()
        assert hass.states.get(entity_id).state == CoverState.CLOSING
        assert hass.states.get(entity_id).attributes[ATTR_CURRENT_TILT_POSITION] == 15

        # Test stop
        await hass.services.async_call(
            COVER_DOMAIN,
            SERVICE_STOP_COVER_TILT,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )
        coordinator.device.parsed_data["tilt"] = 10
        motionDirection["opening"] = True
        motionDirection["closing"] = False
        coordinator.async_update_listeners()
        mock_stop.assert_awaited_once()
        assert hass.states.get(entity_id).state == CoverState.OPENING
        assert hass.states.get(entity_id).attributes[ATTR_CURRENT_TILT_POSITION] == 10

        # Test set position
        await hass.services.async_call(
            COVER_DOMAIN,
            SERVICE_SET_COVER_TILT_POSITION,
            {ATTR_ENTITY_ID: entity_id, ATTR_TILT_POSITION: 50},
            blocking=True,
        )
        coordinator.device.parsed_data["tilt"] = 60
        motionDirection["opening"] = True
        motionDirection["closing"] = False
        coordinator.async_update_listeners()
        mock_set_position.assert_awaited_once()
        assert hass.states.get(entity_id).state == CoverState.OPENING
        assert hass.states.get(entity_id).attributes[ATTR_CURRENT_TILT_POSITION] == 60
