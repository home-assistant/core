"""Test Wyoming number."""

from unittest.mock import patch

from homeassistant.components.wyoming.devices import SatelliteDevice
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from . import reload_satellite


async def test_auto_gain_number(
    hass: HomeAssistant,
    satellite_config_entry: ConfigEntry,
    satellite_device: SatelliteDevice,
) -> None:
    """Test automatic gain control number."""
    agc_entity_id = satellite_device.get_auto_gain_entity_id(hass)
    assert agc_entity_id

    state = hass.states.get(agc_entity_id)
    assert state is not None
    assert int(state.state) == 0
    assert satellite_device.auto_gain == 0

    # Change setting
    with patch.object(satellite_device, "set_auto_gain") as mock_agc_changed:
        await hass.services.async_call(
            "number",
            "set_value",
            {"entity_id": agc_entity_id, "value": 31},
            blocking=True,
        )

        state = hass.states.get(agc_entity_id)
        assert state is not None
        assert int(state.state) == 31

        # set function should have been called
        mock_agc_changed.assert_called_once_with(31)

    # test restore
    satellite_device = await reload_satellite(hass, satellite_config_entry.entry_id)

    state = hass.states.get(agc_entity_id)
    assert state is not None
    assert int(state.state) == 31

    await hass.services.async_call(
        "number",
        "set_value",
        {"entity_id": agc_entity_id, "value": 15},
        blocking=True,
    )

    assert satellite_device.auto_gain == 15


async def test_volume_multiplier_number(
    hass: HomeAssistant,
    satellite_config_entry: ConfigEntry,
    satellite_device: SatelliteDevice,
) -> None:
    """Test volume multiplier number."""
    vm_entity_id = satellite_device.get_volume_multiplier_entity_id(hass)
    assert vm_entity_id

    state = hass.states.get(vm_entity_id)
    assert state is not None
    assert float(state.state) == 1.0
    assert satellite_device.volume_multiplier == 1.0

    # Change setting
    with patch.object(satellite_device, "set_volume_multiplier") as mock_vm_changed:
        await hass.services.async_call(
            "number",
            "set_value",
            {"entity_id": vm_entity_id, "value": 2.0},
            blocking=True,
        )

        state = hass.states.get(vm_entity_id)
        assert state is not None
        assert float(state.state) == 2.0

        # set function should have been called
        mock_vm_changed.assert_called_once_with(2.0)

    # test restore
    satellite_device = await reload_satellite(hass, satellite_config_entry.entry_id)

    state = hass.states.get(vm_entity_id)
    assert state is not None
    assert float(state.state) == 2.0

    await hass.services.async_call(
        "number",
        "set_value",
        {"entity_id": vm_entity_id, "value": 0.5},
        blocking=True,
    )

    assert float(satellite_device.volume_multiplier) == 0.5
