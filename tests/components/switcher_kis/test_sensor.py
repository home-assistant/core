"""Test the Switcher Sensor Platform."""

import pytest

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import slugify

from . import init_integration
from .consts import DUMMY_PLUG_DEVICE, DUMMY_SWITCHER_DEVICES, DUMMY_WATER_HEATER_DEVICE

DEVICE_SENSORS_TUPLE = (
    (
        DUMMY_PLUG_DEVICE,
        [
            ("power", "power_consumption"),
            ("current", "electric_current"),
        ],
    ),
    (
        DUMMY_WATER_HEATER_DEVICE,
        [
            ("power", "power_consumption"),
            ("current", "electric_current"),
            ("remaining_time", "remaining_time"),
        ],
    ),
)


@pytest.mark.parametrize("mock_bridge", [DUMMY_SWITCHER_DEVICES], indirect=True)
async def test_sensor_platform(hass: HomeAssistant, mock_bridge) -> None:
    """Test sensor platform."""
    entry = await init_integration(hass)
    assert mock_bridge

    assert mock_bridge.is_running is True
    assert len(entry.runtime_data) == 2

    for device, sensors in DEVICE_SENSORS_TUPLE:
        for sensor, field in sensors:
            entity_id = f"sensor.{slugify(device.name)}_{sensor}"
            state = hass.states.get(entity_id)
            assert state.state == str(getattr(device, field))


async def test_sensor_disabled(
    hass: HomeAssistant, entity_registry: er.EntityRegistry, mock_bridge
) -> None:
    """Test sensor disabled by default."""
    await init_integration(hass)
    assert mock_bridge

    mock_bridge.mock_callbacks([DUMMY_WATER_HEATER_DEVICE])
    await hass.async_block_till_done()

    device = DUMMY_WATER_HEATER_DEVICE
    unique_id = f"{device.device_id}-{device.mac_address}-auto_off_set"
    entity_id = f"sensor.{slugify(device.name)}_auto_shutdown"
    entry = entity_registry.async_get(entity_id)

    assert entry
    assert entry.unique_id == unique_id
    assert entry.disabled is True
    assert entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION

    # Test enabling entity
    updated_entry = entity_registry.async_update_entity(
        entry.entity_id, disabled_by=None
    )

    assert updated_entry != entry
    assert updated_entry.disabled is False


@pytest.mark.parametrize("mock_bridge", [[DUMMY_WATER_HEATER_DEVICE]], indirect=True)
async def test_sensor_update(
    hass: HomeAssistant, mock_bridge, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test sensor update."""
    await init_integration(hass)
    assert mock_bridge

    device = DUMMY_WATER_HEATER_DEVICE
    field = "power_consumption"
    entity_id = f"sensor.{slugify(device.name)}_power"

    state = hass.states.get(entity_id)
    assert state.state == str(getattr(device, field))

    monkeypatch.setattr(device, field, 1431)
    mock_bridge.mock_callbacks([DUMMY_WATER_HEATER_DEVICE])
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state.state == "1431"
