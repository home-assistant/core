"""Tests for the Hinen select platform."""

from unittest.mock import patch

from homeassistant.components.hinen.const import (
    WORK_MODE_BATTERY_PRIORITY,
    WORK_MODE_OPTIONS,
    WORK_MODE_SETTING,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er


async def test_select_added_correctly(hass: HomeAssistant, setup_integration) -> None:
    """Test select entities are added correctly."""
    await setup_integration()
    await hass.async_block_till_done()
    entity_registry = er.async_get(hass)

    work_mode_select_entity = entity_registry.async_get(
        "select.test_hinen_device_work_mode"
    )
    assert work_mode_select_entity is not None
    assert (
        work_mode_select_entity.unique_id
        == f"{work_mode_select_entity.config_entry_id}_device_12345_work_mode_setting"
    )

    assert work_mode_select_entity.capabilities is not None
    assert work_mode_select_entity.capabilities["options"] == list(
        WORK_MODE_OPTIONS.values()
    )

    work_mode_select_state = hass.states.get("select.test_hinen_device_work_mode")
    assert work_mode_select_state is not None
    assert work_mode_select_state.state == "self_consumption"
    assert work_mode_select_state.attributes.get("options") == list(
        WORK_MODE_OPTIONS.values()
    )


async def test_select_option(hass: HomeAssistant, setup_integration) -> None:
    """Test selecting an option."""
    mock_hinen = await setup_integration()
    await hass.async_block_till_done()
    with patch.object(mock_hinen, "set_property") as mock_set_device_work_mode:
        await hass.services.async_call(
            "select",
            "select_option",
            {
                "entity_id": "select.test_hinen_device_work_mode",
                "option": "battery_priority",
            },
            blocking=True,
        )

        mock_set_device_work_mode.assert_called_once_with(
            WORK_MODE_BATTERY_PRIORITY, "device_12345", WORK_MODE_SETTING
        )
