"""Tests for the Hinen switch platform."""

from unittest.mock import AsyncMock, patch

from homeassistant.components.hinen.const import CD_PERIOD_TIMES2
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er


async def test_switches_added_correctly(hass: HomeAssistant, setup_integration) -> None:
    """Test switches are added correctly."""
    await setup_integration()
    await hass.async_block_till_done()
    entity_registry = er.async_get(hass)

    for period_index in range(6):
        entity_id = f"switch.test_hinen_device_cd_period_{period_index + 1}_enable"
        entity = entity_registry.async_get(entity_id)
        assert entity is not None
        unique_id = f"{entity.config_entry_id}_device_12345_cd_period_times_{period_index + 1}_enable"

        assert entity is not None
        assert entity.unique_id == unique_id


async def test_switch_states(hass: HomeAssistant, setup_integration) -> None:
    """Test switch states are correctly reported."""
    await setup_integration()
    await hass.async_block_till_done()
    for period_index in range(6):
        entity_id = f"switch.test_hinen_device_cd_period_{period_index + 1}_enable"
        state = hass.states.get(entity_id)
        assert state is not None
        assert state.state == "on"


async def test_switch_turn_on(hass: HomeAssistant, setup_integration) -> None:
    """Test turning on a switch."""
    mock_hinen = await setup_integration()
    await hass.async_block_till_done()
    with patch.object(mock_hinen, "set_property") as mock_set_property:
        await hass.services.async_call(
            "switch",
            "turn_on",
            {"entity_id": "switch.test_hinen_device_cd_period_1_enable"},
            blocking=True,
        )

        mock_set_property.assert_called_once()
        args, kwargs = mock_set_property.call_args

        cd_period_times = args[0]
        device_id = args[1]
        property_key = args[2]

        assert property_key == CD_PERIOD_TIMES2
        assert device_id == "device_12345"

        assert len(cd_period_times) >= 1
        assert cd_period_times[0]["periodEnable"] == 1


async def test_switch_turn_off(hass: HomeAssistant, setup_integration) -> None:
    """Test turning off a switch."""
    mock_hinen = await setup_integration()
    await hass.async_block_till_done()
    with patch.object(
        mock_hinen, "set_property", new_callable=AsyncMock
    ) as mock_set_property:
        await hass.services.async_call(
            "switch",
            "turn_off",
            {"entity_id": "switch.test_hinen_device_cd_period_1_enable"},
            blocking=True,
        )

        mock_set_property.assert_called_once()
        args, kwargs = mock_set_property.call_args

        cd_period_times = args[0]
        device_id = args[1]
        property_key = args[2]

        assert property_key == CD_PERIOD_TIMES2
        assert device_id == "device_12345"

        assert len(cd_period_times) >= 1
        assert cd_period_times[0]["periodEnable"] == 0
