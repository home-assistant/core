"""Test the OneDrive setup."""

from copy import copy
from http import HTTPStatus
from unittest.mock import MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
from onedrive_personal_sdk.exceptions import (
    AuthenticationError,
    NotFoundError,
    OneDriveException,
)
from onedrive_personal_sdk.models.items import Folder
import pytest
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.test_util.aiohttp import AiohttpClientMocker

from homeassistant.components.backup import DOMAIN as BACKUP_DOMAIN, async_get_manager
from homeassistant.components.onedrive_for_business.const import (
    CONF_FOLDER_ID,
    CONF_FOLDER_PATH,
    CONF_TENANT_ID,
    DOMAIN,
    OAUTH2_TOKEN,
)
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.config_entry_oauth2_flow import (
    ImplementationUnavailableError,
)
from homeassistant.setup import async_setup_component

from . import setup_integration


async def test_load_unload_config_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_onedrive_client_init: MagicMock,
    mock_onedrive_client: MagicMock,
) -> None:
    """Test loading and unloading the integration."""
    await setup_integration(hass, mock_config_entry)

    # Ensure the token callback is set up correctly
    token_callback = mock_onedrive_client_init.call_args[0][0]
    assert await token_callback() == "mock-access-token"

    # make sure metadata migration is not called
    assert mock_onedrive_client.upload_file.call_count == 0
    assert mock_onedrive_client.update_drive_item.call_count == 0

    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.parametrize(
    ("status", "state", "translation_key", "reauth_expected"),
    [
        pytest.param(
            HTTPStatus.BAD_REQUEST,
            ConfigEntryState.SETUP_ERROR,
            "oauth2_helper_reauth_required",
            True,
            id="reauth",
        ),
        pytest.param(
            HTTPStatus.TOO_MANY_REQUESTS,
            ConfigEntryState.SETUP_RETRY,
            "oauth2_helper_refresh_transient",
            False,
            id="transient",
        ),
        pytest.param(
            HTTPStatus.INTERNAL_SERVER_ERROR,
            ConfigEntryState.SETUP_RETRY,
            "oauth2_helper_refresh_transient",
            False,
            id="server_error",
        ),
    ],
)
@pytest.mark.parametrize("expires_at", [0], ids=["expired"])
async def test_token_refresh_errors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
    status: HTTPStatus,
    state: ConfigEntryState,
    translation_key: str,
    reauth_expected: bool,
) -> None:
    """Test a failing token refresh during setup."""
    aioclient_mock.post(
        OAUTH2_TOKEN.format(tenant_id=mock_config_entry.data[CONF_TENANT_ID]),
        status=status,
        json={},
    )
    mock_config_entry.add_to_hass(hass)

    assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is state
    assert mock_config_entry.error_reason_translation_key == translation_key
    assert bool(hass.config_entries.flow.async_progress()) is reauth_expected


@pytest.mark.parametrize(
    ("side_effect", "state"),
    [
        (AuthenticationError(403, "Auth failed"), ConfigEntryState.SETUP_ERROR),
        (OneDriveException(), ConfigEntryState.SETUP_RETRY),
    ],
)
async def test_approot_errors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_onedrive_client: MagicMock,
    side_effect: Exception,
    state: ConfigEntryState,
) -> None:
    """Test errors during approot retrieval."""
    mock_onedrive_client.get_drive_item.side_effect = side_effect
    await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state is state


async def test_get_integration_folder_creation(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_onedrive_client: MagicMock,
    mock_folder: Folder,
) -> None:
    """Test faulty integration folder creation."""
    folder_name = copy(mock_config_entry.data[CONF_FOLDER_PATH])
    mock_onedrive_client.get_drive_item.side_effect = NotFoundError(404, "Not found")
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    mock_onedrive_client.create_folder.assert_called_once_with(
        parent_id="root",
        name=folder_name,
    )
    # ensure the folder id and name are updated
    assert mock_config_entry.data[CONF_FOLDER_ID] == mock_folder.id
    assert mock_config_entry.data[CONF_FOLDER_PATH] == folder_name


async def test_get_integration_folder_creation_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_onedrive_client: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test faulty integration folder creation error."""
    mock_onedrive_client.get_drive_item.side_effect = NotFoundError(404, "Not found")
    mock_onedrive_client.create_folder.side_effect = OneDriveException()
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    assert "Failed to get backups/home_assistant folder" in caplog.text


async def test_oauth_implementation_not_available(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that unavailable OAuth implementation raises ConfigEntryNotReady."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.onedrive_for_business.async_get_config_entry_implementation",
        side_effect=ImplementationUnavailableError,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.parametrize(
    ("stale_agents", "stale_agent_ids"),
    [
        pytest.param({}, [], id="no_stale_settings"),
        # Left behind by a removed config entry that had the uppercase drive ID
        pytest.param(
            {f"{DOMAIN}.MOCK_DRIVE_ID": {"protected": True}},
            [f"{DOMAIN}.MOCK_DRIVE_ID"],
            id="stale_settings",
        ),
    ],
)
async def test_1_1_to_1_2_migration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    stale_agents: dict[str, dict[str, bool]],
    stale_agent_ids: list[str],
) -> None:
    """Test migration from 1.1 to 1.2 uppercases the drive ID."""
    old_config_entry = MockConfigEntry(
        unique_id="mock_drive_id",
        title=mock_config_entry.title,
        domain=DOMAIN,
        data=mock_config_entry.data,
        minor_version=1,
    )
    old_config_entry.add_to_hass(hass)
    device = device_registry.async_get_or_create(
        config_entry_id=old_config_entry.entry_id,
        identifiers={(DOMAIN, "mock_drive_id")},
    )
    lowercase_entity = entity_registry.async_get_or_create(
        SENSOR_DOMAIN,
        DOMAIN,
        "mock_drive_id_total_size",
        config_entry=old_config_entry,
        device_id=device.id,
    )
    # Not all entities need migrating, e.g. if the drive ID was already uppercase
    uppercase_entity = entity_registry.async_get_or_create(
        SENSOR_DOMAIN,
        DOMAIN,
        "MOCK_DRIVE_ID_used_size",
        config_entry=old_config_entry,
        device_id=device.id,
    )

    assert await async_setup_component(hass, BACKUP_DOMAIN, {})
    async_get_manager(hass).config.update(
        agents={f"{DOMAIN}.mock_drive_id": {"protected": False}, **stale_agents},
        create_backup={"agent_ids": [f"{DOMAIN}.mock_drive_id", *stale_agent_ids]},
    )

    await setup_integration(hass, old_config_entry)

    assert old_config_entry.state is ConfigEntryState.LOADED
    assert old_config_entry.unique_id == "MOCK_DRIVE_ID"
    assert old_config_entry.minor_version == 2
    assert (
        entity_registry.async_get(lowercase_entity.entity_id).unique_id
        == "MOCK_DRIVE_ID_total_size"
    )
    assert (
        entity_registry.async_get(uppercase_entity.entity_id).unique_id
        == "MOCK_DRIVE_ID_used_size"
    )
    assert device_registry.async_get(device.id).identifiers == {
        (DOMAIN, "MOCK_DRIVE_ID")
    }
    backup_config = async_get_manager(hass).config.data
    assert backup_config.create_backup.agent_ids == [f"{DOMAIN}.MOCK_DRIVE_ID"]
    assert list(backup_config.agents) == [f"{DOMAIN}.MOCK_DRIVE_ID"]
    assert backup_config.agents[f"{DOMAIN}.MOCK_DRIVE_ID"].protected is False


@pytest.mark.parametrize(
    ("first_drive_id", "second_drive_id"),
    [
        pytest.param("MOCK_DRIVE_ID", "mock_drive_id", id="uppercase_first"),
        pytest.param("mock_drive_id", "MOCK_DRIVE_ID", id="lowercase_first"),
    ],
)
async def test_1_1_to_1_2_migration_removes_duplicates(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
    first_drive_id: str,
    second_drive_id: str,
) -> None:
    """Test migration keeps the oldest entity and device after a casing flip."""
    old_config_entry = MockConfigEntry(
        unique_id="mock_drive_id",
        title=mock_config_entry.title,
        domain=DOMAIN,
        data=mock_config_entry.data,
        minor_version=1,
    )
    old_config_entry.add_to_hass(hass)
    original_device = device_registry.async_get_or_create(
        config_entry_id=old_config_entry.entry_id,
        identifiers={(DOMAIN, first_drive_id)},
    )
    original_entity = entity_registry.async_get_or_create(
        SENSOR_DOMAIN,
        DOMAIN,
        f"{first_drive_id}_total_size",
        config_entry=old_config_entry,
        device_id=original_device.id,
    )
    freezer.tick()
    duplicate_device = device_registry.async_get_or_create(
        config_entry_id=old_config_entry.entry_id,
        identifiers={(DOMAIN, second_drive_id)},
    )
    duplicate_entity = entity_registry.async_get_or_create(
        SENSOR_DOMAIN,
        DOMAIN,
        f"{second_drive_id}_total_size",
        config_entry=old_config_entry,
        device_id=duplicate_device.id,
    )
    # Only exists on the duplicate device, so it has to move to the original one
    moved_entity = entity_registry.async_get_or_create(
        SENSOR_DOMAIN,
        DOMAIN,
        f"{second_drive_id}_used_size",
        config_entry=old_config_entry,
        device_id=duplicate_device.id,
    )
    assert await async_setup_component(hass, BACKUP_DOMAIN, {})

    await setup_integration(hass, old_config_entry)

    assert old_config_entry.state is ConfigEntryState.LOADED
    assert old_config_entry.unique_id == "MOCK_DRIVE_ID"
    original_entity = entity_registry.async_get(original_entity.entity_id)
    assert original_entity.unique_id == "MOCK_DRIVE_ID_total_size"
    assert original_entity.device_id == original_device.id
    assert entity_registry.async_get(duplicate_entity.entity_id) is None
    moved_entity = entity_registry.async_get(moved_entity.entity_id)
    assert moved_entity.unique_id == "MOCK_DRIVE_ID_used_size"
    assert moved_entity.device_id == original_device.id
    assert device_registry.async_get(original_device.id).identifiers == {
        (DOMAIN, "MOCK_DRIVE_ID")
    }
    assert device_registry.async_get(duplicate_device.id) is None


async def test_1_1_to_1_2_migration_duplicate_config_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test migration fails if another config entry already has the drive ID."""
    MockConfigEntry(
        unique_id="MOCK_DRIVE_ID",
        title=mock_config_entry.title,
        domain=DOMAIN,
        data=mock_config_entry.data,
        minor_version=2,
    ).add_to_hass(hass)
    old_config_entry = MockConfigEntry(
        unique_id="mock_drive_id",
        title=mock_config_entry.title,
        domain=DOMAIN,
        data=mock_config_entry.data,
        minor_version=1,
    )
    old_config_entry.add_to_hass(hass)
    old_entity = entity_registry.async_get_or_create(
        SENSOR_DOMAIN,
        DOMAIN,
        "mock_drive_id_total_size",
        config_entry=old_config_entry,
    )

    await setup_integration(hass, old_config_entry)

    assert old_config_entry.state is ConfigEntryState.MIGRATION_ERROR
    assert old_config_entry.unique_id == "mock_drive_id"
    assert (
        entity_registry.async_get(old_entity.entity_id).unique_id
        == "mock_drive_id_total_size"
    )
