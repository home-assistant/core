"""Test the BraviaTV picture coordinator."""

from unittest.mock import AsyncMock

from pybravia import BraviaError
import pytest

from homeassistant.components.braviatv.const import CONF_USE_PSK, DOMAIN
from homeassistant.components.braviatv.coordinator import (
    BraviaTVCoordinator,
    BraviaTVPictureCoordinator,
)
from homeassistant.const import CONF_HOST, CONF_MAC, CONF_PIN
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

PICTURE_SETTINGS = [
    {
        "target": "brightness",
        "currentValue": 50,
        "candidate": [{"min": 0, "max": 100, "step": 1}],
        "isAvailable": True,
    },
    {
        "target": "pictureMode",
        "currentValue": "vivid",
        "candidate": ["vivid", "standard", "cinema"],
        "isAvailable": True,
    },
]


@pytest.fixture
def config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Return a config entry for the picture coordinator tests."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "localhost",
            CONF_MAC: "AA:BB:CC:DD:EE:FF",
            CONF_USE_PSK: True,
            CONF_PIN: "12345qwerty",
        },
    )
    entry.add_to_hass(hass)
    return entry


def _create_coordinators(
    hass: HomeAssistant, config_entry: MockConfigEntry, is_on: bool
) -> tuple[BraviaTVPictureCoordinator, AsyncMock]:
    """Create a picture coordinator with a mocked client."""
    client = AsyncMock()
    main_coordinator = BraviaTVCoordinator(hass, config_entry, client)
    main_coordinator.is_on = is_on
    return (
        BraviaTVPictureCoordinator(hass, config_entry, client, main_coordinator),
        client,
    )


async def test_async_update_data(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test that picture settings are fetched and keyed by target."""
    coordinator, client = _create_coordinators(hass, config_entry, is_on=True)
    client.get_picture_setting.return_value = PICTURE_SETTINGS

    data = await coordinator._async_update_data()

    assert data is not None
    assert set(data) == {"brightness", "pictureMode"}

    coordinator.data = data
    assert coordinator.get_setting("brightness") == PICTURE_SETTINGS[0]
    assert coordinator.get_setting("not_a_setting") is None


async def test_async_update_data_tv_off(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test that the last known settings are kept when the TV is off."""
    coordinator, client = _create_coordinators(hass, config_entry, is_on=False)
    client.get_picture_setting.return_value = PICTURE_SETTINGS
    coordinator.data = {"brightness": PICTURE_SETTINGS[0]}

    assert await coordinator._async_update_data() == {"brightness": PICTURE_SETTINGS[0]}
    client.get_picture_setting.assert_not_awaited()


async def test_async_update_data_uses_main_coordinator_connection(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test the picture coordinator reuses the main coordinator connection."""
    coordinator, client = _create_coordinators(hass, config_entry, is_on=True)
    coordinator._coordinator.async_connect = AsyncMock()
    client.get_picture_setting.return_value = PICTURE_SETTINGS

    await coordinator._async_update_data()

    coordinator._coordinator.async_connect.assert_awaited_once()
    client.get_picture_setting.assert_awaited_once()


async def test_async_update_data_unsupported(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test that TVs without picture settings support keep no data."""
    coordinator, client = _create_coordinators(hass, config_entry, is_on=True)
    client.get_picture_setting.side_effect = BraviaError("not supported")

    assert await coordinator._async_update_data() is None


async def test_async_set_picture_quality(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test setting a picture quality value sends the command and refreshes."""
    coordinator, client = _create_coordinators(hass, config_entry, is_on=True)
    coordinator.async_request_refresh = AsyncMock()

    await coordinator.async_set_picture_quality("brightness", "75")

    client.set_picture_setting.assert_awaited_once_with("brightness", "75")
    coordinator.async_request_refresh.assert_awaited_once()
