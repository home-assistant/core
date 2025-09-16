"""Tests for the Velux select platform."""

from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components.velux.coordinator import Velocity
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
@pytest.mark.usefixtures("mock_module")
async def test_select_entity_options(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the select entity has correct options."""

    mock_config_entry.add_to_hass(hass)
    with patch("homeassistant.components.velux.PLATFORMS", [Platform.SELECT]):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    test_entity_id = "select.test_window_open_close_velocity"

    # Get the select entity state
    select_state = hass.states.get(test_entity_id)
    assert select_state is not None

    # Check that options attribute exists and contains expected velocity options
    options = select_state.attributes.get("options")
    assert options is not None

    # Verify all velocity options are available
    expected_options = [
        velocity.name.lower()
        for velocity in Velocity
        if velocity != Velocity.NOT_AVAILABLE
    ]
    assert set(options) == set(expected_options)


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
@pytest.mark.usefixtures("mock_module")
async def test_select_value_change(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the select entity."""

    mock_config_entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.velux.PLATFORMS", [Platform.SELECT, Platform.COVER]
    ):
        # setup config entry
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    test_select_entity_id = "select.test_window_open_close_velocity"
    test_window_entity_id = "cover.test_window"

    # check entity exists and has Default velocity
    select_state = hass.states.get(test_select_entity_id)
    assert select_state is not None
    assert select_state.state == Velocity.DEFAULT.name.lower()

    # check cover entity exists and has Default velocity
    cover_state = hass.states.get(test_window_entity_id)
    assert cover_state is not None
    assert cover_state.attributes.get("velocity") == Velocity.DEFAULT.name.capitalize()

    # simulate changing velocity to Fast
    await hass.services.async_call(
        "select",
        "select_option",
        {
            "entity_id": test_select_entity_id,
            "option": Velocity.FAST.name.lower(),
        },
        blocking=True,
    )

    # check select entity has updated
    select_state = hass.states.get(test_select_entity_id)
    assert select_state is not None
    assert select_state.state == Velocity.FAST.name.lower()

    # check cover also has updated
    cover_state = hass.states.get(test_window_entity_id)
    assert cover_state is not None
    assert cover_state.attributes.get("velocity") == Velocity.FAST.name.capitalize()


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
@pytest.mark.usefixtures("mock_module")
async def test_select_device_association(
    hass: HomeAssistant,
    mock_window: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the select entity is properly associated with its device."""

    mock_config_entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.velux.PLATFORMS", [Platform.SELECT, Platform.COVER]
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    test_entity_id = "select.test_window_open_close_velocity"
    test_cover_entity_id = "cover.test_window"

    # Get registries
    entity_registry = er.async_get(hass)
    device_registry = dr.async_get(hass)

    # Get entity entry
    select_entity_entry = entity_registry.async_get(test_entity_id)
    assert select_entity_entry is not None
    assert select_entity_entry.device_id is not None

    # Get device entry
    select_device_entry = device_registry.async_get(select_entity_entry.device_id)
    assert select_device_entry is not None

    # Verify device has correct identifiers
    assert ("velux", mock_window.serial_number) in select_device_entry.identifiers
    assert select_device_entry.name == mock_window.name

    # verify device of cover and select are identical
    cover_entity_entry = entity_registry.async_get(test_cover_entity_id)
    assert cover_entity_entry is not None
    assert cover_entity_entry.device_id is not None
    cover_device = device_registry.async_get(cover_entity_entry.device_id)
    assert cover_device == select_device_entry
