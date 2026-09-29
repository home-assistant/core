"""Tests that uninstalling only touches the files of that repository."""

from copy import deepcopy
from pathlib import Path
from typing import Any
from unittest.mock import patch

from aiogithubapi.models.git_tree import GitHubGitTreeEntryModel
import pytest

from homeassistant.components.marketplace.base import MarketplaceManager
from homeassistant.components.marketplace.data_client import CatalogClient
from homeassistant.components.marketplace.exceptions import MarketplaceError
from homeassistant.components.marketplace.repositories.template import (
    TemplateRepository,
)
from homeassistant.components.marketplace.repositories.theme import ThemeRepository
from homeassistant.core import HomeAssistant

from . import get_marketplace
from .const import REPOSITORY_PLUGIN_ID

THEME_ID = "1296266"


async def test_theme_can_not_take_the_folder_of_another_theme(
    marketplace: MarketplaceManager,
) -> None:
    """Test a theme is refused when another installed theme has its folder."""
    first = ThemeRepository(marketplace, "owner-one/theme-one")
    first.data.id = "111"
    first.data.file_name = "theme.yaml"
    first.data.installed = True
    marketplace.repositories.register(first)

    second = ThemeRepository(marketplace, "owner-two/theme-two")
    second.data.id = "222"
    second.data.file_name = "theme.yaml"
    assert first.localpath == second.localpath

    with pytest.raises(MarketplaceError, match="is owned by owner-one/theme-one"):
        await second.async_pre_install()


async def test_removing_a_theme_keeps_a_handwritten_theme(
    marketplace: MarketplaceManager, config_dir: Path
) -> None:
    """Test removal leaves a theme file the install never wrote alone."""
    repository = marketplace.repositories.get_by_id(THEME_ID)
    await repository.async_install_repository()
    handwritten = config_dir / "themes/theme-basic.yaml"
    handwritten.write_text("Handwritten Theme:\n  primary-color: red\n")
    assert handwritten.parent != Path(repository.localpath)

    await repository.uninstall()

    assert not Path(repository.localpath).exists()
    assert handwritten.exists()


async def test_template_refresh_keeps_the_installed_file_name(
    marketplace: MarketplaceManager,
) -> None:
    """Test a newer manifest naming another file does not change what is removed."""
    repository = TemplateRepository(marketplace, "owner/template")
    repository.data.id = "8003"
    repository.data.installed = True
    repository.data.file_name = "old.jinja"
    folder = Path(repository.localpath)
    folder.mkdir(parents=True)
    (folder / "old.jinja").write_text("installed template")
    other = folder / "new.jinja"
    other.write_text("another repository's template")

    async def refresh(*args: object, **kwargs: object) -> bool:
        repository.repository_manifest.filename = "new.jinja"
        return True

    with patch.object(repository, "common_update", refresh):
        await repository.update_repository(force=True)
    await repository.uninstall()

    assert other.exists()
    assert not (folder / "old.jinja").exists()


async def test_template_update_to_a_new_file_name_removes_the_old_file(
    marketplace: MarketplaceManager,
) -> None:
    """Test a version with another file name replaces the installed file."""
    repository = TemplateRepository(marketplace, "owner/template")
    repository.data.id = "8004"
    repository.data.installed = True
    repository.data.file_name = "old.jinja"
    folder = Path(repository.localpath)
    folder.mkdir(parents=True)
    (folder / "old.jinja").write_text("installed template")

    repository.repository_manifest.filename = "new.jinja"
    repository.treefiles = ["new.jinja"]
    repository.resolve_content()

    async def download() -> None:
        (folder / "new.jinja").write_text("new template")

    await repository._async_write_content(download)

    assert repository.data.file_name == "new.jinja"
    assert (folder / "new.jinja").read_text() == "new template"
    assert not (folder / "old.jinja").exists()


async def test_renamed_card_stays_installed_after_a_reload(
    hass: HomeAssistant, marketplace: MarketplaceManager
) -> None:
    """Test a card renamed on GitHub keeps pointing at the folder it is in."""
    repository = marketplace.repositories.get_by_id(REPOSITORY_PLUGIN_ID)
    await repository.async_install_repository()
    installed = Path(repository.localpath)
    assert installed.is_dir()
    marketplace.repositories.rename(repository, "hacs-test-org/renamed-card")
    get_data = CatalogClient.get_data

    async def renamed_catalog(
        self: CatalogClient, section: str | None, *, validate: bool
    ) -> Any:
        data = await get_data(self, section, validate=validate)
        if section == "plugin":
            data = deepcopy(data)
            data[REPOSITORY_PLUGIN_ID]["full_name"] = "hacs-test-org/renamed-card"
        return data

    with patch.object(CatalogClient, "get_data", renamed_catalog):
        await hass.config_entries.async_reload(
            marketplace.configuration.config_entry.entry_id
        )
        await hass.async_block_till_done()

    repository = get_marketplace(hass).repositories.get_by_id(REPOSITORY_PLUGIN_ID)
    assert installed.is_dir()
    assert repository.data.installed
    assert Path(repository.localpath) == installed


async def test_template_can_not_take_the_file_of_another_template(
    marketplace: MarketplaceManager,
) -> None:
    """Test a template version naming the file of another template is refused."""
    owner = TemplateRepository(marketplace, "owner/new-template")
    owner.data.id = "8005"
    owner.data.installed = True
    owner.data.file_name = "new.jinja"
    marketplace.repositories.register(owner)

    repository = TemplateRepository(marketplace, "owner/template")
    repository.data.id = "8006"
    repository.data.installed = True
    repository.data.file_name = "old.jinja"
    repository.repository_manifest.filename = "new.jinja"

    with pytest.raises(MarketplaceError, match="is owned by owner/new-template"):
        await repository.async_pre_install()


@pytest.mark.parametrize(
    ("content_in_root", "tree", "file_name"),
    [
        pytest.param(
            True, ["theme.yaml", "examples/demo.yaml"], "theme.yaml", id="root"
        ),
        pytest.param(
            False,
            ["themes/theme.yaml", "themes/examples/demo.yaml", "other/demo.yaml"],
            "theme.yaml",
            id="themes_folder",
        ),
    ],
)
async def test_theme_targets_the_file_in_its_folder(
    marketplace: MarketplaceManager,
    content_in_root: bool,
    tree: list[str],
    file_name: str,
) -> None:
    """Test a theme picks its file from the folder validation checked, not below."""
    repository = ThemeRepository(marketplace, "owner/theme")
    repository.repository_manifest.content_in_root = content_in_root
    repository.content.path.remote = "" if content_in_root else "themes"
    repository.tree = [
        GitHubGitTreeEntryModel({"path": path, "type": "blob"}) for path in tree
    ]

    repository.update_filenames()

    assert repository.data.file_name == file_name


async def test_theme_refresh_keeps_the_installed_folder(
    marketplace: MarketplaceManager,
) -> None:
    """Test a theme renamed upstream is removed from the folder it is in."""
    owner = ThemeRepository(marketplace, "owner/new-theme")
    owner.data.id = "9001"
    owner.data.installed = True
    owner.data.file_name = "new.yaml"
    owner.data.directory = "new"
    marketplace.repositories.register(owner)
    owned = Path(owner.localpath)
    owned.mkdir(parents=True)
    (owned / "new.yaml").write_text("New Theme:\n  primary-color: blue\n")

    repository = ThemeRepository(marketplace, "owner/theme")
    repository.data.id = "9002"
    repository.data.installed = True
    repository.data.file_name = "old.yaml"
    repository.data.directory = "old"
    installed = Path(repository.localpath)
    installed.mkdir(parents=True)
    (installed / "old.yaml").write_text("Old Theme:\n  primary-color: red\n")

    async def refresh(*args: object, **kwargs: object) -> bool:
        repository.tree = [
            GitHubGitTreeEntryModel({"path": "themes/new.yaml", "type": "blob"})
        ]
        return True

    with patch.object(repository, "common_update", refresh):
        await repository.update_repository(force=True)
    await repository.uninstall()

    assert not installed.exists()
    assert (owned / "new.yaml").exists()


async def test_removing_a_symlinked_install_keeps_its_source(
    marketplace: MarketplaceManager, config_dir: Path
) -> None:
    """Test removal takes the symlink away, not what it points at."""
    repository = marketplace.repositories.get_by_id(REPOSITORY_PLUGIN_ID)
    repository.data.installed = True
    source = config_dir / "development/card"
    source.mkdir(parents=True)
    (source / "card.js").write_text("source checkout")
    local = Path(repository.localpath)
    local.parent.mkdir(parents=True, exist_ok=True)
    local.symlink_to(source, target_is_directory=True)

    await repository.uninstall()

    assert not local.is_symlink()
    assert (source / "card.js").read_text() == "source checkout"
