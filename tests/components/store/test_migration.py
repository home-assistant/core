"""Tests for taking over an existing HACS installation."""

from datetime import UTC, datetime

import pytest

from homeassistant.components.store.const import (
    DOMAIN,
    LEGACY_HACS_REPOSITORY_ID,
    LEGACY_HACS_SYSTEM_ID,
)
from homeassistant.components.store.migration import LEGACY_HACS_DOMAIN
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.components.update import DOMAIN as UPDATE_DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import (
    device_registry as dr,
    entity_registry as er,
    issue_registry as ir,
)
from homeassistant.setup import async_setup_component

from .const import REPOSITORY_INTEGRATION_ID, TOKEN

from tests.common import MockConfigEntry

UPDATE_ENTITY_ID = "update.hacs_basic_integration"
SWITCH_ENTITY_ID = "switch.hacs_basic_integration_pre_release"
SELF_UPDATE_ENTITY_ID = "update.hacs"
SELF_SWITCH_ENTITY_ID = "switch.hacs_pre_release"

ISSUE_IDS = (f"restart_required_{REPOSITORY_INTEGRATION_ID}", "removed")


@pytest.fixture
def ignore_translations_for_mock_domains() -> list[str]:
    """The seeded repair issues belong to the HACS custom integration."""
    return [LEGACY_HACS_DOMAIN]


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a config entry the way HACS left it behind."""
    return MockConfigEntry(
        title="HACS",
        domain=DOMAIN,
        data={CONF_TOKEN: TOKEN},
        options={
            "country": "ALL",
            "appdaemon": True,
            "sidepanel_title": "HACS",
            "sidepanel_icon": "hacs:hacs",
            "experimental": True,
        },
        unique_id="12345",
    )


def _seed_repository_device(
    entry: MockConfigEntry, device_registry: dr.DeviceRegistry
) -> dr.DeviceEntry:
    """Create the device HACS made for a downloaded repository."""
    return device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(LEGACY_HACS_DOMAIN, REPOSITORY_INTEGRATION_ID)},
        name="Basic integration",
        entry_type=dr.DeviceEntryType.SERVICE,
    )


def _seed_system_device(
    entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> dr.DeviceEntry:
    """Create the HACS system device and the entities of HACS itself."""
    device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(LEGACY_HACS_DOMAIN, LEGACY_HACS_SYSTEM_ID)},
        name="HACS",
        entry_type=dr.DeviceEntryType.SERVICE,
    )

    for domain, object_id in (
        (UPDATE_DOMAIN, "hacs"),
        (SWITCH_DOMAIN, "hacs_pre_release"),
    ):
        entity_registry.async_get_or_create(
            domain,
            LEGACY_HACS_DOMAIN,
            LEGACY_HACS_REPOSITORY_ID,
            config_entry=entry,
            device_id=device.id,
            suggested_object_id=object_id,
        )

    return device


def _seed_repository_entities(
    entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    device: dr.DeviceEntry,
) -> None:
    """Create the entities HACS made for a downloaded repository."""
    for domain, object_id in (
        (UPDATE_DOMAIN, "hacs_basic_integration"),
        (SWITCH_DOMAIN, "hacs_basic_integration_pre_release"),
    ):
        entity_registry.async_get_or_create(
            domain,
            LEGACY_HACS_DOMAIN,
            REPOSITORY_INTEGRATION_ID,
            config_entry=entry,
            device_id=device.id,
            suggested_object_id=object_id,
        )


def _seed_issues(hass: HomeAssistant) -> None:
    """Create the repair issues HACS left behind."""
    for issue_id in ISSUE_IDS:
        ir.async_create_issue(
            hass,
            LEGACY_HACS_DOMAIN,
            issue_id,
            is_fixable=issue_id.startswith("restart_required"),
            severity=ir.IssueSeverity.WARNING,
            translation_key=issue_id,
        )


def _registry_state(
    hass: HomeAssistant, entry: MockConfigEntry
) -> tuple[dict[str, tuple], dict[str, frozenset]]:
    """Return the part of the registries the takeover touches."""
    entity_registry = er.async_get(hass)
    device_registry = dr.async_get(hass)

    entities = {
        entity.entity_id: (entity.platform, entity.unique_id, entity.device_id)
        for entity in er.async_entries_for_config_entry(entity_registry, entry.entry_id)
    }
    devices = {
        device.id: frozenset(device.identifiers)
        for device in dr.async_entries_for_config_entry(device_registry, entry.entry_id)
    }
    return entities, devices


@pytest.mark.usefixtures("stored_repositories")
async def test_takeover(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test the store adopts what a HACS install left behind."""
    mock_config_entry.add_to_hass(hass)

    repository_device = _seed_repository_device(mock_config_entry, device_registry)
    system_device = _seed_system_device(
        mock_config_entry, device_registry, entity_registry
    )
    _seed_repository_entities(mock_config_entry, entity_registry, repository_device)
    _seed_issues(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert "Took over the existing installation" in caplog.text

    # The entities keep their entity id and are served by the store now
    update_entity = entity_registry.async_get(UPDATE_ENTITY_ID)
    switch_entity = entity_registry.async_get(SWITCH_ENTITY_ID)
    assert update_entity is not None
    assert switch_entity is not None
    assert update_entity.platform == DOMAIN
    assert switch_entity.platform == DOMAIN
    assert update_entity.unique_id == REPOSITORY_INTEGRATION_ID
    assert update_entity.config_entry_id == mock_config_entry.entry_id

    assert hass.states.get(UPDATE_ENTITY_ID).state == "on"
    assert hass.states.get(SWITCH_ENTITY_ID).state == "off"

    # The device stays where it was, only its identifiers move over
    assert update_entity.device_id == repository_device.id
    assert device_registry.async_get(repository_device.id).identifiers == {
        (DOMAIN, REPOSITORY_INTEGRATION_ID)
    }

    # HACS itself is gone from the catalog
    assert device_registry.async_get(system_device.id) is None
    assert entity_registry.async_get(SELF_UPDATE_ENTITY_ID) is None
    assert entity_registry.async_get(SELF_SWITCH_ENTITY_ID) is None

    # No repair issue is left behind
    assert not [
        domain for domain, _ in issue_registry.issues if domain == LEGACY_HACS_DOMAIN
    ]

    # The options that only ever meant something to HACS are dropped
    assert mock_config_entry.options == {"country": "ALL", "appdaemon": True}


@pytest.mark.usefixtures("stored_repositories")
async def test_takeover_runs_once(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a second setup leaves the adopted registries alone."""
    mock_config_entry.add_to_hass(hass)

    repository_device = _seed_repository_device(mock_config_entry, device_registry)
    _seed_system_device(mock_config_entry, device_registry, entity_registry)
    _seed_repository_entities(mock_config_entry, entity_registry, repository_device)
    _seed_issues(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    before = _registry_state(hass, mock_config_entry)

    caplog.clear()
    await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert _registry_state(hass, mock_config_entry) == before
    assert "Took over the existing installation" not in caplog.text


@pytest.mark.usefixtures("stored_repositories")
async def test_takeover_unique_id_taken(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test a HACS entity is dropped when the store already has that unique id."""
    mock_config_entry.add_to_hass(hass)

    repository_device = _seed_repository_device(mock_config_entry, device_registry)
    _seed_repository_entities(mock_config_entry, entity_registry, repository_device)

    kept = entity_registry.async_get_or_create(
        UPDATE_DOMAIN,
        DOMAIN,
        REPOSITORY_INTEGRATION_ID,
        config_entry=mock_config_entry,
        suggested_object_id="basic_integration_update",
    )

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert entity_registry.async_get(UPDATE_ENTITY_ID) is None
    assert entity_registry.async_get(kept.entity_id) is not None
    assert (
        entity_registry.async_get_entity_id(
            UPDATE_DOMAIN, DOMAIN, REPOSITORY_INTEGRATION_ID
        )
        == kept.entity_id
    )

    # The switch had no counterpart, so it is adopted as usual
    assert entity_registry.async_get(SWITCH_ENTITY_ID).platform == DOMAIN


@pytest.mark.usefixtures("stored_repositories")
async def test_takeover_device_identifier_taken(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test a HACS device is merged into the store device holding its identifier."""
    mock_config_entry.add_to_hass(hass)

    hacs_device = _seed_repository_device(mock_config_entry, device_registry)
    _seed_repository_entities(mock_config_entry, entity_registry, hacs_device)

    kept = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={(DOMAIN, REPOSITORY_INTEGRATION_ID)},
        name="Basic integration",
        entry_type=dr.DeviceEntryType.SERVICE,
    )

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert device_registry.async_get(hacs_device.id) is None
    assert entity_registry.async_get(UPDATE_ENTITY_ID).device_id == kept.id
    assert entity_registry.async_get(SWITCH_ENTITY_ID).device_id == kept.id


@pytest.mark.parametrize(
    ("oldest_data", "newest_data"),
    [
        pytest.param({}, {CONF_TOKEN: TOKEN}, id="token_copied"),
        pytest.param({CONF_TOKEN: TOKEN}, {CONF_TOKEN: "other"}, id="token_kept"),
    ],
)
@pytest.mark.usefixtures("stored_repositories")
async def test_duplicate_entries_removed(
    hass: HomeAssistant,
    oldest_data: dict[str, str],
    newest_data: dict[str, str],
) -> None:
    """Test the oldest entry wins when a HACS entry lands next to a store one."""
    oldest = MockConfigEntry(
        title="HACS",
        domain=DOMAIN,
        created_at=datetime(2024, 1, 1, tzinfo=UTC),
        data=oldest_data,
        options={"country": "ALL"},
    )
    newest = MockConfigEntry(
        title="Community store",
        domain=DOMAIN,
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        data=newest_data,
        options={"country": "ALL"},
    )
    oldest.add_to_hass(hass)
    newest.add_to_hass(hass)

    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    assert hass.config_entries.async_entries(DOMAIN) == [oldest]
    assert oldest.data == {CONF_TOKEN: TOKEN}
    assert oldest.state is ConfigEntryState.LOADED
