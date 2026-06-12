"""Tests for Dyson Infrared fan component."""

from unittest.mock import AsyncMock, call, patch

import pytest

from homeassistant.components.dyson_infrared.const import (
    CONF_INFRARED_EMITTER_ENTITY_ID,
)
from homeassistant.components.dyson_infrared.fan import DysonInfraredFan
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_async_setup_entry(hass: HomeAssistant) -> None:
    """Test async setup entry adds a DysonInfraredFan entity."""
    entry = MockConfigEntry(
        domain="dyson_infrared",
        data={CONF_INFRARED_EMITTER_ENTITY_ID: "infrared.test_emitter"},
        entry_id="test_entry_id",
        title="Test Dyson Fan",
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.dyson_infrared.fan.DysonInfraredFan"
    ) as mock_fan:
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    mock_fan.assert_called_once_with(
        "infrared.test_emitter",
        "test_entry_id",
        "Test Dyson Fan",
    )


@pytest.fixture
def fan_entity() -> DysonInfraredFan:
    """Return a DysonInfraredFan test entity."""
    fan = DysonInfraredFan("infrared.test_emitter", "unique_id_123", "Fan Name")
    fan.hass = AsyncMock()
    return fan


async def test_is_on(fan_entity: DysonInfraredFan) -> None:
    """Test is_on property reflects internal state."""
    assert fan_entity.is_on is False
    fan_entity._attr_is_on = True
    assert fan_entity.is_on is True


async def test_async_send_dyson_action(fan_entity: DysonInfraredFan) -> None:
    """Test sending a Dyson action builds and sends the command."""
    with (
        patch(
            "homeassistant.components.dyson_infrared.fan.DysonCoolStateBuilder"
        ) as mock_builder,
        patch.object(fan_entity, "_send_command") as mock_send_command,
    ):
        mock_builder_instance = mock_builder.return_value
        mock_builder_instance.to_command.return_value = "mocked_command"

        await fan_entity._async_send_dyson_action("on")

        mock_builder.assert_called_once_with(action="on")
        mock_builder_instance.to_command.assert_called_once()
        mock_send_command.assert_called_once_with("mocked_command")


async def test_async_turn_on(fan_entity: DysonInfraredFan) -> None:
    """Test async_turn_on sends an on action and updates state."""
    with (
        patch.object(fan_entity, "_async_send_dyson_action") as mock_send_action,
        patch.object(fan_entity, "async_write_ha_state") as mock_write_state,
    ):
        await fan_entity.async_turn_on()

        mock_send_action.assert_called_once_with("on")
        assert fan_entity.is_on is True
        mock_write_state.assert_called_once()


async def test_async_turn_on_with_percentage(fan_entity: DysonInfraredFan) -> None:
    """Test async_turn_on delegates to async_set_percentage when a percentage is provided."""
    with patch.object(fan_entity, "async_set_percentage") as mock_set_percentage:
        await fan_entity.async_turn_on(percentage=70)

        mock_set_percentage.assert_called_once_with(70)


async def test_async_turn_off(fan_entity: DysonInfraredFan) -> None:
    """Test async_turn_off sends an off action and updates state."""
    fan_entity._attr_is_on = True
    with (
        patch.object(fan_entity, "_async_send_dyson_action") as mock_send_action,
        patch.object(fan_entity, "async_write_ha_state") as mock_write_state,
    ):
        await fan_entity.async_turn_off()

        mock_send_action.assert_called_once_with("off")
        assert fan_entity.is_on is False
        mock_write_state.assert_called_once()


async def test_async_set_percentage_zero(fan_entity: DysonInfraredFan) -> None:
    """Test setting percentage to zero turns off the fan."""
    with patch.object(fan_entity, "async_turn_off") as mock_turn_off:
        await fan_entity.async_set_percentage(0)

        mock_turn_off.assert_called_once()


async def test_async_set_percentage_same(fan_entity: DysonInfraredFan) -> None:
    """Test setting the exact same percentage does nothing."""
    fan_entity._attr_percentage = 50
    with (
        patch.object(fan_entity, "_async_send_dyson_action") as mock_send_action,
        patch.object(fan_entity, "async_write_ha_state") as mock_write_state,
    ):
        await fan_entity.async_set_percentage(50)

        mock_send_action.assert_not_called()
        mock_write_state.assert_not_called()


async def test_async_set_percentage_speed_up(fan_entity: DysonInfraredFan) -> None:
    """Test increasing percentage sends multiple speed_up actions and updates state."""
    fan_entity._attr_percentage = 40
    with (
        patch.object(fan_entity, "_async_send_dyson_action") as mock_send_action,
        patch(
            "homeassistant.components.dyson_infrared.fan.asyncio.sleep"
        ) as mock_sleep,
        patch.object(fan_entity, "async_write_ha_state") as mock_write_state,
    ):
        await fan_entity.async_set_percentage(80)

        assert mock_send_action.call_count == 4
        mock_send_action.assert_has_calls([call("speed_up")] * 4)
        assert mock_sleep.call_count == 4

        assert fan_entity._attr_percentage == 80
        assert fan_entity.is_on is True
        mock_write_state.assert_called_once()


async def test_async_set_percentage_speed_down(fan_entity: DysonInfraredFan) -> None:
    """Test decreasing percentage sends multiple speed_down actions and updates state."""
    fan_entity._attr_percentage = 90
    with (
        patch.object(fan_entity, "_async_send_dyson_action") as mock_send_action,
        patch(
            "homeassistant.components.dyson_infrared.fan.asyncio.sleep"
        ) as mock_sleep,
        patch.object(fan_entity, "async_write_ha_state") as mock_write_state,
    ):
        await fan_entity.async_set_percentage(30)
        assert mock_send_action.call_count == 6
        mock_send_action.assert_has_calls([call("speed_down")] * 6)
        assert mock_sleep.call_count == 6

        assert fan_entity._attr_percentage == 30
        assert fan_entity.is_on is True
        mock_write_state.assert_called_once()
