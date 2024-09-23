"""Test VoIP binary sensor devices."""

import pytest

from homeassistant.components.voip.devices import VoIPDevice
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_call_in_progress(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    voip_device: VoIPDevice,
) -> None:
    """Test call in progress."""
    state = hass.states.get("binary_sensor.192_168_1_210_call_in_progress")
    assert state is not None
    assert state.state == "off"

    voip_device.set_is_active(True)

    state = hass.states.get("binary_sensor.192_168_1_210_call_in_progress")
    assert state.state == "on"

    voip_device.set_is_active(False)

    state = hass.states.get("binary_sensor.192_168_1_210_call_in_progress")
    assert state.state == "off"


@pytest.mark.usefixtures("voip_device")
async def test_assist_in_progress_disabled_by_default(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test assist in progress binary sensor is added disabled."""

    assert not hass.states.get("binary_sensor.192_168_1_210_call_in_progress")
    entity_entry = entity_registry.async_get(
        "binary_sensor.192_168_1_210_call_in_progress"
    )
    assert entity_entry
    assert entity_entry.disabled
    assert entity_entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION
