"""Test the GitHub init file."""

from unittest.mock import AsyncMock

from homeassistant.components.github import CONF_REPOSITORY
from homeassistant.components.github.const import CONF_REPOSITORIES, DOMAIN
from homeassistant.const import CONF_ACCESS_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er, icon

from . import setup_integration
from .const import MOCK_ACCESS_TOKEN

from tests.common import MockConfigEntry


async def test_device_registry_cleanup(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
    github_client: AsyncMock,
) -> None:
    """Test that we remove untracked repositories from the device registry."""
    await setup_integration(hass, mock_config_entry)

    devices = dr.async_entries_for_config_entry(
        registry=device_registry,
        config_entry_id=mock_config_entry.entry_id,
    )

    assert len(devices) == 1

    hass.config_entries.async_remove_subentry(
        mock_config_entry, list(mock_config_entry.subentries)[0]
    )
    await hass.async_block_till_done()

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
    await setup_integration(hass, mock_config_entry)
    github_client.repos.events.subscribe.assert_called_once()


async def test_subscription_setup_polling_disabled(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    github_client: AsyncMock,
) -> None:
    """Test that we do not setup event subscription if polling is disabled."""
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(mock_config_entry, pref_disable_polling=True)
    await setup_integration(hass, mock_config_entry)
    github_client.repos.events.subscribe.assert_not_called()

    # Prove that we subscribed if the user enabled polling again
    hass.config_entries.async_update_entry(
        mock_config_entry, pref_disable_polling=False
    )
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


async def test_minor_v1_v2_migration(
    hass: HomeAssistant, github_client: AsyncMock
) -> None:
    """Test that we migrate minor version 1 to 2 correctly."""
    mock_config_entry = MockConfigEntry(
        domain=DOMAIN,
        title=DOMAIN,
        data={CONF_ACCESS_TOKEN: MOCK_ACCESS_TOKEN},
        options={CONF_REPOSITORIES: ["test/repository"]},
        minor_version=1,
    )
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.options[CONF_REPOSITORIES] == ["test/repository"]
    assert mock_config_entry.minor_version == 2
    assert len(mock_config_entry.subentries) == 1
    subentry = list(mock_config_entry.subentries.values())[0]
    assert subentry.data[CONF_REPOSITORY] == "test/repository"
    assert subentry.title == "test/repository"
    assert subentry.unique_id == "test/repository"
