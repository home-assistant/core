"""Provide common Lutron fixtures and mocks."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

from pylutron import OccupancyGroup
import pytest

from homeassistant.components.lutron.const import DOMAIN

from tests.common import MockConfigEntry


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.lutron.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_lutron() -> Generator[MagicMock]:
    """Mock Lutron client."""
    with (
        patch("homeassistant.components.lutron.Lutron", autospec=True) as mock_lutron,
        patch("homeassistant.components.lutron.config_flow.Lutron", new=mock_lutron),
    ):
        client = mock_lutron.return_value
        client.guid = "12345678901"
        client.areas = []

        # Mock an area
        area = MagicMock()
        area.name = "Test Area"
        area.outputs = []
        area.keypads = []
        area.occupancy_group = None
        client.areas.append(area)

        # Mock a light
        light = MagicMock()
        light.name = "Test Light"
        light.id = "light_id"
        light.uuid = "light_uuid"
        light.legacy_uuid = "light_legacy_uuid"
        light.is_dimmable = True
        light.type = "LIGHT"
        light.last_level.return_value = 0
        area.outputs.append(light)

        # Mock a switch
        switch = MagicMock()
        switch.name = "Test Switch"
        switch.id = "switch_id"
        switch.uuid = "switch_uuid"
        switch.legacy_uuid = "switch_legacy_uuid"
        switch.is_dimmable = False
        switch.type = "NON_DIM"
        switch.last_level.return_value = 0
        area.outputs.append(switch)

        # Mock a cover
        cover = MagicMock()
        cover.name = "Test Cover"
        cover.id = "cover_id"
        cover.uuid = "cover_uuid"
        cover.legacy_uuid = "cover_legacy_uuid"
        cover.type = "SYSTEM_SHADE"
        cover.last_level.return_value = 0
        area.outputs.append(cover)

        # Mock a fan
        fan = MagicMock()
        fan.name = "Test Fan"
        fan.uuid = "fan_uuid"
        fan.legacy_uuid = "fan_legacy_uuid"
        fan.type = "CEILING_FAN_TYPE"
        fan.last_level.return_value = 0
        area.outputs.append(fan)

        # Mock a keypad with a button and LED
        keypad = MagicMock()
        keypad.name = "Test Keypad"
        keypad.id = "keypad_id"
        keypad.type = "KEYPAD"
        area.keypads.append(keypad)

        button = MagicMock()
        button.name = "Test Button"
        button.number = 1
        button.button_type = "SingleAction"
        button.uuid = "button_uuid"
        button.legacy_uuid = "button_legacy_uuid"
        keypad.buttons = [button]

        led = MagicMock()
        led.name = "Test LED"
        led.number = 1
        led.uuid = "led_uuid"
        led.legacy_uuid = "led_legacy_uuid"
        led.last_state = 0
        keypad.leds = [led]

        # Mock an occupancy group
        occ_group = MagicMock()
        occ_group.name = "Test Occupancy"
        occ_group.id = "occ_id"
        occ_group.uuid = "occ_uuid"
        occ_group.legacy_uuid = "occ_legacy_uuid"
        occ_group.state = OccupancyGroup.State.VACANT
        area.occupancy_group = occ_group

        yield client


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Mock a Lutron config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            "host": "127.0.0.1",
            "username": "lutron",
            "password": "password",
        },
        unique_id="12345678901",
    )
