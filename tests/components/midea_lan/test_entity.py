"""Tests for midea_lan entity behavior via loaded platforms."""

from collections.abc import Callable

from midealocal.devices.ac import DeviceAttributes as ACAttributes
import pytest

from homeassistant.core import CoreState, HomeAssistant

from . import setup_integration
from .conftest import DummyDevice, default_ac_device, entity_entries
from .const import TEST_DEVICE_ID

from tests.common import MockConfigEntry


@pytest.mark.parametrize(
    (
        "update",
        "status",
        "availability",
        "expected_current_temp",
        "expected_unavailable",
    ),
    [
        pytest.param(
            {ACAttributes.indoor_temperature: 24.0},
            {"available": True},
            True,
            24.0,
            False,
            id="temperature_update",
        ),
        pytest.param(
            {},
            {"available": False},
            False,
            None,
            True,
            id="availability_update",
        ),
        pytest.param(
            {ACAttributes.indoor_temperature: 24.0},
            {"power": True, ACAttributes.indoor_temperature: 24.0},
            True,
            24.0,
            False,
            id="attribute_update_without_available_key",
        ),
    ],
)
async def test_entity_updates_from_device_callback(
    hass: HomeAssistant,
    mock_config_entry: Callable[[DummyDevice], MockConfigEntry],
    update: dict[str, float],
    status: dict[str, bool | float],
    availability: bool,
    expected_current_temp: float | None,
    expected_unavailable: bool,
) -> None:
    """Test entity callback updates state and availability."""
    device = default_ac_device()
    config_entry = mock_config_entry(device)
    await setup_integration(hass, config_entry, device)

    entity_entry = entity_entries(hass, config_entry)[f"{TEST_DEVICE_ID}_climate"]

    assert (state := hass.states.get(entity_entry.entity_id))
    assert state.attributes["current_temperature"] == 21.0
    assert state.state != "unavailable"

    device.attributes.update(update)
    device.available = availability
    device.notify_update(status)
    await hass.async_block_till_done()

    assert (state := hass.states.get(entity_entry.entity_id))
    assert state.attributes.get("current_temperature") == expected_current_temp
    assert (state.state == "unavailable") is expected_unavailable


async def test_entity_callback_ignored_while_hass_stopping(
    hass: HomeAssistant,
    mock_config_entry: Callable[[DummyDevice], MockConfigEntry],
) -> None:
    """Test update callback does not schedule updates while Home Assistant stops."""
    device = default_ac_device()
    config_entry = mock_config_entry(device)
    await setup_integration(hass, config_entry, device)

    entity_entry = entity_entries(hass, config_entry)[f"{TEST_DEVICE_ID}_climate"]

    assert hass.states.get(entity_entry.entity_id) is not None

    device.attributes[ACAttributes.indoor_temperature] = 25.0
    hass.set_state(CoreState.stopping)
    device.notify_update({"available": True})
    await hass.async_block_till_done()

    assert (state := hass.states.get(entity_entry.entity_id))
    assert state.attributes["current_temperature"] == 21.0
