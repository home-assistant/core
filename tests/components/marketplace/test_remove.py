"""Tests that removing a download only touches the files of that download."""

from copy import deepcopy
from pathlib import Path
from typing import Any
from unittest.mock import patch

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
    """Test a theme is refused when another downloaded theme has its folder."""
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
    """Test removal leaves a theme file the download never wrote alone."""
    repository = marketplace.repositories.get_by_id(THEME_ID)
    await repository.async_download_repository()
    handwritten = config_dir / "themes/theme-basic.yaml"
    handwritten.write_text("Handwritten Theme:\n  primary-color: red\n")
    assert handwritten.parent != Path(repository.localpath)

    await repository.uninstall()

    assert not Path(repository.localpath).exists()
    assert handwritten.exists()


async def test_template_refresh_keeps_the_downloaded_file_name(
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
    """Test a version with another file name replaces the downloaded file."""
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


async def test_renamed_card_stays_downloaded_after_a_reload(
    hass: HomeAssistant, marketplace: MarketplaceManager
) -> None:
    """Test a card renamed on GitHub keeps pointing at the folder it is in."""
    repository = marketplace.repositories.get_by_id(REPOSITORY_PLUGIN_ID)
    await repository.async_download_repository()
    downloaded = Path(repository.localpath)
    assert downloaded.is_dir()
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
    assert downloaded.is_dir()
    assert repository.data.installed
    assert Path(repository.localpath) == downloaded
