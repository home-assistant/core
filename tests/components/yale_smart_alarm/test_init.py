"""Test for Yale Smart Alarm component Init."""

from unittest.mock import Mock, patch

import pytest

from homeassistant.components.lock import DOMAIN as LOCK_DOMAIN
from homeassistant.components.yale_smart_alarm.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER, ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

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
        minor_version=3,
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


@pytest.mark.parametrize(
    ("load_platforms", "child_identifier"),
    [
        pytest.param([Platform.LOCK], "1111", id="lock"),
        pytest.param([Platform.BINARY_SENSOR], "RF4", id="binary_sensor"),
    ],
)
async def test_child_devices_linked_to_panel(
    hass: HomeAssistant,
    load_config_entry: tuple[MockConfigEntry, Mock],
    device_registry: dr.DeviceRegistry,
    child_identifier: str,
) -> None:
    """Test child devices link to the alarm panel through via_device_id.

    Only a single platform is loaded per case, whose entities never create the
    panel device themselves, so the link is established solely by the panel
    being registered at setup. Covers both YaleEntity and YaleLockEntity.
    """
    config_entry, _ = load_config_entry

    panel_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, ENTRY_CONFIG["username"]), config_entry.entry_id
    )
    assert panel_device is not None

    child_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, child_identifier), config_entry.entry_id
    )
    assert child_device is not None
    assert child_device.via_device_id == panel_device.id


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
    assert entry.minor_version == 3
    assert entry.data == ENTRY_CONFIG
    assert entry.options == OPTIONS_CONFIG

    lock_entity_id = entity_registry.async_get_entity_id(LOCK_DOMAIN, DOMAIN, "1111")
    lock = entity_registry.async_get(lock_entity_id)

    assert lock.options == {"lock": {"default_code": "123456"}}


async def test_migrate_panic_button_unique_id(
    hass: HomeAssistant,
    get_client: Mock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test migration of panic button unique_id from v2.2 to v2.3."""
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
    entity_registry.async_get_or_create(
        "button",
        DOMAIN,
        "yale_smart_alarm-panic",
        config_entry=entry,
    )

    with patch(
        "homeassistant.components.yale_smart_alarm.coordinator.YaleSmartAlarmClient",
        return_value=get_client,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert entry.version == 2
    assert entry.minor_version == 3

    migrated = entity_registry.async_get_entity_id("button", DOMAIN, "1-panic")
    assert migrated is not None
    old = entity_registry.async_get_entity_id(
        "button", DOMAIN, "yale_smart_alarm-panic"
    )
    assert old is None
