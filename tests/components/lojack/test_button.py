"""Tests for the LoJack button platform."""

from unittest.mock import AsyncMock

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant

from .const import TEST_MAKE, TEST_MODEL, TEST_YEAR

from tests.common import MockConfigEntry

# Expected entity ID based on device name pattern: {year} {make} {model}
EXPECTED_BUTTON_ENTITY_ID = f"button.{TEST_YEAR.lower()}_{TEST_MAKE.lower()}_{TEST_MODEL.lower()}_refresh_location"


async def test_button_setup(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_lojack_client: AsyncMock,
) -> None:
    """Test button entity is created."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(EXPECTED_BUTTON_ENTITY_ID)
    assert state is not None


async def test_button_press(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_lojack_client: AsyncMock,
    mock_device: AsyncMock,
) -> None:
    """Test pressing the refresh location button."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Press the button
    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: EXPECTED_BUTTON_ENTITY_ID},
        blocking=True,
    )

    # Verify request_fresh_location was called
    mock_device.request_fresh_location.assert_called_once()


async def test_button_press_device_not_found(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_lojack_client: AsyncMock,
) -> None:
    """Test pressing button when device is not found."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Clear the devices list for subsequent calls
    mock_lojack_client.list_devices.return_value = []

    # Press the button - should not raise an error
    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: EXPECTED_BUTTON_ENTITY_ID},
        blocking=True,
    )


async def test_button_press_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_lojack_client: AsyncMock,
    mock_device: AsyncMock,
) -> None:
    """Test pressing button when API call fails."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Make request_fresh_location raise an error
    mock_device.request_fresh_location.side_effect = Exception("API Error")

    # Press the button - should not raise an error (handled gracefully)
    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: EXPECTED_BUTTON_ENTITY_ID},
        blocking=True,
    )
