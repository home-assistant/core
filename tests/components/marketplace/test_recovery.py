"""Test reconnecting Marketplace repositories to existing integration files."""

import json
from pathlib import Path
import sys
from types import ModuleType
from typing import Any

import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.marketplace.const import (
    DOMAIN,
    LEGACY_HACS_STORAGE_VERSION,
    STORAGE_VERSION,
)
from homeassistant.components.marketplace.migration import LEGACY_HACS_DOMAIN
from homeassistant.components.update import ATTR_INSTALLED_VERSION, ATTR_LATEST_VERSION
from homeassistant.const import STATE_ON, STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration
from .const import REPOSITORY_INTEGRATION, REPOSITORY_INTEGRATION_ID

VERSION = "0.9.0"


@pytest.fixture
def disconnected_manifest(
    config_dir: Path,
    hass_storage: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
    request: pytest.FixtureRequest,
) -> Path:
    """Leave the integration files in place with an incomplete repository record."""
    records = {
        REPOSITORY_INTEGRATION_ID: {
            "category": "integration",
            "domain": "example",
            "full_name": REPOSITORY_INTEGRATION,
        },
    }
    if getattr(request, "param", DOMAIN) == LEGACY_HACS_DOMAIN:
        storage = config_dir / ".storage"
        storage.mkdir(exist_ok=True)
        (storage / "hacs.repositories").write_text(
            json.dumps({"version": LEGACY_HACS_STORAGE_VERSION, "data": records})
        )
    else:
        hass_storage[f"{DOMAIN}.repositories"] = {
            "version": STORAGE_VERSION,
            "data": records,
        }
    folder = config_dir / "custom_components" / "example"
    folder.mkdir(parents=True)
    root = ModuleType("custom_components")
    root.__path__ = [str(folder.parent)]
    monkeypatch.setitem(sys.modules, "custom_components", root)
    (folder / "__init__.py").touch()
    manifest = folder / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "domain": "example",
                "name": "Basic integration",
                "version": VERSION,
                "issue_tracker": f"https://github.com/{REPOSITORY_INTEGRATION}/issues",
            }
        )
    )
    return manifest


@pytest.fixture
def old_update_entity(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    request: pytest.FixtureRequest,
) -> er.RegistryEntry:
    """Leave an update entity with its original registry ID and name."""
    mock_config_entry.add_to_hass(hass)
    entry = entity_registry.async_get_or_create(
        Platform.UPDATE,
        getattr(request, "param", DOMAIN),
        REPOSITORY_INTEGRATION_ID,
        config_entry=mock_config_entry,
        suggested_object_id="original_custom_integration",
    )
    entry.write_unavailable_state(hass)
    return entry


@pytest.mark.usefixtures("enable_custom_integrations", "disconnected_manifest")
@pytest.mark.parametrize(
    ("disconnected_manifest", "old_update_entity"),
    [
        pytest.param(LEGACY_HACS_DOMAIN, LEGACY_HACS_DOMAIN, id="hacs-takeover"),
        pytest.param(DOMAIN, DOMAIN, id="already-migrated"),
    ],
    indirect=True,
)
async def test_recovers_install_on_startup(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    old_update_entity: er.RegistryEntry,
    hass_storage: dict[str, Any],
) -> None:
    """Restore updates for the installed version through the original entity."""
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(old_update_entity.entity_id)
    assert state is not None
    assert state.state == STATE_ON
    assert state.attributes[ATTR_INSTALLED_VERSION] == VERSION
    assert state.attributes[ATTR_LATEST_VERSION] == "1.0.0"
    saved = hass_storage[f"{DOMAIN}.repositories"]["data"][REPOSITORY_INTEGRATION_ID]
    assert saved["installed"] is True
    assert saved["version_installed"] == VERSION


@pytest.mark.usefixtures("enable_custom_integrations", "disconnected_manifest")
async def test_unmanaged_install_stays_unmanaged(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """An on-disk package alone cannot establish Marketplace ownership."""
    await setup_integration(hass, mock_config_entry)

    assert (
        entity_registry.async_get_entity_id(
            Platform.UPDATE, DOMAIN, REPOSITORY_INTEGRATION_ID
        )
        is None
    )


@pytest.mark.usefixtures("enable_custom_integrations")
@pytest.mark.parametrize(
    "issue_tracker",
    [
        pytest.param("https://github.com/test/fork/issues", id="fork"),
        pytest.param(
            f"https://example.com/github.com/{REPOSITORY_INTEGRATION}/issues",
            id="unrelated-host",
        ),
    ],
)
async def test_does_not_claim_another_source(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    old_update_entity: er.RegistryEntry,
    disconnected_manifest: Path,
    issue_tracker: str,
) -> None:
    """Keep an orphaned entity unavailable when the manifest points elsewhere."""
    manifest = json.loads(disconnected_manifest.read_text())
    manifest["issue_tracker"] = issue_tracker
    disconnected_manifest.write_text(json.dumps(manifest))
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(old_update_entity.entity_id)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE
