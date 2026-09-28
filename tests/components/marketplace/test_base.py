"""Tests for the Marketplace base object."""

from unittest.mock import patch

import pytest

from homeassistant.components.marketplace.base import (
    MarketplaceConfiguration,
    MarketplaceManager,
    Repositories,
)
from homeassistant.components.marketplace.enums import RepositoryCategory
from homeassistant.components.marketplace.exceptions import MarketplaceError
from homeassistant.components.marketplace.repositories.base import Repository

from .const import DEFAULT_CATEGORIES, REPOSITORY_INTEGRATION, REPOSITORY_PLUGIN


def test_configuration_defaults() -> None:
    """Test the configuration defaults and what a dict can set."""
    configuration = MarketplaceConfiguration()
    configuration.update_from_dict({"token": "xxxxxxxxxx"})

    assert isinstance(configuration.to_json(), dict)
    assert configuration.token == "xxxxxxxxxx"


@pytest.mark.parametrize(
    "option",
    [
        pytest.param("experimental", id="experimental"),
        pytest.param("netdaemon", id="netdaemon"),
        pytest.param("release_limit", id="release_limit"),
    ],
)
def test_configuration_ignores_option(option: str) -> None:
    """Test the options that are accepted but never stored."""
    configuration = MarketplaceConfiguration()

    configuration.update_from_dict({option: True})

    assert not hasattr(configuration, option)


@pytest.mark.parametrize(
    ("option", "default"),
    [
        pytest.param("plugin_path", "www/community/", id="plugin_path"),
        pytest.param("theme_path", "themes/", id="theme_path"),
    ],
)
def test_configuration_keeps_its_paths(option: str, default: str) -> None:
    """Test the paths downloads go to can not be changed from entry data."""
    configuration = MarketplaceConfiguration()

    configuration.update_from_dict({option: "somewhere/else/"})

    assert getattr(configuration, option) == default


def test_configuration_rejects_non_dict() -> None:
    """Test updating from something that is not a dict."""
    configuration = MarketplaceConfiguration()

    with pytest.raises(MarketplaceError):
        configuration.update_from_dict(None)


@pytest.mark.usefixtures("init_integration")
async def test_repository_lookups(
    marketplace: MarketplaceManager, mock_repository: Repository
) -> None:
    """Test looking a repository up by id and by name."""
    marketplace.repositories = Repositories()
    assert marketplace.repositories.get_by_id(None) is None
    assert marketplace.repositories.get_by_full_name(None) is None

    mock_repository.data.id = "1337"
    mock_repository.data.category = RepositoryCategory.INTEGRATION
    mock_repository.data.installed = True
    marketplace.repositories.register(mock_repository)

    assert marketplace.repositories.get_by_id("1337").data.full_name == "test/test"
    assert marketplace.repositories.get_by_full_name("test/test").data.id == "1337"
    assert marketplace.repositories.is_registered(repository_id="1337")
    assert marketplace.repositories.is_downloaded(repository_id="1337")


@pytest.mark.usefixtures("init_integration")
async def test_category_downloaded(
    marketplace: MarketplaceManager, mock_repository: Repository
) -> None:
    """Test only the category of a downloaded repository counts as downloaded."""
    marketplace.repositories = Repositories()
    mock_repository.data.id = "1337"
    mock_repository.data.category = RepositoryCategory.INTEGRATION
    mock_repository.data.installed = True
    marketplace.repositories.register(mock_repository)

    assert marketplace.repositories.category_downloaded(RepositoryCategory.INTEGRATION)
    assert not marketplace.repositories.category_downloaded(RepositoryCategory.THEME)


@pytest.mark.usefixtures("init_integration")
async def test_repository_id_is_set_once(
    marketplace: MarketplaceManager, mock_repository: Repository
) -> None:
    """Test a repository id can be set once and then never changes."""
    mock_repository.data.id = "0"
    marketplace.repositories.register(mock_repository)

    marketplace.repositories.set_repository_id(mock_repository, "42")

    with pytest.raises(ValueError):
        marketplace.repositories.set_repository_id(mock_repository, "30")

    # Setting the same id again is fine
    marketplace.repositories.set_repository_id(mock_repository, "42")

    assert marketplace.repositories.get_by_full_name("test/test") is mock_repository
    assert marketplace.repositories.get_by_id("42") is mock_repository


@pytest.mark.usefixtures("init_integration")
async def test_unregister_repository(
    marketplace: MarketplaceManager, mock_repository: Repository
) -> None:
    """Test unregistering a repository twice does not raise."""
    mock_repository.data.id = "42"
    marketplace.repositories.register(mock_repository)

    marketplace.repositories.unregister(mock_repository)
    assert marketplace.repositories.get_by_full_name("test/test") is None
    assert marketplace.repositories.get_by_id("42") is None

    marketplace.repositories.unregister(mock_repository)


@pytest.mark.usefixtures("init_integration")
async def test_active_categories(marketplace: MarketplaceManager) -> None:
    """Test which categories are active for the default options."""
    assert marketplace.common.categories == DEFAULT_CATEGORIES | {
        RepositoryCategory.THEME,
    }


async def test_catalog_restores_versions_of_repositories_not_installed(
    marketplace: MarketplaceManager,
) -> None:
    """Test an unchanged feed still sets the versions storage does not keep."""
    repository = marketplace.repositories.get_by_full_name(REPOSITORY_PLUGIN)
    assert not repository.data.installed
    last_version = repository.data.last_version
    last_commit = repository.data.last_commit
    assert last_version or last_commit

    # Restored from storage: same fetch time as the feed, but no versions
    repository.data.last_version = None
    repository.data.last_commit = None

    await marketplace.async_get_category_repositories_from_catalog(
        RepositoryCategory.PLUGIN
    )

    assert repository.data.last_version == last_version
    assert repository.data.last_commit == last_commit


async def test_catalog_keeps_the_domain_of_a_downloaded_integration(
    marketplace: MarketplaceManager,
) -> None:
    """Test the feed can not point a downloaded integration at another directory."""
    repository = marketplace.repositories.get_by_full_name(REPOSITORY_INTEGRATION)
    repository.data.installed = True
    repository.data.domain = "example"

    feed = {
        repository.data.id: {
            "domain": "other",
            "full_name": repository.data.full_name,
            "last_fetched": repository.data.last_fetched.timestamp() + 1,
            "manifest": {},
            "manifest_name": "Example",
        }
    }
    with patch.object(marketplace.data_client, "get_data", return_value=feed):
        await marketplace.async_get_category_repositories_from_catalog(
            RepositoryCategory.INTEGRATION
        )

    assert repository.data.manifest_name == "Example"
    assert repository.data.domain == "example"


async def test_custom_repository_listed_by_the_catalog_is_default(
    marketplace: MarketplaceManager,
) -> None:
    """Test a custom repository the catalog starts listing stops being custom."""
    repository = marketplace.repositories.get_by_full_name(REPOSITORY_INTEGRATION)
    repository_id = str(repository.data.id)

    # Added by hand before the catalog listed it
    marketplace.repositories._default_repositories.discard(repository_id)
    assert not marketplace.repositories.is_default(repository_id)

    await marketplace.async_get_category_repositories_from_catalog(
        RepositoryCategory.INTEGRATION
    )

    assert marketplace.repositories.is_default(repository_id)
    assert (
        marketplace.repositories.get_by_full_name(REPOSITORY_INTEGRATION) is repository
    )
