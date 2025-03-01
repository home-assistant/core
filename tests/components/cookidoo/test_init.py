"""Unit tests for the cookidoo integration."""

from unittest.mock import AsyncMock

from cookidoo_api import CookidooAuthException, CookidooRequestException
import pytest

from homeassistant.components.cookidoo.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    CONF_COUNTRY,
    CONF_EMAIL,
    CONF_LANGUAGE,
    CONF_PASSWORD,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import setup_integration
from .conftest import COUNTRY, EMAIL, LANGUAGE, PASSWORD, TEST_UUID

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("mock_cookidoo_client")
async def test_load_unload(
    hass: HomeAssistant,
    cookidoo_config_entry: MockConfigEntry,
) -> None:
    """Test loading and unloading of the config entry."""
    await setup_integration(hass, cookidoo_config_entry)

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1

    assert cookidoo_config_entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(cookidoo_config_entry.entry_id)
    assert cookidoo_config_entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.parametrize(
    ("exception", "status"),
    [
        (CookidooRequestException, ConfigEntryState.SETUP_RETRY),
        (CookidooAuthException, ConfigEntryState.SETUP_ERROR),
    ],
)
async def test_init_failure(
    hass: HomeAssistant,
    mock_cookidoo_client: AsyncMock,
    status: ConfigEntryState,
    exception: Exception,
    cookidoo_config_entry: MockConfigEntry,
) -> None:
    """Test an initialization error on integration load."""
    mock_cookidoo_client.login.side_effect = exception
    await setup_integration(hass, cookidoo_config_entry)
    assert cookidoo_config_entry.state == status


@pytest.mark.parametrize(
    "cookidoo_method",
    [
        "get_ingredient_items",
        "get_additional_items",
    ],
)
async def test_config_entry_not_ready(
    hass: HomeAssistant,
    cookidoo_config_entry: MockConfigEntry,
    mock_cookidoo_client: AsyncMock,
    cookidoo_method: str,
) -> None:
    """Test config entry not ready."""
    getattr(
        mock_cookidoo_client, cookidoo_method
    ).side_effect = CookidooRequestException()
    cookidoo_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(cookidoo_config_entry.entry_id)
    await hass.async_block_till_done()

    assert cookidoo_config_entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.parametrize(
    ("exception", "status"),
    [
        (None, ConfigEntryState.LOADED),
        (CookidooRequestException, ConfigEntryState.SETUP_RETRY),
        (CookidooAuthException, ConfigEntryState.SETUP_ERROR),
    ],
)
async def test_config_entry_not_ready_auth_error(
    hass: HomeAssistant,
    cookidoo_config_entry: MockConfigEntry,
    mock_cookidoo_client: AsyncMock,
    exception: Exception | None,
    status: ConfigEntryState,
) -> None:
    """Test config entry not ready from authentication error."""

    mock_cookidoo_client.get_ingredient_items.side_effect = CookidooAuthException
    mock_cookidoo_client.refresh_token.side_effect = exception

    cookidoo_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(cookidoo_config_entry.entry_id)
    await hass.async_block_till_done()

    assert cookidoo_config_entry.state is status


MOCK_CONFIG_ENTRY_MIGRATION = {
    CONF_EMAIL: EMAIL,
    CONF_PASSWORD: PASSWORD,
    CONF_COUNTRY: COUNTRY,
    CONF_LANGUAGE: LANGUAGE,
}

OLD_ENTRY_ID = "OLD_OLD_ENTRY_ID"


@pytest.mark.parametrize(
    (
        "from_version",
        "from_minor_version",
        "config_data",
        "unique_id",
    ),
    [
        (
            1,
            1,
            MOCK_CONFIG_ENTRY_MIGRATION,
            None,
        ),
        (1, 2, MOCK_CONFIG_ENTRY_MIGRATION, TEST_UUID),
    ],
)
async def test_migration_from(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    from_version,
    from_minor_version,
    config_data,
    unique_id,
    mock_cookidoo_client: AsyncMock,
) -> None:
    """Test different expected migration paths."""

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data=config_data,
        title=f"MIGRATION_TEST from {from_version}.{from_minor_version}",
        version=from_version,
        minor_version=from_minor_version,
        unique_id=unique_id,
        entry_id=OLD_ENTRY_ID,
    )
    config_entry.add_to_hass(hass)

    device = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, OLD_ENTRY_ID)},
        entry_type=dr.DeviceEntryType.SERVICE,
    )
    entity_registry.async_get_or_create(
        config_entry=config_entry,
        platform=DOMAIN,
        domain="todo",
        unique_id=f"{OLD_ENTRY_ID}_ingredients",
        device_id=device.id,
    )
    entity_registry.async_get_or_create(
        config_entry=config_entry,
        platform=DOMAIN,
        domain="todo",
        unique_id=f"{OLD_ENTRY_ID}_additional_items",
        device_id=device.id,
    )
    entity_registry.async_get_or_create(
        config_entry=config_entry,
        platform=DOMAIN,
        domain="button",
        unique_id=f"{OLD_ENTRY_ID}_todo_clear",
        device_id=device.id,
    )

    await hass.config_entries.async_setup(config_entry.entry_id)

    assert config_entry.state is ConfigEntryState.LOADED

    # Check change in config entry and verify most recent version
    assert config_entry.version == 1
    assert config_entry.minor_version == 2
    assert config_entry.unique_id == TEST_UUID

    assert entity_registry.async_is_registered(
        entity_registry.entities.get_entity_id(
            (
                Platform.TODO,
                DOMAIN,
                f"{TEST_UUID}_ingredients",
            )
        )
    )
    assert entity_registry.async_is_registered(
        entity_registry.entities.get_entity_id(
            (
                Platform.TODO,
                DOMAIN,
                f"{TEST_UUID}_additional_items",
            )
        )
    )
    assert entity_registry.async_is_registered(
        entity_registry.entities.get_entity_id(
            (
                Platform.BUTTON,
                DOMAIN,
                f"{TEST_UUID}_todo_clear",
            )
        )
    )


@pytest.mark.parametrize(
    (
        "from_version",
        "from_minor_version",
        "config_data",
        "unique_id",
        "login_exception",
    ),
    [
        (
            1,
            1,
            MOCK_CONFIG_ENTRY_MIGRATION,
            None,
            CookidooRequestException,
        ),
        (
            1,
            1,
            MOCK_CONFIG_ENTRY_MIGRATION,
            None,
            CookidooAuthException,
        ),
    ],
)
async def test_migration_from_with_error(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    from_version,
    from_minor_version,
    config_data,
    unique_id,
    login_exception: Exception,
    mock_cookidoo_client: AsyncMock,
) -> None:
    """Test different expected migration paths but with connection issues."""
    # Migration can fail due to connection issues as we have to fetch the uuid
    mock_cookidoo_client.login.side_effect = login_exception

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data=config_data,
        title=f"MIGRATION_TEST from {from_version}.{from_minor_version} with login exception '{login_exception}'",
        version=from_version,
        minor_version=from_minor_version,
        unique_id=unique_id,
        entry_id=OLD_ENTRY_ID,
    )
    config_entry.add_to_hass(hass)

    device = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, OLD_ENTRY_ID)},
        entry_type=dr.DeviceEntryType.SERVICE,
    )
    entity_registry.async_get_or_create(
        config_entry=config_entry,
        platform=DOMAIN,
        domain="todo",
        unique_id=f"{OLD_ENTRY_ID}_ingredients",
        device_id=device.id,
    )
    entity_registry.async_get_or_create(
        config_entry=config_entry,
        platform=DOMAIN,
        domain="todo",
        unique_id=f"{OLD_ENTRY_ID}_additional_items",
        device_id=device.id,
    )
    entity_registry.async_get_or_create(
        config_entry=config_entry,
        platform=DOMAIN,
        domain="button",
        unique_id=f"{OLD_ENTRY_ID}_todo_clear",
        device_id=device.id,
    )

    await hass.config_entries.async_setup(config_entry.entry_id)

    assert config_entry.state is ConfigEntryState.MIGRATION_ERROR

    assert entity_registry.async_is_registered(
        entity_registry.entities.get_entity_id(
            (
                Platform.TODO,
                DOMAIN,
                f"{OLD_ENTRY_ID}_ingredients",
            )
        )
    )
    assert entity_registry.async_is_registered(
        entity_registry.entities.get_entity_id(
            (
                Platform.TODO,
                DOMAIN,
                f"{OLD_ENTRY_ID}_additional_items",
            )
        )
    )
    assert entity_registry.async_is_registered(
        entity_registry.entities.get_entity_id(
            (
                Platform.BUTTON,
                DOMAIN,
                f"{OLD_ENTRY_ID}_todo_clear",
            )
        )
    )
