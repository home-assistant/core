"""Tests for midea_lan entity behavior via loaded platforms."""

from unittest.mock import patch

from midealocal.const import DeviceType
from midealocal.devices.ac import DeviceAttributes as ACAttributes
import pytest

from homeassistant.components.midea_lan.const import DOMAIN
from homeassistant.const import CONF_TYPE
from homeassistant.core import CoreState, HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import DummyDevice
from .const import BASE_DATA

from tests.common import MockConfigEntry


def _build_ac_device() -> DummyDevice:
    """Create a baseline AC dummy device for entity tests."""
    return DummyDevice(
        DeviceType.AC,
        attributes={
            ACAttributes.power: True,
            ACAttributes.mode: 1,
            ACAttributes.target_temperature: 22.0,
            ACAttributes.indoor_temperature: 21.0,
            ACAttributes.fan_speed: 103,
            ACAttributes.swing_vertical: True,
            ACAttributes.swing_horizontal: True,
            ACAttributes.indoor_humidity: 50,
        },
    )


async def _setup_entity(hass: HomeAssistant, device: DummyDevice) -> str:
    """Set up one AC entry and return created entity_id."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={**BASE_DATA, CONF_TYPE: device.device_type},
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.midea_lan.device_selector",
        return_value=device,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)

    entity_registry = er.async_get(hass)
    entity_entry = er.async_entries_for_config_entry(entity_registry, entry.entry_id)[0]
    return entity_entry.entity_id


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
    ],
)
async def test_entity_updates_from_device_callback(
    hass: HomeAssistant,
    update: dict[str, float],
    status: dict[str, bool],
    availability: bool,
    expected_current_temp: float | None,
    expected_unavailable: bool,
) -> None:
    """Test entity callback updates state and availability."""
    device = _build_ac_device()
    entity_id = await _setup_entity(hass, device)

    assert (state := hass.states.get(entity_id))
    assert state.attributes["current_temperature"] == 21.0
    assert state.state != "unavailable"

    device.attributes.update(update)
    device.available = availability
    device.notify_update(status)
    await hass.async_block_till_done()

    assert (state := hass.states.get(entity_id))
    assert state.attributes.get("current_temperature") == expected_current_temp
    assert (state.state == "unavailable") is expected_unavailable


async def test_entity_callback_ignored_while_hass_stopping(hass: HomeAssistant) -> None:
    """Test update callback does not schedule updates while Home Assistant stops."""
    device = _build_ac_device()
    entity_id = await _setup_entity(hass, device)
    assert hass.states.get(entity_id) is not None

    device.attributes[ACAttributes.indoor_temperature] = 25.0
    hass.set_state(CoreState.stopping)
    device.notify_update({"available": True})
    await hass.async_block_till_done()

    assert (state := hass.states.get(entity_id))
    assert state.attributes["current_temperature"] == 21.0
