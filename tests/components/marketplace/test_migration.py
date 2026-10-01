"""Tests for taking over an existing HACS installation."""

from collections.abc import Callable
from datetime import UTC, datetime
import json
from pathlib import Path
import shutil
from typing import Any
from unittest.mock import patch

import pytest

from homeassistant.components import lovelace
from homeassistant.components.lovelace import LOVELACE_DATA
from homeassistant.components.marketplace.const import (
    CONF_WARNING_ACCEPTED,
    DOMAIN,
    LEGACY_HACS_REPOSITORY_ID,
    LEGACY_HACS_STORAGE_VERSION,
    LEGACY_HACS_SYSTEM_ID,
    STORAGE_VERSION,
    WARNING_VERSION,
)
from homeassistant.components.marketplace.migration import (
    LEGACY_HACS_DOMAIN,
    async_migrate_dashboard_resources,
)
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.components.update import DOMAIN as UPDATE_DOMAIN
from homeassistant.config_entries import SOURCE_SYSTEM, SOURCE_USER, ConfigEntryState
from homeassistant.const import CONF_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import (
    device_registry as dr,
    entity_registry as er,
    issue_registry as ir,
)
from homeassistant.setup import async_setup_component

from . import create_install_folders, setup_integration
from .const import REPOSITORY_INTEGRATION_ID, TOKEN, WARNING_ACCEPTANCE

from tests.common import MockConfigEntry, MockUser, load_json_object_fixture

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
    """Create the device HACS made for an installed repository."""
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
    """Create the entities HACS made for an installed repository."""
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
    """Test the Marketplace adopts what a HACS install left behind."""
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

    # The entities keep their entity id and are served by the Marketplace now
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

    # The options only ever meant something to HACS
    assert mock_config_entry.options == {}


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


@pytest.mark.parametrize(
    ("warning_accepted", "seed_legacy_install"),
    [
        pytest.param(None, True, id="takeover"),
        pytest.param(None, False, id="previous_setup_flow"),
    ],
)
@pytest.mark.usefixtures("stored_repositories")
async def test_existing_install_reads_warning(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    warning_accepted: None,
    seed_legacy_install: bool,
) -> None:
    """Test an install from before the warning still has to read it."""
    mock_config_entry.add_to_hass(hass)
    if seed_legacy_install:
        _seed_repository_device(mock_config_entry, device_registry)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert CONF_WARNING_ACCEPTED not in mock_config_entry.data
    assert mock_config_entry.runtime_data.warning_acceptances == {}


@pytest.mark.parametrize(
    "data",
    [
        pytest.param({}, id="new"),
        pytest.param({CONF_TOKEN: TOKEN}, id="github_connected"),
    ],
)
@pytest.mark.usefixtures("stored_repositories")
async def test_system_entry_does_not_accept_warning(
    hass: HomeAssistant, data: dict[str, str]
) -> None:
    """Test a system entry needs the warning read, connecting GitHub does not count."""
    entry = MockConfigEntry(domain=DOMAIN, source=SOURCE_SYSTEM, data=data)
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.data == data
    assert entry.runtime_data.warning_acceptances == {}


@pytest.mark.usefixtures("stored_repositories")
async def test_takeover_unique_id_taken(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test a HACS entity is dropped when the Marketplace already has that unique id."""
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
    """Test a HACS device is merged into the Marketplace device holding its identifier."""
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
    """Test the oldest entry wins when a HACS entry lands next to a Marketplace one."""
    oldest = MockConfigEntry(
        title="HACS",
        domain=DOMAIN,
        created_at=datetime(2024, 1, 1, tzinfo=UTC),
        data=oldest_data,
    )
    newest = MockConfigEntry(
        title="Marketplace",
        domain=DOMAIN,
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        data=newest_data,
    )
    oldest.add_to_hass(hass)
    newest.add_to_hass(hass)

    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    assert hass.config_entries.async_entries(DOMAIN) == [oldest]
    assert oldest.data[CONF_TOKEN] == TOKEN
    assert oldest.state is ConfigEntryState.LOADED


@pytest.mark.usefixtures("stored_repositories")
async def test_duplicate_entries_keep_the_legacy_entities(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the entry with the entities of HACS wins over an older one.

    An older entry is left over from before a downgrade, the newer one is the
    HACS install the user went back to and customized since.
    """
    oldest = MockConfigEntry(
        title="Marketplace",
        domain=DOMAIN,
        created_at=datetime(2024, 1, 1, tzinfo=UTC),
        data={},
    )
    newest = MockConfigEntry(
        title="HACS",
        domain=DOMAIN,
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        data={CONF_TOKEN: TOKEN},
    )
    oldest.add_to_hass(hass)
    newest.add_to_hass(hass)
    entity_registry.async_get_or_create(
        UPDATE_DOMAIN,
        LEGACY_HACS_DOMAIN,
        REPOSITORY_INTEGRATION_ID,
        config_entry=newest,
        suggested_object_id="my_integration",
    )

    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    assert hass.config_entries.async_entries(DOMAIN) == [newest]
    entity = entity_registry.async_get("update.my_integration")
    assert entity is not None
    assert entity.platform == DOMAIN


@pytest.fixture
def users_who_accepted(hass: HomeAssistant) -> None:
    """Add the users the stored acceptances belong to, others are forgotten."""
    for user_id in ("abc", "def", "ghi"):
        MockUser(id=user_id).add_to_hass(hass)


OLDER_WARNING_ACCEPTANCE = {
    "version": WARNING_VERSION,
    "accepted_at": "2026-03-01T00:00:00+00:00",
}


@pytest.mark.parametrize(
    ("oldest_data", "newest_source", "newest_data", "kept_acceptances"),
    [
        pytest.param({}, SOURCE_USER, {CONF_TOKEN: TOKEN}, None, id="hacs_entry"),
        pytest.param(
            {},
            SOURCE_SYSTEM,
            {CONF_WARNING_ACCEPTED: {"abc": WARNING_ACCEPTANCE}},
            {"abc": WARNING_ACCEPTANCE},
            id="accepted_system_entry",
        ),
        pytest.param(
            {
                CONF_WARNING_ACCEPTED: {
                    "abc": WARNING_ACCEPTANCE,
                    "def": OLDER_WARNING_ACCEPTANCE,
                }
            },
            SOURCE_SYSTEM,
            {
                CONF_WARNING_ACCEPTED: {
                    "abc": OLDER_WARNING_ACCEPTANCE,
                    "def": WARNING_ACCEPTANCE,
                    "ghi": OLDER_WARNING_ACCEPTANCE,
                }
            },
            {
                "abc": WARNING_ACCEPTANCE,
                "def": WARNING_ACCEPTANCE,
                "ghi": OLDER_WARNING_ACCEPTANCE,
            },
            id="newest_acceptance_per_user",
        ),
    ],
)
@pytest.mark.usefixtures("stored_repositories", "users_who_accepted")
async def test_duplicate_entries_keep_warning_acceptance(
    hass: HomeAssistant,
    oldest_data: dict[str, Any],
    newest_source: str,
    newest_data: dict[str, Any],
    kept_acceptances: dict[str, Any] | None,
) -> None:
    """Test the kept entry merges the warning acceptances of every user."""
    oldest = MockConfigEntry(
        domain=DOMAIN,
        source=SOURCE_SYSTEM,
        created_at=datetime(2024, 1, 1, tzinfo=UTC),
        data=oldest_data,
    )
    newest = MockConfigEntry(
        domain=DOMAIN,
        source=newest_source,
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        data=newest_data,
    )
    oldest.add_to_hass(hass)
    newest.add_to_hass(hass)

    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    assert hass.config_entries.async_entries(DOMAIN) == [oldest]
    assert oldest.data.get(CONF_WARNING_ACCEPTED) == kept_acceptances


LEGACY_RESOURCE_URL = "/hacsfiles/plugin-basic/plugin-basic.js?hacstag=1296267100"
MIGRATED_RESOURCE_URL = "/local/community/plugin-basic/plugin-basic.js?v=1296267100"
MODERN_RESOURCE_URL = "/local/community/plugin-other/plugin-other.js?v=42100"


@pytest.fixture
def lovelace_resources(hass_storage: dict[str, Any]) -> list[dict[str, str]]:
    """Seed the dashboard resources with a legacy and an already moved entry."""
    items = [
        {"id": "1", "type": "module", "url": LEGACY_RESOURCE_URL},
        {"id": "2", "type": "module", "url": MODERN_RESOURCE_URL},
        {"id": "3", "type": "module", "url": "/hacsfiles/plugin-plain/plugin-plain.js"},
        {"id": "4", "type": "module", "url": "/local/own.js"},
    ]
    hass_storage["lovelace_resources"] = {
        "version": 1,
        "key": "lovelace_resources",
        "data": {"items": items},
    }
    return items


def _resource_urls(hass: HomeAssistant) -> list[str]:
    """Return the URL of every registered dashboard resource."""
    return [item["url"] for item in hass.data[LOVELACE_DATA].resources.async_items()]


@pytest.mark.usefixtures("lovelace_resources")
async def test_dashboard_resource_migration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test the resources of the custom integration move to the served path."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert _resource_urls(hass) == [
        MIGRATED_RESOURCE_URL,
        MODERN_RESOURCE_URL,
        "/local/community/plugin-plain/plugin-plain.js",
        "/local/own.js",
    ]
    assert "Moved 2 dashboard resource(s) to /local/community" in caplog.text


@pytest.mark.usefixtures("lovelace_resources")
async def test_dashboard_resources_are_loaded_once(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test moving the resources does not read their file a second time."""
    assert await async_setup_component(hass, "lovelace", {})
    resources = hass.data[LOVELACE_DATA].resources
    mock_config_entry.add_to_hass(hass)

    with patch.object(resources, "async_load", wraps=resources.async_load) as load:
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert load.call_count == 1


@pytest.mark.usefixtures("lovelace_resources")
async def test_dashboard_resource_migration_is_idempotent(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that a second run leaves the moved resources alone."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    migrated = _resource_urls(hass)
    caplog.clear()

    await async_migrate_dashboard_resources(hass)

    assert _resource_urls(hass) == migrated
    assert "dashboard resource(s)" not in caplog.text


async def test_dashboard_resource_migration_in_yaml_mode(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    issue_registry: ir.IssueRegistry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that the resources of a YAML dashboard are the user's own file."""
    items = [{"id": "1", "type": "module", "url": LEGACY_RESOURCE_URL}]
    hass.data[LOVELACE_DATA].resources = lovelace.resources.ResourceYAMLCollection(
        items
    )
    caplog.clear()

    await async_migrate_dashboard_resources(hass)

    assert _resource_urls(hass) == [LEGACY_RESOURCE_URL]
    assert "dashboard resource(s)" not in caplog.text

    # The user is told what to change in their own file
    issue = issue_registry.async_get_issue(DOMAIN, "legacy_dashboard_resources")
    assert issue is not None
    assert issue.translation_placeholders == {
        "resources": f"- `{LEGACY_RESOURCE_URL}` becomes `{MIGRATED_RESOURCE_URL}`"
    }

    # Once they did, the issue goes away
    hass.data[LOVELACE_DATA].resources = lovelace.resources.ResourceYAMLCollection(
        [{"id": "1", "type": "module", "url": MIGRATED_RESOURCE_URL}]
    )
    await async_migrate_dashboard_resources(hass)

    assert not issue_registry.async_get_issue(DOMAIN, "legacy_dashboard_resources")


LEGACY_STORAGE_FILES = ("hacs.hacs", "hacs.repositories", "hacs.critical", "hacs.data")
REMOVED_LOG = "Removed what the previous installation left behind"


def _seed_storage(config_dir: Path, *keys: str) -> None:
    """Write empty storage files, each with the version its writer used."""
    storage = config_dir / ".storage"
    storage.mkdir(exist_ok=True)
    for key in keys:
        version = LEGACY_HACS_STORAGE_VERSION if key in LEGACY_STORAGE_FILES else 1
        (storage / key).write_text(
            json.dumps({"version": version, "data": {}}), encoding="utf-8"
        )


def _seed_integration(config_dir: Path, manifest: str) -> Path:
    """Write a custom integration to custom_components/hacs."""
    directory = config_dir / "custom_components" / "hacs"
    directory.mkdir(parents=True)
    (directory / "manifest.json").write_text(manifest, encoding="utf-8")
    return directory


def _remaining_storage(config_dir: Path) -> set[str]:
    """Return the legacy storage files still on disk."""
    return {
        key for key in LEGACY_STORAGE_FILES if (config_dir / ".storage" / key).exists()
    }


@pytest.fixture
def adopted_storage(config_dir: Path) -> None:
    """Leave the storage of a HACS install next to the adopted Marketplace storage."""
    _seed_storage(
        config_dir,
        *LEGACY_STORAGE_FILES,
        "marketplace.common",
        "marketplace.repositories",
        "marketplace.critical",
    )


@pytest.fixture
def legacy_integration(config_dir: Path) -> Path:
    """Leave the HACS custom integration in custom_components."""
    return _seed_integration(config_dir, json.dumps({"domain": LEGACY_HACS_DOMAIN}))


@pytest.mark.usefixtures("adopted_storage", "stored_repositories")
async def test_legacy_files_removed(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    config_dir: Path,
    legacy_integration: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test the files of the HACS install are removed once adopted."""
    repository_files = config_dir / ".storage" / "hacs"
    await hass.async_add_executor_job(repository_files.mkdir)
    await hass.async_add_executor_job(
        (repository_files / "1296269.hacs").write_text, "{}", "utf-8"
    )

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert not legacy_integration.exists()
    assert not repository_files.exists()
    assert _remaining_storage(config_dir) == set()
    assert REMOVED_LOG in caplog.text
    assert str(legacy_integration) in caplog.text


@pytest.mark.parametrize("mode", ["safe_mode", "recovery_mode"])
@pytest.mark.usefixtures("adopted_storage", "stored_repositories")
async def test_legacy_files_kept_in_safe_mode(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    config_dir: Path,
    legacy_integration: Path,
    mode: str,
) -> None:
    """Test safe and recovery mode keep HACS, they are the way back to it."""
    setattr(hass.config, mode, True)

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert legacy_integration.is_dir()
    assert _remaining_storage(config_dir) == set(LEGACY_STORAGE_FILES)


@pytest.mark.parametrize("mode", ["safe_mode", "recovery_mode"])
async def test_no_entry_of_its_own_in_safe_mode(hass: HomeAssistant, mode: str) -> None:
    """Test safe and recovery mode leave the entry of HACS to take over later."""
    setattr(hass.config, mode, True)
    MockConfigEntry(domain=LEGACY_HACS_DOMAIN, source=SOURCE_USER).add_to_hass(hass)

    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    assert hass.config_entries.async_entries(DOMAIN) == []


@pytest.mark.parametrize(
    "manifest",
    [
        pytest.param('{"domain": "not_hacs"}', id="foreign_domain"),
        pytest.param("not json", id="invalid_manifest"),
    ],
)
@pytest.mark.usefixtures("adopted_storage", "stored_repositories")
async def test_foreign_integration_kept(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    config_dir: Path,
    manifest: str,
) -> None:
    """Test a custom_components/hacs that is not HACS stays where it is."""
    integration = await hass.async_add_executor_job(
        _seed_integration, config_dir, manifest
    )

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert integration.is_dir()
    assert _remaining_storage(config_dir) == set()


def _seed_git_checkout(config_dir: Path) -> Path:
    """Put a development checkout of HACS in custom_components/hacs."""
    checkout = _seed_integration(config_dir, json.dumps({"domain": LEGACY_HACS_DOMAIN}))
    (checkout / ".git").mkdir()
    (checkout / "uncommitted.py").write_text("work in progress", encoding="utf-8")
    return checkout


def _seed_linked_checkout(config_dir: Path) -> Path:
    """Link custom_components/hacs to a checkout of HACS elsewhere."""
    checkout = config_dir / "development" / "hacs"
    checkout.mkdir(parents=True)
    (checkout / "manifest.json").write_text(
        json.dumps({"domain": LEGACY_HACS_DOMAIN}), encoding="utf-8"
    )
    link = config_dir / "custom_components" / "hacs"
    link.parent.mkdir(parents=True, exist_ok=True)
    link.symlink_to(checkout, target_is_directory=True)
    return link


def _seed_linked_custom_components(config_dir: Path) -> Path:
    """Link custom_components to the one of a HACS checkout, its .git at the root."""
    checkout = config_dir / "development" / "hacs"
    (checkout / ".git").mkdir(parents=True)
    linked = checkout / "custom_components"
    custom_components = config_dir / "custom_components"
    if custom_components.is_dir():
        shutil.move(custom_components, linked)
    integration = linked / "hacs"
    integration.mkdir(parents=True)
    (integration / "manifest.json").write_text(
        json.dumps({"domain": LEGACY_HACS_DOMAIN}), encoding="utf-8"
    )
    custom_components.symlink_to(linked, target_is_directory=True)
    return custom_components / "hacs"


@pytest.mark.parametrize(
    "seed",
    [
        pytest.param(_seed_git_checkout, id="git_checkout"),
        pytest.param(_seed_linked_checkout, id="symlink"),
        pytest.param(_seed_linked_custom_components, id="linked_custom_components"),
    ],
)
@pytest.mark.usefixtures("adopted_storage", "stored_repositories")
async def test_development_checkout_kept(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    config_dir: Path,
    caplog: pytest.LogCaptureFixture,
    seed: Callable[[Path], Path],
) -> None:
    """Test a checkout of HACS someone works on is left for them to remove."""
    integration = await hass.async_add_executor_job(seed, config_dir)

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert (integration / "manifest.json").is_file()
    assert "Could not remove" not in caplog.text
    assert "remove it yourself" in caplog.text


@pytest.mark.usefixtures("adopted_storage", "stored_repositories")
async def test_no_legacy_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    config_dir: Path,
) -> None:
    """Test a missing custom_components/hacs is no reason to fail."""
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert not (config_dir / "custom_components" / "hacs").exists()
    assert _remaining_storage(config_dir) == set()


@pytest.mark.parametrize(
    ("storage_keys", "remaining"),
    [
        pytest.param(
            ("marketplace.repositories",),
            {"hacs.hacs", "hacs.critical"},
            id="only_repositories",
        ),
        pytest.param(
            ("marketplace.repositories", "marketplace.common"),
            {"hacs.critical"},
            id="critical_not_adopted",
        ),
        pytest.param(
            ("marketplace.common", "marketplace.critical"),
            set(LEGACY_STORAGE_FILES),
            id="repositories_not_adopted",
        ),
    ],
)
@pytest.mark.usefixtures("stored_repositories")
async def test_legacy_storage_needs_counterpart(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    config_dir: Path,
    legacy_integration: Path,
    storage_keys: tuple[str, ...],
    remaining: set[str],
) -> None:
    """Test a legacy storage file is only removed once the Marketplace has its own."""
    await hass.async_add_executor_job(
        _seed_storage, config_dir, *LEGACY_STORAGE_FILES, *storage_keys
    )

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert _remaining_storage(config_dir) == remaining


@pytest.mark.usefixtures("adopted_storage", "stored_repositories")
async def test_legacy_storage_of_another_version_kept(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, config_dir: Path
) -> None:
    """Test a legacy file the Marketplace could not take the data from stays."""
    legacy = config_dir / ".storage" / "hacs.repositories"
    await hass.async_add_executor_job(
        legacy.write_text, '{"version": "5", "data": {}}', "utf-8"
    )

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert _remaining_storage(config_dir) == {"hacs.repositories"}


@pytest.mark.usefixtures("stored_repositories")
async def test_legacy_integration_kept_without_marketplace_storage(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    legacy_integration: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test nothing is removed before the Marketplace has a repositories file."""
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert legacy_integration.is_dir()
    assert REMOVED_LOG not in caplog.text


@pytest.mark.usefixtures("adopted_storage", "stored_repositories")
async def test_legacy_integration_removal_fails(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    config_dir: Path,
    legacy_integration: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a failing removal is logged and the Marketplace still sets up."""
    with patch(
        "homeassistant.components.marketplace.migration.shutil.rmtree",
        side_effect=OSError("Permission denied"),
    ):
        await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert legacy_integration.is_dir()
    assert f"Could not remove {legacy_integration}: Permission denied" in caplog.text
    assert _remaining_storage(config_dir) == set()


@pytest.mark.usefixtures("adopted_storage", "stored_repositories")
async def test_legacy_storage_removal_fails(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    config_dir: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a storage file that can not be removed is logged and left alone."""
    with patch(
        "homeassistant.components.marketplace.migration.Path.unlink",
        side_effect=OSError("Read-only file system"),
    ):
        await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert _remaining_storage(config_dir) == set(LEGACY_STORAGE_FILES)
    assert "Read-only file system" in caplog.text
    assert REMOVED_LOG not in caplog.text


@pytest.mark.usefixtures("adopted_storage", "stored_repositories", "legacy_integration")
async def test_legacy_files_removal_runs_once(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a second setup finds nothing left to remove."""
    await setup_integration(hass, mock_config_entry)
    assert REMOVED_LOG in caplog.text

    caplog.clear()
    await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert REMOVED_LOG not in caplog.text


APPDAEMON_INSTALLED_ID = "990001"
APPDAEMON_UNNAMED_ID = "990002"
APPDAEMON_NOT_INSTALLED_ID = "990003"

APPDAEMON_REPOSITORIES: dict[str, dict[str, Any]] = {
    APPDAEMON_INSTALLED_ID: {
        "category": "appdaemon",
        "full_name": "hacs-test-org/appdaemon-basic",
        "installed": True,
        "repository_manifest": {"name": "Basic app"},
        "version_installed": "1.0.0",
    },
    APPDAEMON_UNNAMED_ID: {
        "category": "appdaemon",
        "full_name": "hacs-test-org/motion_lights-app",
        "installed": True,
    },
    APPDAEMON_NOT_INSTALLED_ID: {
        "category": "appdaemon",
        "full_name": "hacs-test-org/appdaemon-other",
    },
}


def _seed_stored_repositories(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    appdaemon_repositories: dict[str, dict[str, Any]],
) -> None:
    """Store the regular repositories next to the given AppDaemon ones."""
    repositories = load_json_object_fixture("stored_repositories.json", DOMAIN)
    hass_storage[f"{DOMAIN}.repositories"] = {
        "version": STORAGE_VERSION,
        "data": {**repositories, **appdaemon_repositories},
    }
    create_install_folders(Path(hass.config.config_dir), repositories)


def _seed_appdaemon_registry_entries(
    entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    repository_id: str,
) -> dr.DeviceEntry:
    """Create the device and entities of an installed AppDaemon app."""
    device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, repository_id)},
        name="Basic app",
        entry_type=dr.DeviceEntryType.SERVICE,
    )

    for domain in (UPDATE_DOMAIN, SWITCH_DOMAIN):
        entity_registry.async_get_or_create(
            domain,
            DOMAIN,
            repository_id,
            config_entry=entry,
            device_id=device.id,
        )

    return device


async def test_appdaemon_repositories_forgotten(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    config_dir: Path,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test the stored AppDaemon apps are forgotten, but stay on disk."""
    _seed_stored_repositories(hass, hass_storage, APPDAEMON_REPOSITORIES)
    app_file = config_dir / "appdaemon" / "apps" / "basic" / "basic.py"
    app_file.parent.mkdir(parents=True)
    app_file.write_text("import appdaemon", encoding="utf-8")

    entry = MockConfigEntry(domain=DOMAIN, data={CONF_TOKEN: TOKEN})
    entry.add_to_hass(hass)
    device = _seed_appdaemon_registry_entries(
        entry, device_registry, entity_registry, APPDAEMON_INSTALLED_ID
    )

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    marketplace = entry.runtime_data
    for repository_id in APPDAEMON_REPOSITORIES:
        assert marketplace.repositories.get_by_id(repository_id) is None
    assert marketplace.repositories.get_by_id(REPOSITORY_INTEGRATION_ID) is not None

    assert device_registry.async_get(device.id) is None
    for domain in (UPDATE_DOMAIN, SWITCH_DOMAIN):
        assert (
            entity_registry.async_get_entity_id(domain, DOMAIN, APPDAEMON_INSTALLED_ID)
            is None
        )

    # Only the installed apps are listed, the files are left alone
    issue = issue_registry.async_get_issue(DOMAIN, "appdaemon_not_supported")
    assert issue is not None
    assert issue.is_fixable is False
    assert issue.is_persistent is False
    assert issue.severity is ir.IssueSeverity.WARNING
    assert issue.translation_placeholders == {"apps": "Basic app, Motion Lights App"}
    assert app_file.read_text(encoding="utf-8") == "import appdaemon"

    # Unloading writes the stored data, without the AppDaemon apps
    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    stored = hass_storage[f"{DOMAIN}.repositories"]["data"]
    assert REPOSITORY_INTEGRATION_ID in stored
    assert not set(APPDAEMON_REPOSITORIES) & set(stored)

    # With nothing left to report, the next start has nothing to say
    ir.async_delete_issue(hass, DOMAIN, "appdaemon_not_supported")
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert issue_registry.async_get_issue(DOMAIN, "appdaemon_not_supported") is None
    assert app_file.exists()


async def test_appdaemon_repositories_not_installed(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test AppDaemon apps that were never installed are dropped quietly."""
    _seed_stored_repositories(
        hass,
        hass_storage,
        {
            APPDAEMON_NOT_INSTALLED_ID: APPDAEMON_REPOSITORIES[
                APPDAEMON_NOT_INSTALLED_ID
            ]
        },
    )
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_TOKEN: TOKEN})
    await setup_integration(hass, entry)

    assert entry.state is ConfigEntryState.LOADED
    assert entry.runtime_data.repositories.get_by_id(APPDAEMON_NOT_INSTALLED_ID) is None
    assert issue_registry.async_get_issue(DOMAIN, "appdaemon_not_supported") is None


PYTHON_SCRIPT_INSTALLED_ID = "990011"
PYTHON_SCRIPT_NOT_INSTALLED_ID = "990012"

PYTHON_SCRIPT_REPOSITORIES: dict[str, dict[str, Any]] = {
    PYTHON_SCRIPT_INSTALLED_ID: {
        "category": "python_script",
        "full_name": "hacs-test-org/python_script-basic",
        "installed": True,
        "repository_manifest": {"name": "Basic script"},
        "version_installed": "1.0.0",
    },
    PYTHON_SCRIPT_NOT_INSTALLED_ID: {
        "category": "python_script",
        "full_name": "hacs-test-org/python_script-other",
    },
}


async def test_python_scripts_forgotten_next_to_appdaemon(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    config_dir: Path,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test python scripts are forgotten like AppDaemon apps, each with its issue."""
    _seed_stored_repositories(
        hass, hass_storage, {**APPDAEMON_REPOSITORIES, **PYTHON_SCRIPT_REPOSITORIES}
    )
    script_file = config_dir / "python_scripts" / "basic.py"
    script_file.parent.mkdir(parents=True)
    script_file.write_text("logger.info('hello')", encoding="utf-8")

    entry = MockConfigEntry(domain=DOMAIN, data={CONF_TOKEN: TOKEN})
    entry.add_to_hass(hass)
    device = _seed_appdaemon_registry_entries(
        entry, device_registry, entity_registry, PYTHON_SCRIPT_INSTALLED_ID
    )

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    marketplace = entry.runtime_data
    for repository_id in PYTHON_SCRIPT_REPOSITORIES:
        assert marketplace.repositories.get_by_id(repository_id) is None
    assert device_registry.async_get(device.id) is None

    issue = issue_registry.async_get_issue(DOMAIN, "python_scripts_not_supported")
    assert issue is not None
    assert issue.translation_placeholders == {"scripts": "Basic script"}
    assert issue_registry.async_get_issue(DOMAIN, "appdaemon_not_supported")

    # The python_script integration keeps running what was installed
    assert script_file.read_text(encoding="utf-8") == "logger.info('hello')"


@pytest.mark.usefixtures("stored_repositories")
async def test_options_cleared(hass: HomeAssistant) -> None:
    """Test every option is cleared, including ones the Marketplace never knew."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_TOKEN: TOKEN},
        options={"country": "NL", "appdaemon": True, "unknown": "dropped"},
    )
    await setup_integration(hass, entry)

    assert entry.state is ConfigEntryState.LOADED
    assert entry.options == {}

    configuration = entry.runtime_data.configuration
    for option in ("country", "appdaemon", "unknown"):
        assert not hasattr(configuration, option)
