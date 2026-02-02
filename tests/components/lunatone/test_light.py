"""Tests for the Lunatone integration."""

import copy
from unittest.mock import AsyncMock

from lunatone_rest_api_client.models import LineStatus
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.light import ATTR_BRIGHTNESS, DOMAIN as LIGHT_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry

TEST_ENTITY_ID = "light.device_1"


async def test_setup(
    hass: HomeAssistant,
    mock_lunatone_devices: AsyncMock,
    mock_lunatone_info: AsyncMock,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the Lunatone configuration entry loading/unloading."""
    await setup_integration(hass, mock_config_entry)

    entities = hass.states.async_all(Platform.LIGHT)
    for entity_state in entities:
        entity_entry = entity_registry.async_get(entity_state.entity_id)
        assert entity_entry
        assert entity_entry == snapshot(name=f"{entity_entry.entity_id}-entry")
        assert entity_state == snapshot(name=f"{entity_entry.entity_id}-state")


async def test_turn_on_off(
    hass: HomeAssistant,
    mock_lunatone_devices: AsyncMock,
    mock_lunatone_info: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the light can be turned on and off."""
    await setup_integration(hass, mock_config_entry)

    async def fake_update():
        device = mock_lunatone_devices.data.devices[0]
        device.features.switchable.status = not device.features.switchable.status

    mock_lunatone_devices.async_update.side_effect = fake_update

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: TEST_ENTITY_ID},
        blocking=True,
    )

    state = hass.states.get(TEST_ENTITY_ID)
    assert state
    assert state.state == STATE_ON

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: TEST_ENTITY_ID},
        blocking=True,
    )

    state = hass.states.get(TEST_ENTITY_ID)
    assert state
    assert state.state == STATE_OFF


async def test_turn_on_off_with_brightness(
    hass: HomeAssistant,
    mock_lunatone_devices: AsyncMock,
    mock_lunatone_info: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the light can be turned on with brightness."""
    expected_brightness = 128
    brightness_percentages = iter([50.0, 0.0, 50.0])

    mock_lunatone_devices.set_is_dimmable(True)

    await setup_integration(hass, mock_config_entry)

    async def fake_update():
        brightness = next(brightness_percentages)
        device = mock_lunatone_devices.data.devices[0]
        device.features.switchable.status = brightness > 0
        device.features.dimmable.status = brightness

    mock_lunatone_devices.async_update.side_effect = fake_update

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: TEST_ENTITY_ID, ATTR_BRIGHTNESS: expected_brightness},
        blocking=True,
    )

    state = hass.states.get(TEST_ENTITY_ID)
    assert state
    assert state.state == STATE_ON
    assert state.attributes["brightness"] == expected_brightness

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: TEST_ENTITY_ID},
        blocking=True,
    )

    state = hass.states.get(TEST_ENTITY_ID)
    assert state
    assert state.state == STATE_OFF
    assert not state.attributes["brightness"]

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: TEST_ENTITY_ID},
        blocking=True,
    )

    state = hass.states.get(TEST_ENTITY_ID)
    assert state
    assert state.state == STATE_ON
    assert state.attributes["brightness"] == expected_brightness


async def test_turn_on_off_broadcast(
    hass: HomeAssistant,
    mock_lunatone_info: AsyncMock,
    mock_lunatone_devices: AsyncMock,
    mock_lunatone_dali_broadcast: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the broadcast light can be turned on and off."""
    entity_id = (
        f"light.{mock_config_entry.domain}_{mock_config_entry.unique_id}"
        f"_line{mock_lunatone_dali_broadcast.line}"
    )

    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )

    assert mock_lunatone_dali_broadcast.fade_to_brightness.await_count == 1
    mock_lunatone_dali_broadcast.fade_to_brightness.assert_awaited()

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: entity_id, ATTR_BRIGHTNESS: 128},
        blocking=True,
    )

    assert mock_lunatone_dali_broadcast.fade_to_brightness.await_count == 2
    mock_lunatone_dali_broadcast.fade_to_brightness.assert_awaited()

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )

    assert mock_lunatone_dali_broadcast.fade_to_brightness.await_count == 3
    mock_lunatone_dali_broadcast.fade_to_brightness.assert_awaited()


async def test_line_broadcast_available_status(
    hass: HomeAssistant,
    mock_lunatone_info: AsyncMock,
    mock_lunatone_devices: AsyncMock,
    mock_lunatone_dali_broadcast: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test if the broadcast light is available."""
    entity_id = (
        f"light.{mock_config_entry.domain}_{mock_config_entry.unique_id}"
        f"_line{mock_lunatone_dali_broadcast.line}"
    )

    await setup_integration(hass, mock_config_entry)

    async def fake_update():
        info_data = copy.deepcopy(mock_lunatone_info.data)
        info_data.lines["0"].line_status = LineStatus.NOT_REACHABLE
        mock_lunatone_info.data = info_data

    mock_lunatone_info.async_update.side_effect = fake_update

    state = hass.states.get(entity_id)
    assert state
    assert state.state != "unavailable"

    await mock_config_entry.runtime_data.coordinator_info.async_refresh()
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state
    assert state.state == "unavailable"


async def test_line_broadcast_line_present(
    hass: HomeAssistant,
    mock_lunatone_info: AsyncMock,
    mock_lunatone_devices: AsyncMock,
    mock_lunatone_dali_broadcast: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test if the broadcast light line is present."""
    mock_lunatone_dali_broadcast.line = None

    await setup_integration(hass, mock_config_entry)

    assert not hass.states.async_entity_ids("light")
