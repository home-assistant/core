"""Tests for the Community store base object."""

import pytest

from homeassistant.components.store.base import (
    Repositories,
    StoreConfiguration,
    StoreManager,
)
from homeassistant.components.store.enums import RepositoryCategory
from homeassistant.components.store.exceptions import StoreError
from homeassistant.components.store.repositories.base import Repository

from .const import DEFAULT_CATEGORIES


def test_configuration_defaults() -> None:
    """Test the configuration defaults and what a dict can set."""
    configuration = StoreConfiguration()
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
    configuration = StoreConfiguration()

    configuration.update_from_dict({option: True})

    assert not hasattr(configuration, option)


def test_configuration_rejects_non_dict() -> None:
    """Test updating from something that is not a dict."""
    configuration = StoreConfiguration()

    with pytest.raises(StoreError):
        configuration.update_from_dict(None)


@pytest.mark.usefixtures("init_integration")
async def test_repository_lookups(
    store: StoreManager, mock_repository: Repository
) -> None:
    """Test looking a repository up by id and by name."""
    store.repositories = Repositories()
    assert store.repositories.get_by_id(None) is None
    assert store.repositories.get_by_full_name(None) is None

    mock_repository.data.id = "1337"
    mock_repository.data.category = RepositoryCategory.INTEGRATION
    mock_repository.data.installed = True
    store.repositories.register(mock_repository)

    assert store.repositories.get_by_id("1337").data.full_name == "test/test"
    assert store.repositories.get_by_full_name("test/test").data.id == "1337"
    assert store.repositories.is_registered(repository_id="1337")
    assert store.repositories.is_downloaded(repository_id="1337")


@pytest.mark.usefixtures("init_integration")
async def test_category_downloaded(
    store: StoreManager, mock_repository: Repository
) -> None:
    """Test only the category of a downloaded repository counts as downloaded."""
    store.repositories = Repositories()
    mock_repository.data.id = "1337"
    mock_repository.data.category = RepositoryCategory.INTEGRATION
    mock_repository.data.installed = True
    store.repositories.register(mock_repository)

    assert store.repositories.category_downloaded(RepositoryCategory.INTEGRATION)
    assert not store.repositories.category_downloaded(RepositoryCategory.THEME)


@pytest.mark.usefixtures("init_integration")
async def test_repository_id_is_set_once(
    store: StoreManager, mock_repository: Repository
) -> None:
    """Test a repository id can be set once and then never changes."""
    mock_repository.data.id = "0"
    store.repositories.register(mock_repository)

    store.repositories.set_repository_id(mock_repository, "42")

    with pytest.raises(ValueError):
        store.repositories.set_repository_id(mock_repository, "30")

    # Setting the same id again is fine
    store.repositories.set_repository_id(mock_repository, "42")

    assert store.repositories.get_by_full_name("test/test") is mock_repository
    assert store.repositories.get_by_id("42") is mock_repository


@pytest.mark.usefixtures("init_integration")
async def test_unregister_repository(
    store: StoreManager, mock_repository: Repository
) -> None:
    """Test unregistering a repository twice does not raise."""
    mock_repository.data.id = "42"
    store.repositories.register(mock_repository)

    store.repositories.unregister(mock_repository)
    assert store.repositories.get_by_full_name("test/test") is None
    assert store.repositories.get_by_id("42") is None

    store.repositories.unregister(mock_repository)


@pytest.mark.usefixtures("init_integration")
async def test_active_categories(store: StoreManager) -> None:
    """Test which categories are active for the default options."""
    assert store.common.categories == DEFAULT_CATEGORIES | {
        RepositoryCategory.APPDAEMON,
        RepositoryCategory.THEME,
    }
