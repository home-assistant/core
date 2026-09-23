"""Tests for the Marketplace base object."""

import pytest

from homeassistant.components.marketplace.base import (
    MarketplaceConfiguration,
    MarketplaceManager,
    Repositories,
)
from homeassistant.components.marketplace.enums import RepositoryCategory
from homeassistant.components.marketplace.exceptions import MarketplaceError
from homeassistant.components.marketplace.repositories.base import Repository

from .const import DEFAULT_CATEGORIES


def test_configuration_defaults() -> None:
    """Test the configuration defaults and what a dict can set."""
    configuration = MarketplaceConfiguration()
    configuration.update_from_dict({"token": "xxxxxxxxxx"})

    assert isinstance(configuration.to_json(), dict)
    assert configuration.token == "xxxxxxxxxx"
    assert configuration.appdaemon is False
    assert configuration.python_script is False
    assert configuration.theme is False
    assert configuration.country == "ALL"
    assert configuration.release_limit == 5


@pytest.mark.parametrize(
    "option",
    [
        pytest.param("experimental", id="experimental"),
        pytest.param("netdaemon", id="netdaemon"),
    ],
)
def test_configuration_ignores_option(option: str) -> None:
    """Test the options that are accepted but never stored."""
    configuration = MarketplaceConfiguration()

    configuration.update_from_dict({option: True})

    assert not hasattr(configuration, option)


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
        RepositoryCategory.APPDAEMON,
        RepositoryCategory.THEME,
    }
