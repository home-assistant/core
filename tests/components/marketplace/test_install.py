"""Tests that an install or update leaves a working install behind."""

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
from homeassistant.components.marketplace.const import DOMAIN
from homeassistant.components.marketplace.enums import MarketplaceSignal
from homeassistant.components.marketplace.exceptions import (
    MarketplaceError,
    RepositoryBusyError,
)
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
from homeassistant.components.marketplace.utils.storage import async_load_from_storage
from homeassistant.config import async_hass_config_yaml
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.template import MAX_CUSTOM_TEMPLATE_SIZE
from homeassistant.loader import Integration

from . import mocked_response
from .conftest import MarketplaceResponses
from .const import REPOSITORY_INTEGRATION_ID, REPOSITORY_PLUGIN_ID

from tests.typing import WebSocketGenerator

THEME_ID = "1296266"
TEMPLATE_ID = "1296268"


def _zip(files: dict[str, str | bytes]) -> bytes:
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
    """Install the example integration and make it one the loader accepts."""
    repository = marketplace.repositories.get_by_id(REPOSITORY_INTEGRATION_ID)
    await repository.async_install_repository()

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
    """Test a card of release assets is backed up like any other install."""
    repository = PluginRepository(marketplace, "review/test-card")
    repository.data.installed = True
    repository.content.single = True
    repository.content.path.remote = ""
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


async def test_failed_backup_stops_the_install(
    marketplace: MarketplaceManager,
) -> None:
    """Test nothing is written when the backup of the install fails."""
    repository = PluginRepository(marketplace, "review/test-card")
    repository.data.installed = True
    repository.content.path.remote = ""
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


async def test_backup_left_behind_after_an_update_is_not_restored(
    marketplace: MarketplaceManager,
) -> None:
    """Test a backup the update could not remove never brings back the old version."""
    repository = PluginRepository(marketplace, "review/test-card")
    repository.data.installed = True
    repository.content.single = True
    repository.content.path.remote = ""
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

    with patch(
        "homeassistant.components.marketplace.utils.backup.shutil.rmtree",
        side_effect=OSError("device busy"),
    ):
        await repository._async_write_content(download)

    # The next start treats what is left like an unfinished install
    await marketplace.hass.async_add_executor_job(
        restore_interrupted_backups, marketplace
    )

    assert (folder / "test-card.js").read_bytes() == b"new version"


async def test_backup_that_would_come_back_fails_the_update(
    marketplace: MarketplaceManager,
) -> None:
    """Test the update says so when its backup would put the old version back."""
    repository = PluginRepository(marketplace, "review/test-card")
    repository.data.installed = True
    repository.content.single = True
    repository.content.path.remote = ""
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

    with (
        patch(
            "homeassistant.components.marketplace.utils.backup.os.remove",
            side_effect=OSError("read-only file system"),
        ),
        pytest.raises(MarketplaceError, match="backup"),
    ):
        await repository._async_write_content(download)


async def test_failed_first_install_keeps_a_manual_install(
    marketplace: MarketplaceManager, response_mocker: MarketplaceResponses
) -> None:
    """Test files already in place before the first install are backed up too."""
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
        await repository.async_install_repository()

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


async def test_file_by_file_download_has_the_archive_limits(
    marketplace: MarketplaceManager,
) -> None:
    """Test the way around a capped archive is capped the same way."""
    repository = marketplace.repositories.get_by_id(REPOSITORY_PLUGIN_ID)
    repository.content.path.remote = ""
    contents = [
        FileInformation(f"https://example.com/{name}", name, name)
        for name in ("a.js", "b.js", "c.js")
    ]

    with (
        patch(
            "homeassistant.components.marketplace.repositories.base.MAX_ARCHIVE_MEMBERS",
            2,
        ),
        pytest.raises(MarketplaceError) as exc_info,
    ):
        await repository._async_download_files(contents)

    assert exc_info.value.translation_key == "content_too_many_files"

    with (
        patch(
            "homeassistant.components.marketplace.repositories.base.MAX_DOWNLOAD_SIZE",
            100,
        ),
        patch.object(
            marketplace, "async_download_file", AsyncMock(return_value=b"x" * 60)
        ),
        patch.object(repository, "_async_write_file") as write,
    ):
        await repository._async_download_files(contents)

    assert write.call_count == 1
    assert {error.translation_key for error in repository.validate.errors} == {
        "content_over_limit"
    }


def test_archive_with_too_many_members_is_refused() -> None:
    """Test an archive of countless tiny entries is not taken apart."""
    with (
        patch(
            "homeassistant.components.marketplace.repositories.base.MAX_ARCHIVE_MEMBERS",
            1,
        ),
        pytest.raises(MarketplaceError) as exc_info,
    ):
        _archive({"a.py": "", "b.py": ""})

    assert exc_info.value.translation_key == "archive_too_many_files"


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
        pytest.raises(MarketplaceError) as exc_info,
    ):
        await candidate.async_install_repository(ref="1.0.0")

    assert exc_info.value.translation_key == "integration_owned"
    assert exc_info.value.translation_placeholders["owner"] == "owner/existing"

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
        await repository.async_install_repository(ref="2.0.0")

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
        await repository.async_install_repository()

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
        await repository.async_install_repository()

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
        await repository.async_install_repository()

    assert repository.data.installed_version == "1.0.0"
    assert (local / "__init__.py").read_text() == "# working old integration\n"


@pytest.mark.parametrize(
    ("theme", "error"),
    [
        pytest.param("Example:\n  primary-color: [\n", "not valid YAML", id="yaml"),
        pytest.param(
            "Example:\n  primary-color: [red, blue]\n", "not a valid theme", id="schema"
        ),
        pytest.param(
            "Example: !include ../../secrets.yaml\n", "!include", id="include"
        ),
        pytest.param("&x [*x]\n", "recursive", id="recursive_alias"),
        pytest.param(
            "Example:\n  primary-color: café\n".encode("cp1252"),
            "not valid YAML",
            id="encoding",
        ),
    ],
)
async def test_invalid_theme_keeps_the_configuration_loadable(
    hass: HomeAssistant,
    marketplace: MarketplaceManager,
    response_mocker: MarketplaceResponses,
    config_dir: Path,
    theme: str | bytes,
    error: str,
) -> None:
    """Test a theme the frontend can not load is not written over a working one."""
    (config_dir / "configuration.yaml").write_text(
        "frontend:\n  themes: !include_dir_merge_named themes\n"
    )
    # A valid theme, so only the tag that reaches it can be what is refused
    (config_dir / "secrets.yaml").write_text("primary-color: red\n")
    repository = marketplace.repositories.get_by_id(THEME_ID)
    await repository.async_install_repository()
    await hass.async_block_till_done()
    assert await async_hass_config_yaml(hass)

    repository.data.last_version = "2.0.0"
    archive = _zip({"repo-2.0.0/themes/example.yaml": theme})
    url = f"https://github.com/{repository.data.full_name}/archive/refs/tags/2.0.0.zip"
    response_mocker.add(url, mocked_response(url, content=archive), keep=True)

    with pytest.raises(MarketplaceError, match=error):
        await repository.async_install_repository()
    await hass.async_block_till_done()

    assert await async_hass_config_yaml(hass)
    assert (config_dir / "themes/example/example.yaml").read_text() != theme


async def test_template_larger_than_core_reads_is_refused(
    marketplace: MarketplaceManager,
) -> None:
    """Test a template Core would skip is not reported as installed."""
    repository = TemplateRepository(marketplace, "owner/template")
    repository.repository_manifest.filename = "large.jinja"

    async def write_large_template() -> None:
        path = Path(repository.localpath)
        path.mkdir(parents=True, exist_ok=True)
        (path / "large.jinja").write_bytes(b"x" * (MAX_CUSTOM_TEMPLATE_SIZE + 1))

    with pytest.raises(MarketplaceError, match="larger than"):
        await repository._async_write_content(write_large_template)

    assert not (Path(repository.localpath) / "large.jinja").exists()


async def test_template_that_is_not_utf8_keeps_the_old_one(
    hass: HomeAssistant,
    marketplace: MarketplaceManager,
    response_mocker: MarketplaceResponses,
    config_dir: Path,
) -> None:
    """Test a template Home Assistant can not read is not written over a working one."""
    repository = marketplace.repositories.get_by_id(TEMPLATE_ID)
    await repository.async_install_repository()
    await hass.async_block_till_done()
    installed = config_dir / "custom_templates/example.jinja"
    working = installed.read_bytes()

    repository.data.last_version = "2.0.0"
    archive = _zip(
        {
            "repo-2.0.0/example.jinja": "{{ 'café' }}".encode("cp1252"),
            "repo-2.0.0/hacs.json": json.dumps(
                {"name": "Template", "filename": "example.jinja"}
            ),
        }
    )
    url = f"https://github.com/{repository.data.full_name}/archive/refs/tags/2.0.0.zip"
    response_mocker.add(url, mocked_response(url, content=archive), keep=True)

    with pytest.raises(MarketplaceError) as exc_info:
        await repository.async_install_repository()

    assert exc_info.value.translation_key == "template_not_utf8"
    await hass.async_block_till_done()

    assert installed.read_bytes() == working


@pytest.mark.parametrize(
    "relative", [pytest.param(False, id="absolute"), pytest.param(True, id="relative")]
)
def test_interrupted_update_of_a_symlink_keeps_its_source(
    marketplace: MarketplaceManager, config_dir: Path, relative: bool
) -> None:
    """Test recovery puts the symlink back, without touching what it points at."""
    source = config_dir / "development/example"
    source.mkdir(parents=True)
    (source / "__init__.py").write_text("source checkout")
    local = config_dir / "custom_components/example"
    local.parent.mkdir(parents=True, exist_ok=True)
    # A relative link does not resolve from inside the backup
    local.symlink_to(
        Path("../development/example") if relative else source,
        target_is_directory=True,
    )

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
        await repository.async_install_repository()

    assert not scratch.exists()


async def test_second_install_of_a_repository_waits_its_turn(
    marketplace: MarketplaceManager,
) -> None:
    """Test an install of a repository that is already installing is refused."""
    repository = marketplace.repositories.get_by_id(REPOSITORY_INTEGRATION_ID)
    started = asyncio.Event()
    release = asyncio.Event()

    async def slow_install(*args: Any, **kwargs: Any) -> None:
        started.set()
        await release.wait()

    with patch.object(repository, "_async_install_catalog_version", slow_install):
        first = asyncio.create_task(repository.async_install_repository())
        await started.wait()

        with pytest.raises(MarketplaceError, match="is being installed"):
            await repository.async_install_repository()

        release.set()
        await first


async def test_failed_step_after_writing_keeps_the_install(
    hass: HomeAssistant,
    marketplace: MarketplaceManager,
    hass_ws_client: WebSocketGenerator,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test a step failing after the files were written still records them."""
    client = await hass_ws_client(hass)
    with patch.object(
        PluginRepository,
        "update_dashboard_resources",
        side_effect=HomeAssistantError("The resources are read only"),
    ):
        await client.send_json_auto_id(
            {
                "type": "marketplace/repository/install",
                "repository": REPOSITORY_PLUGIN_ID,
            }
        )
        response = await client.receive_json()
    await hass.async_block_till_done()

    assert response["error"]["code"] == "error"
    assert "The resources are read only" in response["error"]["message"]
    assert marketplace.repositories.get_by_id(REPOSITORY_PLUGIN_ID).data.installed
    stored = await async_load_from_storage(hass, "repositories")
    assert stored[REPOSITORY_PLUGIN_ID]["installed"]
    assert entity_registry.async_get_entity_id(
        Platform.UPDATE, DOMAIN, REPOSITORY_PLUGIN_ID
    )


async def test_install_tells_the_panel_once(
    hass: HomeAssistant,
    marketplace: MarketplaceManager,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test one install makes an open panel fetch the repositories once."""
    client = await hass_ws_client(hass)
    with patch.object(
        marketplace, "async_dispatch", wraps=marketplace.async_dispatch
    ) as dispatch:
        await client.send_json_auto_id(
            {
                "type": "marketplace/repository/install",
                "repository": REPOSITORY_PLUGIN_ID,
            }
        )
        assert (await client.receive_json())["success"]
        await hass.async_block_till_done()

    signals = [call.args[0] for call in dispatch.call_args_list]
    assert signals.count(MarketplaceSignal.REPOSITORY) == 1
    assert signals.count(MarketplaceSignal.CONFIG) == 1


async def test_uninstall_during_an_install_is_refused(
    hass: HomeAssistant,
    marketplace: MarketplaceManager,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test an uninstall does not pull the files from under a running install."""
    repository = marketplace.repositories.get_by_id(REPOSITORY_INTEGRATION_ID)
    started = asyncio.Event()
    release = asyncio.Event()

    async def slow_install(*args: Any, **kwargs: Any) -> None:
        started.set()
        await release.wait()

    client = await hass_ws_client(hass)
    with (
        patch.object(repository, "_async_install_catalog_version", slow_install),
        patch.object(repository, "_async_uninstall") as uninstall,
    ):
        install = asyncio.create_task(repository.async_install_repository())
        await started.wait()

        with pytest.raises(RepositoryBusyError):
            await repository.uninstall()

        await client.send_json_auto_id(
            {
                "type": "marketplace/repository/uninstall",
                "repository": REPOSITORY_INTEGRATION_ID,
            }
        )
        response = await client.receive_json()

        release.set()
        await install

    assert response["error"]["code"] == "repository_busy"
    uninstall.assert_not_called()


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

    await repository.async_install_repository()

    integration = await hass.async_add_executor_job(
        Integration.resolve_from_root, hass, _custom_components(hass), "example"
    )
    assert integration is not None
    assert integration.version == "2.0.0"
    assert repository.data.installed_version == "2.0.0"


async def test_failed_first_install_leaves_nothing_behind(
    marketplace: MarketplaceManager,
) -> None:
    """Test a first install that fails removes what it wrote so far."""
    repository = PluginRepository(marketplace, "review/new-card")
    folder = Path(repository.localpath)
    assert not folder.exists()

    async def download() -> None:
        await repository._async_write_file(
            FileInformation(
                name="new-card.js", path="new-card.js", url="https://example.org/card"
            ),
            b"half of a card",
        )
        repository.validate.errors.append("chunk.js failed to download")

    with pytest.raises(MarketplaceError):
        await repository._async_write_content(download)

    assert not folder.exists()


@pytest.mark.parametrize(
    "file_name",
    [
        pytest.param("../configuration.yaml", id="outside"),
        pytest.param("sub/example.jinja", id="subfolder"),
        pytest.param("example.yaml", id="not_a_template"),
    ],
)
async def test_template_update_checks_the_file_name(
    marketplace: MarketplaceManager, config_dir: Path, file_name: str
) -> None:
    """Test a hacs.json of a new version can not point the template elsewhere."""
    configuration = config_dir / "configuration.yaml"
    configuration.write_text("default_config:\n")
    repository = TemplateRepository(marketplace, "owner/template")
    repository.data.id = "8007"
    repository.data.installed = True
    repository.data.file_name = "example.jinja"
    repository.repository_manifest.filename = file_name

    download = AsyncMock()
    with pytest.raises(MarketplaceError) as exc_info:
        await repository._async_write_content(download)

    assert exc_info.value.translation_key == "structure_not_compliant"

    download.assert_not_called()
    assert configuration.read_text() == "default_config:\n"


async def test_plugin_without_a_resource_is_not_written(
    marketplace: MarketplaceManager,
) -> None:
    """Test a card without a file to serve is refused before anything is written."""
    repository = marketplace.repositories.get_by_id(REPOSITORY_PLUGIN_ID)
    # What update_repository leaves behind for a version without a resource
    repository.content.path.remote = None
    repository.data.file_name = ""

    download = AsyncMock()
    with pytest.raises(MarketplaceError) as exc_info:
        await repository._async_write_content(download)

    assert exc_info.value.translation_key == "structure_not_compliant"

    download.assert_not_called()
    assert not Path(repository.localpath).exists()


async def test_template_from_a_zip_release_is_refused(
    marketplace: MarketplaceManager, config_dir: Path
) -> None:
    """Test a release ZIP can not spread files over the shared template folder."""
    repository = TemplateRepository(marketplace, "owner/template")
    repository.data.id = "8008"
    repository.repository_manifest.filename = "own.jinja"
    repository.repository_manifest.zip_release = True

    download = AsyncMock()
    with pytest.raises(MarketplaceError, match="ZIP release"):
        await repository._async_write_content(download)

    download.assert_not_called()
    assert not (config_dir / "custom_templates").exists()


async def test_cancelled_first_install_leaves_nothing(
    marketplace: MarketplaceManager, config_dir: Path
) -> None:
    """Test a first install that is cancelled halfway removes what it wrote."""
    repository = marketplace.repositories.get_by_id(REPOSITORY_PLUGIN_ID)
    repository.content.path.remote = ""
    local = Path(repository.localpath)

    async def cancelled_download() -> None:
        local.mkdir(parents=True)
        (local / "half.js").write_text("half of it")
        raise asyncio.CancelledError

    with pytest.raises(asyncio.CancelledError):
        await repository._async_write_content(cancelled_download)

    assert not local.exists()
    assert list((config_dir / ".storage" / "marketplace_backups").iterdir()) == []


async def test_failed_persistent_directory_restore_keeps_the_old_install(
    marketplace: MarketplaceManager, response_mocker: MarketplaceResponses
) -> None:
    """Test the old version stays when its kept data can not go into the new one."""
    repository = await _working_integration(marketplace)
    local = Path(repository.localpath)
    (local / "data").mkdir()
    (local / "data/settings.json").write_text("{}")
    _release(
        response_mocker,
        repository,
        {
            "manifest.json": json.dumps(_manifest(version="2.0.0")),
            "__init__.py": "# new release\n",
        },
        persistent_directory="data",
    )
    restore = Backup.restore
    persistent = local / "data"
    failed: list[Backup] = []

    # Only the first attempt fails, the rollback puts the kept data back
    def failing_restore(backup: Backup) -> None:
        if backup.local_path == persistent and not failed:
            failed.append(backup)
            raise OSError("Disk is full")
        restore(backup)

    with (
        patch.object(Backup, "restore", failing_restore),
        pytest.raises(MarketplaceError),
    ):
        await repository.async_install_repository()

    assert repository.data.installed_version == "1.0.0"
    assert (local / "__init__.py").read_text() == "# working old integration\n"
    assert (local / "data/settings.json").read_text() == "{}"
