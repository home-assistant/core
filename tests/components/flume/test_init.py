"""Test the flume init."""

from collections.abc import Generator
from unittest.mock import patch

import pytest
from requests_mock.mocker import Mocker

from homeassistant import config_entries
from homeassistant.components.flume.const import DOMAIN
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .conftest import USER_ID

from tests.common import MockConfigEntry


@pytest.fixture(autouse=True)
def platforms_fixture() -> Generator[list[str]]:
    """Return the platforms to be loaded for this test."""
    with patch("homeassistant.components.flume.PLATFORMS", [Platform.BINARY_SENSOR]):
        yield


async def test_setup_config_entry(
    hass: HomeAssistant,
    requests_mock: Mocker,
    config_entry: MockConfigEntry,
    access_token: None,
    device_list: None,
) -> None:
    """Test load and unload of a ConfigEntry."""
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is config_entries.ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(config_entry.entry_id)
    assert config_entry.state is config_entries.ConfigEntryState.NOT_LOADED


async def test_device_list_timeout(
    hass: HomeAssistant,
    requests_mock: Mocker,
    config_entry: MockConfigEntry,
    access_token: None,
    device_list_timeout: None,
) -> None:
    """Test load and unload of a ConfigEntry."""
    assert not await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is config_entries.ConfigEntryState.SETUP_RETRY


async def test_reauth_when_unauthorized(
    hass: HomeAssistant,
    requests_mock: Mocker,
    config_entry: MockConfigEntry,
    access_token: None,
    device_list_unauthorized: None,
) -> None:
    """Test load and unload of a ConfigEntry."""
    assert not await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is config_entries.ConfigEntryState.SETUP_ERROR

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["step_id"] == "reauth_confirm"


async def test_list_notifications_service(
    hass: HomeAssistant,
    requests_mock: Mocker,
    config_entry: MockConfigEntry,
    access_token: None,
    device_list: None,
    notifications_list: None,
) -> None:
    """Test load and unload of a ConfigEntry."""
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is config_entries.ConfigEntryState.LOADED

    response = await hass.services.async_call(
        DOMAIN,
        "list_notifications",
        {},
        target={
            "config_entry": config_entry.entry_id,
        },
        blocking=True,
        return_response=True,
    )
    notifications = response.get("notifications")
    assert notifications
    assert len(notifications) == 1
    assert notifications[0].get("user_id") == USER_ID


async def test_list_notifications_service_config_entry_errors(
    hass: HomeAssistant,
    requests_mock: Mocker,
    config_entry: MockConfigEntry,
    access_token: None,
    device_list: None,
    notifications_list: None,
) -> None:
    """Test load and unload of a ConfigEntry."""
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is config_entries.ConfigEntryState.LOADED
    assert await hass.config_entries.async_unload(config_entry.entry_id)
    assert config_entry.state is config_entries.ConfigEntryState.NOT_LOADED

    with pytest.raises(ValueError, match="Config entry not loaded"):
        await hass.services.async_call(
            DOMAIN,
            "list_notifications",
            {},
            target={
                "config_entry": config_entry.entry_id,
            },
            blocking=True,
            return_response=True,
        )

    with pytest.raises(ValueError, match="Invalid config entry: does-not-exist"):
        await hass.services.async_call(
            DOMAIN,
            "list_notifications",
            {},
            target={
                "config_entry": "does-not-exist",
            },
            blocking=True,
            return_response=True,
        )
