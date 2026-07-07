"""Test AfterShip services."""

from unittest.mock import AsyncMock

from homeassistant.components.aftership.const import (
    CONF_SLUG,
    CONF_TITLE,
    CONF_TRACKING_NUMBER,
    DOMAIN,
    SERVICE_ADD_TRACKING,
    SERVICE_REMOVE_TRACKING,
)
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def setup_integration(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Set up the AfterShip integration for testing."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()


async def test_add_tracking(
    hass: HomeAssistant,
    mock_aftership: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the add_tracking service forwards all fields to the client."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        DOMAIN,
        SERVICE_ADD_TRACKING,
        {
            CONF_TRACKING_NUMBER: "123456789",
            CONF_TITLE: "Laptop",
            CONF_SLUG: "usps",
        },
        blocking=True,
    )

    mock_aftership.trackings.add.assert_called_once_with(
        tracking_number="123456789",
        title="Laptop",
        slug="usps",
    )


async def test_add_tracking_only_required(
    hass: HomeAssistant,
    mock_aftership: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the add_tracking service with only the required field."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        DOMAIN,
        SERVICE_ADD_TRACKING,
        {CONF_TRACKING_NUMBER: "123456789"},
        blocking=True,
    )

    mock_aftership.trackings.add.assert_called_once_with(
        tracking_number="123456789",
        title=None,
        slug=None,
    )


async def test_remove_tracking(
    hass: HomeAssistant,
    mock_aftership: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the remove_tracking service forwards all fields to the client."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        DOMAIN,
        SERVICE_REMOVE_TRACKING,
        {
            CONF_TRACKING_NUMBER: "123456789",
            CONF_SLUG: "usps",
        },
        blocking=True,
    )

    mock_aftership.trackings.remove.assert_called_once_with(
        tracking_number="123456789",
        slug="usps",
    )
