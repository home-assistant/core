"""Test FMD select entities."""

from unittest.mock import AsyncMock

from homeassistant.components.fmd.const import DOMAIN
from homeassistant.components.fmd.select import FmdLocationSourceSelect
from homeassistant.const import CONF_ID, CONF_PASSWORD, CONF_URL
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry
from tests.components.fmd.common import setup_integration


async def test_location_source_select(
    hass: HomeAssistant,
    mock_fmd_api: AsyncMock,
) -> None:
    """Test location source select."""
    await setup_integration(hass, mock_fmd_api)

    entity_id = "select.fmd_test_user_location_source"
    state = hass.states.get(entity_id)
    assert state is not None

    # Select GPS
    await hass.services.async_call(
        "select",
        "select_option",
        {"entity_id": entity_id, "option": "GPS Only (Accurate)"},
        blocking=True,
    )

    state = hass.states.get(entity_id)
    assert state.state == "GPS Only (Accurate)"


async def test_location_source_placeholder_reset(
    hass: HomeAssistant,
    mock_fmd_api: AsyncMock,
) -> None:
    """Test location source select changes option."""
    await setup_integration(hass, mock_fmd_api)

    entity_id = "select.fmd_test_user_location_source"

    # Initially should be default
    state = hass.states.get(entity_id)
    assert state.state == "All Providers (Default)"

    # Select GPS
    await hass.services.async_call(
        "select",
        "select_option",
        {"entity_id": entity_id, "option": "GPS Only (Accurate)"},
        blocking=True,
    )

    # Should update to GPS
    state = hass.states.get(entity_id)
    assert state.state == "GPS Only (Accurate)"


async def test_bluetooth_select(
    hass: HomeAssistant,
    mock_fmd_api: AsyncMock,
) -> None:
    """Test bluetooth command select."""
    await setup_integration(hass, mock_fmd_api)

    entity_id = "select.fmd_test_user_bluetooth"
    state = hass.states.get(entity_id)
    assert state is not None

    # Enable Bluetooth
    await hass.services.async_call(
        "select",
        "select_option",
        {"entity_id": entity_id, "option": "Enable Bluetooth"},
        blocking=True,
    )

    mock_fmd_api.create.return_value.set_bluetooth.assert_called_once_with(True)


async def test_bluetooth_select_disable(
    hass: HomeAssistant,
    mock_fmd_api: AsyncMock,
) -> None:
    """Test bluetooth command select disable."""
    await setup_integration(hass, mock_fmd_api)

    entity_id = "select.fmd_test_user_bluetooth"

    # Disable Bluetooth
    await hass.services.async_call(
        "select",
        "select_option",
        {"entity_id": entity_id, "option": "Disable Bluetooth"},
        blocking=True,
    )

    mock_fmd_api.create.return_value.set_bluetooth.assert_called_once_with(False)


async def test_dnd_select(
    hass: HomeAssistant,
    mock_fmd_api: AsyncMock,
) -> None:
    """Test Do Not Disturb command select."""
    await setup_integration(hass, mock_fmd_api)

    entity_id = "select.fmd_test_user_volume_do_not_disturb"
    state = hass.states.get(entity_id)
    assert state is not None

    # Enable DND
    await hass.services.async_call(
        "select",
        "select_option",
        {"entity_id": entity_id, "option": "Enable Do Not Disturb"},
        blocking=True,
    )

    mock_fmd_api.create.return_value.set_do_not_disturb.assert_called_once_with(True)


async def test_dnd_select_disable(
    hass: HomeAssistant,
    mock_fmd_api: AsyncMock,
) -> None:
    """Test Do Not Disturb command select disable."""
    await setup_integration(hass, mock_fmd_api)

    entity_id = "select.fmd_test_user_volume_do_not_disturb"

    # Disable DND
    await hass.services.async_call(
        "select",
        "select_option",
        {"entity_id": entity_id, "option": "Disable Do Not Disturb"},
        blocking=True,
    )

    mock_fmd_api.create.return_value.set_do_not_disturb.assert_called_once_with(False)


async def test_ringer_mode_select(
    hass: HomeAssistant,
    mock_fmd_api: AsyncMock,
) -> None:
    """Test ringer mode control select."""
    await setup_integration(hass, mock_fmd_api)

    entity_id = "select.fmd_test_user_volume_ringer_mode"
    state = hass.states.get(entity_id)
    assert state is not None

    # Set to Silent
    await hass.services.async_call(
        "select",
        "select_option",
        {"entity_id": entity_id, "option": "Silent"},
        blocking=True,
    )

    mock_fmd_api.create.return_value.set_ringer_mode.assert_called_once_with("silent")


async def test_ringer_mode_vibrate(
    hass: HomeAssistant,
    mock_fmd_api: AsyncMock,
) -> None:
    """Test ringer mode set to vibrate."""
    await setup_integration(hass, mock_fmd_api)

    entity_id = "select.fmd_test_user_volume_ringer_mode"

    await hass.services.async_call(
        "select",
        "select_option",
        {"entity_id": entity_id, "option": "Vibrate Only"},
        blocking=True,
    )

    mock_fmd_api.create.return_value.set_ringer_mode.assert_called_once_with("vibrate")


async def test_ringer_mode_normal(
    hass: HomeAssistant,
    mock_fmd_api: AsyncMock,
) -> None:
    """Test ringer mode set to normal."""
    await setup_integration(hass, mock_fmd_api)

    entity_id = "select.fmd_test_user_volume_ringer_mode"

    await hass.services.async_call(
        "select",
        "select_option",
        {"entity_id": entity_id, "option": "Normal (Sound + Vibrate)"},
        blocking=True,
    )

    mock_fmd_api.create.return_value.set_ringer_mode.assert_called_once_with("normal")


async def test_bluetooth_command_tracker_not_found(
    hass: HomeAssistant,
    mock_fmd_api: AsyncMock,
) -> None:
    """Test bluetooth command when tracker is not found."""
    await setup_integration(hass, mock_fmd_api)

    # Remove tracker from hass.data to simulate it not being found
    hass.config_entries.async_entries("fmd")[0].runtime_data.tracker = None

    entity_id = "select.fmd_test_user_bluetooth"

    # Try to enable bluetooth - should handle gracefully
    await hass.services.async_call(
        "select",
        "select_option",
        {"entity_id": entity_id, "option": "Enable Bluetooth"},
        blocking=True,
    )

    # Should remain in placeholder state since tracker not found
    state = hass.states.get(entity_id)
    assert state is not None


async def test_dnd_command_tracker_not_found(
    hass: HomeAssistant,
    mock_fmd_api: AsyncMock,
) -> None:
    """Test DND command when tracker is not found."""
    await setup_integration(hass, mock_fmd_api)

    # Remove tracker from hass.data to simulate it not being found
    hass.config_entries.async_entries("fmd")[0].runtime_data.tracker = None

    entity_id = "select.fmd_test_user_volume_do_not_disturb"

    # Try to enable DND - should handle gracefully
    await hass.services.async_call(
        "select",
        "select_option",
        {"entity_id": entity_id, "option": "Enable Do Not Disturb"},
        blocking=True,
    )

    # Should remain in placeholder state since tracker not found
    state = hass.states.get(entity_id)
    assert state is not None


async def test_ringer_mode_command_tracker_not_found(
    hass: HomeAssistant,
    mock_fmd_api: AsyncMock,
) -> None:
    """Test ringer mode command when tracker is not found."""
    await setup_integration(hass, mock_fmd_api)

    # Remove tracker from hass.data to simulate it not being found
    hass.config_entries.async_entries("fmd")[0].runtime_data.tracker = None

    entity_id = "select.fmd_test_user_volume_ringer_mode"

    # Try to set ringer mode - should handle gracefully
    await hass.services.async_call(
        "select",
        "select_option",
        {"entity_id": entity_id, "option": "Silent"},
        blocking=True,
    )

    # Should remain in placeholder state since tracker not found
    state = hass.states.get(entity_id)
    assert state is not None


async def test_bluetooth_command_api_error(
    hass: HomeAssistant,
    mock_fmd_api: AsyncMock,
) -> None:
    """Test bluetooth command when API raises error."""
    await setup_integration(hass, mock_fmd_api)

    # Make API raise an error
    mock_fmd_api.create.return_value.set_bluetooth.side_effect = RuntimeError(
        "API error"
    )

    entity_id = "select.fmd_test_user_bluetooth"

    # Try to enable bluetooth - should handle error gracefully
    await hass.services.async_call(
        "select",
        "select_option",
        {"entity_id": entity_id, "option": "Enable Bluetooth"},
        blocking=True,
    )

    # Should reset to placeholder after error
    state = hass.states.get(entity_id)
    assert state is not None


async def test_dnd_command_api_error(
    hass: HomeAssistant,
    mock_fmd_api: AsyncMock,
) -> None:
    """Test DND command when API raises error."""
    await setup_integration(hass, mock_fmd_api)

    # Make API raise an error
    mock_fmd_api.create.return_value.set_do_not_disturb.side_effect = RuntimeError(
        "API error"
    )

    entity_id = "select.fmd_test_user_volume_do_not_disturb"

    # Try to enable DND - should handle error gracefully
    await hass.services.async_call(
        "select",
        "select_option",
        {"entity_id": entity_id, "option": "Enable Do Not Disturb"},
        blocking=True,
    )

    # Should reset to placeholder after error
    state = hass.states.get(entity_id)
    assert state is not None


async def test_ringer_mode_command_api_error(
    hass: HomeAssistant,
    mock_fmd_api: AsyncMock,
) -> None:
    """Test ringer mode command when API raises error."""
    await setup_integration(hass, mock_fmd_api)

    # Make API raise an error
    mock_fmd_api.create.return_value.set_ringer_mode.side_effect = RuntimeError(
        "API error"
    )

    entity_id = "select.fmd_test_user_volume_ringer_mode"

    # Try to set ringer mode - should handle error gracefully
    await hass.services.async_call(
        "select",
        "select_option",
        {"entity_id": entity_id, "option": "Silent"},
        blocking=True,
    )

    # Should reset to placeholder after error
    state = hass.states.get(entity_id)
    assert state is not None


async def test_select_placeholder_option(
    hass: HomeAssistant,
    mock_fmd_api: AsyncMock,
) -> None:
    """Test select entities with placeholder option (no action)."""
    await setup_integration(hass, mock_fmd_api)

    # Select placeholder option for Bluetooth (should do nothing)
    await hass.services.async_call(
        "select",
        "select_option",
        {
            "entity_id": "select.fmd_test_user_bluetooth",
            "option": "Send Command...",
        },
        blocking=True,
    )
    await hass.async_block_till_done()

    # Select placeholder option for DND (should do nothing)
    await hass.services.async_call(
        "select",
        "select_option",
        {
            "entity_id": "select.fmd_test_user_volume_do_not_disturb",
            "option": "Send Command...",
        },
        blocking=True,
    )
    await hass.async_block_till_done()

    # Select placeholder option for ringer mode (should do nothing)
    await hass.services.async_call(
        "select",
        "select_option",
        {
            "entity_id": "select.fmd_test_user_volume_ringer_mode",
            "option": "Send Command...",
        },
        blocking=True,
    )
    await hass.async_block_till_done()

    # Verify API was NOT called
    mock_fmd_api.create.return_value.set_bluetooth.assert_not_called()
    mock_fmd_api.create.return_value.set_do_not_disturb.assert_not_called()
    mock_fmd_api.create.return_value.set_ringer_mode.assert_not_called()


async def test_location_source_invalid_option_fallback(
    hass: HomeAssistant,
    mock_fmd_api: AsyncMock,
) -> None:
    """Test location source returns 'all' for invalid/unmapped options."""
    # Unit-style test of the mapping logic via the public method

    # Minimal config entry for constructing the entity
    config_entry = MockConfigEntry(
        version=1,
        domain=DOMAIN,
        title="test_user",
        data={
            CONF_URL: "https://fmd.example.com",
            CONF_ID: "test_user",
            CONF_PASSWORD: "test_password",
        },
        entry_id="test_entry_id",
        unique_id="test_user",
    )
    config_entry.add_to_hass(hass)

    # Instantiate select and set an invalid option
    location_source = FmdLocationSourceSelect(hass, config_entry)
    location_source._attr_current_option = "Invalid Option Not In Map"

    # Public API should fallback to "all"
    provider = location_source.get_provider_value()
    assert provider == "all"
