"""Test for Yale Smart Alarm component Init."""

from __future__ import annotations

from unittest.mock import Mock, patch

from homeassistant.components.lock import DOMAIN as LOCK_DOMAIN
from homeassistant.components.yale_smart_alarm.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER, ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import ENTRY_CONFIG, OPTIONS_CONFIG

from tests.common import MockConfigEntry


async def test_setup_entry(
    hass: HomeAssistant,
    get_client: Mock,
) -> None:
    """Test setup entry."""
    entry = MockConfigEntry(
        title=ENTRY_CONFIG["username"],
        domain=DOMAIN,
        source=SOURCE_USER,
        data=ENTRY_CONFIG,
        options=OPTIONS_CONFIG,
        entry_id="1",
        unique_id="username",
        version=2,
        minor_version=2,
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.yale_smart_alarm.coordinator.YaleSmartAlarmClient",
        return_value=get_client,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(entry.entry_id)
    assert entry.state is ConfigEntryState.NOT_LOADED


async def test_migrate_entry(
    hass: HomeAssistant,
    get_client: Mock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test migrate entry unique id."""
    config = {
        "username": "test-username",
        "password": "new-test-password",
        "name": "Yale Smart Alarm",
        "area_id": "1",
    }
    options = {"lock_code_digits": 6, "code": "123456"}
    entry = MockConfigEntry(
        title=ENTRY_CONFIG["username"],
        domain=DOMAIN,
        source=SOURCE_USER,
        data=config,
        options=options,
        entry_id="1",
        unique_id="username",
        version=1,
        minor_version=1,
    )
    entry.add_to_hass(hass)
    lock = entity_registry.async_get_or_create(
        LOCK_DOMAIN,
        DOMAIN,
        "1111",
        config_entry=entry,
        has_entity_name=True,
        original_name="Device1",
    )

    with patch(
        "homeassistant.components.yale_smart_alarm.coordinator.YaleSmartAlarmClient",
        return_value=get_client,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert entry.version == 2
    assert entry.minor_version == 2
    assert entry.data == ENTRY_CONFIG
    assert entry.options == OPTIONS_CONFIG

    lock_entity_id = entity_registry.async_get_entity_id(LOCK_DOMAIN, DOMAIN, "1111")
    lock = entity_registry.async_get(lock_entity_id)

    assert lock.options == {"lock": {"default_code": "123456"}}
