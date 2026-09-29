"""Tests that a download or update leaves a working install behind."""

import asyncio
import gzip
import io
import json
from pathlib import Path
import shutil
from threading import Event
from types import ModuleType
from typing import Any, BinaryIO
from unittest.mock import AsyncMock, patch
import zipfile

import pytest

from homeassistant.components.marketplace.base import MarketplaceManager
from homeassistant.components.marketplace.exceptions import MarketplaceError
from homeassistant.components.marketplace.repositories.base import (
    FileInformation,
    Repository,
    RepositoryArchive,
    RepositoryManifest,
)
from homeassistant.components.marketplace.repositories.integration import (
    IntegrationRepository,
)
from homeassistant.components.marketplace.repositories.plugin import PluginRepository
from homeassistant.components.marketplace.repositories.template import (
    TemplateRepository,
)
from homeassistant.components.marketplace.utils.backup import (
    Backup,
    restore_interrupted_backups,
)
from homeassistant.config import async_hass_config_yaml
from homeassistant.core import HomeAssistant
from homeassistant.loader import Integration

from . import mocked_response
from .conftest import MarketplaceResponses
from .const import REPOSITORY_INTEGRATION_ID

THEME_ID = "1296266"


def _zip(files: dict[str, str]) -> bytes:
    """Return a ZIP file holding the given members."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, content in files.items():
            archive.writestr(name, content)
    return buffer.getvalue()


def _archive(files: dict[str, str]) -> RepositoryArchive:
    """Return an archive with the top level directory GitHub adds."""
    return RepositoryArchive(
        _zip({f"repo-main/{name}": value for name, value in files.items()})
    )


def _manifest(**changes: Any) -> dict[str, Any]:
    """Return the manifest of the example integration, with changes."""
    return {
        "domain": "example",
        "name": "Example",
        "version": "1.0.0",
        "config_flow": False,
    } | changes


async def _working_integration(marketplace: MarketplaceManager) -> Repository:
    """Download the example integration and make it one the loader accepts."""
    repository = marketplace.repositories.get_by_id(REPOSITORY_INTEGRATION_ID)
    await repository.async_download_repository()

    local = Path(repository.localpath)
    (local / "__init__.py").write_text("# working old integration\n")
    (local / "manifest.json").write_text(json.dumps(_manifest()))
    return repository


def _release(
    responses: MarketplaceResponses,
    repository: Repository,
    files: dict[str, str],
    *,
    manifest: dict[str, Any] | None = None,
    **repository_manifest: Any,
) -> None:
    """Publish version 2.0.0 of the example integration as a ZIP release."""
    repository.data.last_version = "2.0.0"
    base = f"https://raw.githubusercontent.com/{repository.data.full_name}/2.0.0"

    hacs_json = f"{base}/hacs.json"
    responses.add(
        hacs_json,
        mocked_response(
            hacs_json,
            json_content={
                "name": "Example",
                "zip_release": True,
                "filename": "release.zip",
                **repository_manifest,
            },
        ),
        keep=True,
    )

    integration_manifest = f"{base}/custom_components/example/manifest.json"
    responses.add(
        integration_manifest,
        mocked_response(
            integration_manifest,
            json_content=manifest or _manifest(version="2.0.0"),
        ),
        keep=True,
    )

    asset = (
        f"https://github.com/{repository.data.full_name}"
        "/releases/download/2.0.0/release.zip"
    )
    responses.add(asset, mocked_response(asset, content=_zip(files)), keep=True)


def _custom_components(hass: HomeAssistant) -> ModuleType:
    """Return a root module the loader resolves custom integrations from."""
    root = ModuleType("custom_components")
    root.__path__ = [hass.config.path("custom_components")]
    return root


async def test_failed_card_update_restores_previous_files(
    marketplace: MarketplaceManager,
) -> None:
    """Test a card of release assets is backed up like any other download."""
    repository = PluginRepository(marketplace, "review/test-card")
    repository.data.installed = True
    repository.content.single = True
    folder = Path(repository.localpath)
    folder.mkdir(parents=True)
    (folder / "test-card.js").write_bytes(b"old working version")

    async def download() -> None:
        await repository._async_write_file(
            FileInformation(
                name="test-card.js", path="test-card.js", url="https://example.org/card"
            ),
            b"new version",
        )
        repository.validate.errors.append("chunk.js failed to download")

    with pytest.raises(MarketplaceError):
        await repository._async_write_content(download)

    assert (folder / "test-card.js").read_bytes() == b"old working version"


async def test_failed_backup_stops_the_download(
    marketplace: MarketplaceManager,
) -> None:
    """Test nothing is written when the backup of the install fails."""
    repository = PluginRepository(marketplace, "review/test-card")
    repository.data.installed = True
    folder = Path(repository.localpath)
    folder.mkdir(parents=True)
    (folder / "test-card.js").write_bytes(b"old working version")
    download = AsyncMock()

    with (
        patch(
            "homeassistant.components.marketplace.utils.backup.shutil.move",
            side_effect=OSError("disk full"),
        ),
        pytest.raises(MarketplaceError, match="Could not back up"),
    ):
        await repository._async_write_content(download)

    download.assert_not_called()
    assert (folder / "test-card.js").read_bytes() == b"old working version"


async def test_failed_first_download_keeps_a_manual_install(
    marketplace: MarketplaceManager, response_mocker: MarketplaceResponses
) -> None:
    """Test files already in place before the first download are backed up too."""
    repository = marketplace.repositories.get_by_id(REPOSITORY_INTEGRATION_ID)
    assert not repository.data.installed
    local = Path(repository.localpath)
    local.mkdir(parents=True)
    original = local / "__init__.py"
    original.write_text("# manually installed working version\n")

    _release(response_mocker, repository, {})
    broken_archive = _zip(
        {"__init__.py": "# new code\n", "broken.py": "assert 2 == 2"}
    ).replace(b"assert 2 == 2", b"assert 2 == 3")
    url = (
        f"https://github.com/{repository.data.full_name}"
        "/releases/download/2.0.0/release.zip"
    )
    response_mocker.add(url, mocked_response(url, content=broken_archive), keep=True)

    with pytest.raises(MarketplaceError):
        await repository.async_download_repository()

    assert original.read_text() == "# manually installed working version\n"


def test_archive_extracts_only_the_named_directory(tmp_path: Path) -> None:
    """Test a sibling directory whose name starts the same is left out."""
    RepositoryArchive(
        _zip(
            {
                "repo-1/custom_components/foo/__init__.py": "foo code",
                "repo-1/custom_components/foo/bar/__init__.py": "correct submodule",
                "repo-1/custom_components/foobar/__init__.py": "foobar code",
            }
        )
    ).extract_directory("custom_components/foo", str(tmp_path))

    assert (tmp_path / "__init__.py").read_text() == "foo code"
    assert (tmp_path / "bar" / "__init__.py").read_text() == "correct submodule"
    assert sorted(path.name for path in tmp_path.iterdir()) == ["__init__.py", "bar"]


async def test_template_installs_the_file_in_the_root(
    marketplace: MarketplaceManager,
) -> None:
    """Test an example with the same name does not replace the real template."""
    repository = TemplateRepository(marketplace, "owner/template")
    repository.repository_manifest.filename = "a.jinja"
    archive = _archive(
        {"a.jinja": "real template", "examples/a.jinja": "example template"}
    )
    repository.tree = archive.tree
    repository.treefiles = [entry.path for entry in archive.tree]
    repository.resolve_archive_content()

    await repository._async_write_archive_content(archive)

    assert (Path(repository.localpath) / "a.jinja").read_text() == "real template"


async def test_older_version_checks_the_domain_it_writes_to(
    marketplace: MarketplaceManager,
) -> None:
    """Test ownership is checked for the domain of the version being written."""
    owner = IntegrationRepository(marketplace, "owner/existing")
    owner.data.id = "8001"
    owner.data.domain = "existing_domain"
    owner.data.installed = True
    marketplace.repositories.register(owner)
    original = Path(owner.localpath) / "__init__.py"
    original.parent.mkdir(parents=True)
    original.write_bytes(b"existing integration")

    candidate = IntegrationRepository(marketplace, "other/renamed")
    candidate.data.id = "8002"
    candidate.data.domain = "new_domain"
    candidate.data.last_version = "2.0.0"
    candidate.data.releases = True
    candidate.content.path.remote = "custom_components/existing_domain"
    marketplace.repositories.register(candidate)

    async def download(version: str) -> None:
        await candidate._async_write_file(
            FileInformation(
                name="__init__.py",
                path="custom_components/existing_domain/__init__.py",
                url="https://example.org/integration",
            ),
            b"other integration",
        )

    with (
        patch.object(candidate, "common_update", AsyncMock(return_value=True)),
        patch.object(
            candidate,
            "get_repository_manifest",
            AsyncMock(return_value=RepositoryManifest()),
        ),
        patch.object(
            candidate,
            "async_get_integration_manifest",
            AsyncMock(return_value={"domain": "existing_domain", "name": "Old name"}),
        ),
        patch.object(candidate, "_async_download_version", download),
        patch.object(candidate, "async_post_installation", AsyncMock()),
        pytest.raises(MarketplaceError, match="is owned by owner/existing"),
    ):
        await candidate.async_download_repository(ref="1.0.0")

    assert original.read_bytes() == b"existing integration"


async def test_released_gzip_and_generated_gzip_do_not_mix(
    hass: HomeAssistant, marketplace: MarketplaceManager
) -> None:
    """Test a release shipping its own gzip still ends with a valid gzip file."""
    repository = PluginRepository(marketplace, "review/card")
    repository.content.single = True
    javascript = b"console.log('a dashboard card');\n" * 100
    published_gzip = gzip.compress(javascript, compresslevel=0)
    generated_gzip_started = asyncio.Event()
    published_gzip_written = Event()
    copyfileobj = shutil.copyfileobj
    save_file = marketplace.async_save_file

    def paused_copy(source: BinaryIO, target: BinaryIO, length: int = 0) -> None:
        """Hold the generated gzip until the published one is written."""
        hass.loop.call_soon_threadsafe(generated_gzip_started.set)
        assert published_gzip_written.wait(timeout=5)
        copyfileobj(source, target, length)

    async def download(url: str, **kwargs: Any) -> bytes:
        if url.endswith(".gz"):
            await generated_gzip_started.wait()
            return published_gzip
        return javascript

    async def save(path: str, content: Any) -> bool:
        result = await save_file(path, content)
        if path.endswith(".gz"):
            published_gzip_written.set()
        return result

    try:
        with (
            patch(
                "homeassistant.components.marketplace.base.shutil.copyfileobj",
                paused_copy,
            ),
            patch.object(marketplace, "async_download_file", download),
            patch.object(marketplace, "async_save_file", save),
        ):
            await repository._async_download_files(
                [
                    FileInformation(
                        name="card.js",
                        path="card.js",
                        url="https://example.org/card.js",
                    ),
                    FileInformation(
                        name="card.js.gz",
                        path="card.js.gz",
                        url="https://example.org/card.js.gz",
                    ),
                ]
            )
    finally:
        published_gzip_written.set()

    assert not repository.validate.errors
    assert (
        gzip.decompress((Path(repository.localpath) / "card.js.gz").read_bytes())
        == javascript
    )


async def test_card_release_without_the_named_file_keeps_the_card(
    marketplace: MarketplaceManager,
) -> None:
    """Test a release without the card's file is refused, not an empty update."""
    repository = PluginRepository(marketplace, "owner/card")
    repository.data.id = "8100"
    repository.data.file_name = "card.js"
    repository.data.releases = True
    repository.data.last_version = "2.0.0"
    repository.data.installed = True
    repository.data.installed_version = "1.0.0"
    repository.content.path.remote = ""
    local = Path(repository.localpath)
    local.mkdir(parents=True)
    (local / "card.js").write_text("working card")
    repository.tree = _archive({"other.js": "unrelated asset"}).tree
    repository.repository_manifest = RepositoryManifest.from_dict(
        {"content_in_root": True, "filename": "card.js"}
    )

    with (
        patch.object(repository, "common_update", AsyncMock(return_value=True)),
        patch.object(
            repository,
            "get_repository_manifest",
            AsyncMock(return_value=repository.repository_manifest),
        ),
        pytest.raises(MarketplaceError),
    ):
        await repository.async_download_repository(ref="2.0.0")

    assert repository.data.installed_version == "1.0.0"
    assert (local / "card.js").read_text() == "working card"


async def test_release_with_an_extra_directory_keeps_the_integration(
    marketplace: MarketplaceManager, response_mocker: MarketplaceResponses
) -> None:
    """Test a ZIP that would leave no manifest where the loader looks is refused."""
    repository = await _working_integration(marketplace)
    local = Path(repository.localpath)
    original = (local / "manifest.json").read_text()
    _release(
        response_mocker,
        repository,
        {"example/manifest.json": original, "example/__init__.py": ""},
    )

    with pytest.raises(MarketplaceError, match="manifest.json"):
        await repository.async_download_repository()

    assert repository.data.installed_version == "1.0.0"
    assert (local / "manifest.json").read_text() == original
    assert not (local / "example").exists()


@pytest.mark.parametrize(
    "manifest",
    [
        pytest.param({"domain": "example", "name": "Example"}, id="no_version"),
        pytest.param(_manifest(version="not a version!"), id="invalid_version"),
        pytest.param(_manifest(domain="other"), id="other_domain"),
    ],
)
async def test_release_the_loader_refuses_keeps_the_integration(
    hass: HomeAssistant,
    marketplace: MarketplaceManager,
    response_mocker: MarketplaceResponses,
    manifest: dict[str, Any],
) -> None:
    """Test a release whose manifest the loader would refuse is not installed."""
    repository = await _working_integration(marketplace)
    root = _custom_components(hass)
    assert await hass.async_add_executor_job(
        Integration.resolve_from_root, hass, root, "example"
    )
    _release(
        response_mocker,
        repository,
        {"manifest.json": json.dumps(manifest), "__init__.py": ""},
    )

    with pytest.raises(MarketplaceError, match="manifest.json"):
        await repository.async_download_repository()

    assert await hass.async_add_executor_job(
        Integration.resolve_from_root, hass, root, "example"
    )
    assert repository.data.installed_version == "1.0.0"


async def test_persistent_directory_has_to_be_a_directory_inside(
    marketplace: MarketplaceManager, response_mocker: MarketplaceResponses
) -> None:
    """Test a persistent directory covering the whole install is refused."""
    repository = await _working_integration(marketplace)
    local = Path(repository.localpath)
    _release(
        response_mocker,
        repository,
        {
            "manifest.json": json.dumps(_manifest(version="2.0.0")),
            "__init__.py": "# new release\n",
        },
        persistent_directory=".",
    )

    with pytest.raises(MarketplaceError, match="persistent_directory"):
        await repository.async_download_repository()

    assert repository.data.installed_version == "1.0.0"
    assert (local / "__init__.py").read_text() == "# working old integration\n"


async def test_invalid_theme_keeps_the_configuration_loadable(
    hass: HomeAssistant,
    marketplace: MarketplaceManager,
    response_mocker: MarketplaceResponses,
    config_dir: Path,
) -> None:
    """Test a theme that is not valid YAML is not written over a working one."""
    (config_dir / "configuration.yaml").write_text(
        "frontend:\n  themes: !include_dir_merge_named themes\n"
    )
    repository = marketplace.repositories.get_by_id(THEME_ID)
    await repository.async_download_repository()
    await hass.async_block_till_done()
    assert await async_hass_config_yaml(hass)

    repository.data.last_version = "2.0.0"
    archive = _zip({"repo-2.0.0/themes/example.yaml": "Example:\n  primary-color: [\n"})
    url = f"https://github.com/{repository.data.full_name}/archive/refs/tags/2.0.0.zip"
    response_mocker.add(url, mocked_response(url, content=archive), keep=True)

    with pytest.raises(MarketplaceError, match="not valid YAML"):
        await repository.async_download_repository()
    await hass.async_block_till_done()

    assert await async_hass_config_yaml(hass)


def test_interrupted_update_of_a_symlink_keeps_its_source(
    marketplace: MarketplaceManager, config_dir: Path
) -> None:
    """Test recovery puts the symlink back, without touching what it points at."""
    source = config_dir / "development/example"
    source.mkdir(parents=True)
    (source / "__init__.py").write_text("source checkout")
    local = config_dir / "custom_components/example"
    local.parent.mkdir(parents=True, exist_ok=True)
    local.symlink_to(source, target_is_directory=True)

    Backup(marketplace, local).create()
    local.mkdir()
    (local / "__init__.py").write_text("partial update")
    restore_interrupted_backups(marketplace)

    assert not source.is_symlink()
    assert (source / "__init__.py").read_text() == "source checkout"
    assert local.is_symlink()
    assert local.resolve() == source.resolve()


async def test_failed_release_leaves_no_temporary_archive(
    marketplace: MarketplaceManager,
    response_mocker: MarketplaceResponses,
    config_dir: Path,
) -> None:
    """Test the scratch directory of a broken ZIP release is removed."""
    repository = await _working_integration(marketplace)
    _release(response_mocker, repository, {"__init__.py": "# update\n"})
    url = (
        f"https://github.com/{repository.data.full_name}"
        "/releases/download/2.0.0/release.zip"
    )
    response_mocker.add(
        url, mocked_response(url, content=b"PK\x03\x04truncated"), keep=True
    )
    scratch = config_dir / "download-temporary-directory"
    scratch.mkdir()

    with (
        patch(
            "homeassistant.components.marketplace.repositories.base.tempfile.mkdtemp",
            return_value=str(scratch),
        ),
        pytest.raises(MarketplaceError),
    ):
        await repository.async_download_repository()

    assert not scratch.exists()


async def test_second_download_of_a_repository_waits_its_turn(
    marketplace: MarketplaceManager,
) -> None:
    """Test a download of a repository that is already downloading is refused."""
    repository = marketplace.repositories.get_by_id(REPOSITORY_INTEGRATION_ID)
    started = asyncio.Event()
    release = asyncio.Event()

    async def slow_download(*args: Any, **kwargs: Any) -> None:
        started.set()
        await release.wait()

    with patch.object(repository, "_async_download_catalog_version", slow_download):
        first = asyncio.create_task(repository.async_download_repository())
        await started.wait()

        with pytest.raises(MarketplaceError, match="already downloading"):
            await repository.async_download_repository()

        release.set()
        await first


async def test_valid_release_updates_the_integration(
    hass: HomeAssistant,
    marketplace: MarketplaceManager,
    response_mocker: MarketplaceResponses,
) -> None:
    """Test a correctly packaged release updates the code and the stored version."""
    repository = await _working_integration(marketplace)
    _release(
        response_mocker,
        repository,
        {
            "manifest.json": json.dumps(_manifest(version="2.0.0")),
            "__init__.py": "# new code\n",
        },
    )

    await repository.async_download_repository()

    integration = await hass.async_add_executor_job(
        Integration.resolve_from_root, hass, _custom_components(hass), "example"
    )
    assert integration is not None
    assert integration.version == "2.0.0"
    assert repository.data.installed_version == "2.0.0"
