"""Test the GitHub init file."""

from unittest.mock import AsyncMock

import pytest

from homeassistant.components.github import CONF_REPOSITORIES
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er, icon

from . import setup_integration

from tests.common import MockConfigEntry


async def test_device_registry_cleanup(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
    github_client: AsyncMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that we remove untracked repositories from the device registry."""
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_config_entry,
        options={CONF_REPOSITORIES: ["home-assistant/core"]},
    )
    await setup_integration(hass, mock_config_entry)

    devices = dr.async_entries_for_config_entry(
        registry=device_registry,
        config_entry_id=mock_config_entry.entry_id,
    )

    assert len(devices) == 1

    hass.config_entries.async_update_entry(
        mock_config_entry,
        options={CONF_REPOSITORIES: []},
    )
    assert await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert (
        f"Unlinking device {devices[0].id} for untracked repository home-assistant/core from config entry {mock_config_entry.entry_id}"
        in caplog.text
    )

    devices = dr.async_entries_for_config_entry(
        registry=device_registry,
        config_entry_id=mock_config_entry.entry_id,
    )

    assert len(devices) == 0


async def test_subscription_setup(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    github_client: AsyncMock,
) -> None:
    """Test that we setup event subscription."""
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_config_entry,
        options={CONF_REPOSITORIES: ["home-assistant/core"]},
        pref_disable_polling=False,
    )
    await setup_integration(hass, mock_config_entry)
    github_client.repos.events.subscribe.assert_called_once()


async def test_subscription_setup_polling_disabled(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    github_client: AsyncMock,
) -> None:
    """Test that we do not setup event subscription if polling is disabled."""
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_config_entry,
        options={CONF_REPOSITORIES: ["home-assistant/core"]},
        pref_disable_polling=True,
    )
    await setup_integration(hass, mock_config_entry)
    github_client.repos.events.subscribe.assert_not_called()

    # Prove that we subscribed if the user enabled polling again
    hass.config_entries.async_update_entry(
        mock_config_entry, pref_disable_polling=False
    )
    assert await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    github_client.repos.events.subscribe.assert_called_once()


async def test_sensor_icons(
    hass: HomeAssistant,
    github_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test to ensure that all sensor entities have an icon definition."""
    await setup_integration(hass, mock_config_entry)
    entities = er.async_entries_for_config_entry(
        entity_registry,
        config_entry_id=mock_config_entry.entry_id,
    )

    icons = await icon.async_get_icons(hass, "entity", integrations=["github"])
    for entity in entities:
        assert entity.translation_key is not None
        assert icons["github"]["sensor"][entity.translation_key] is not None
