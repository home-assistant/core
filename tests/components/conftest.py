"""Fixtures for component testing."""
from collections.abc import Generator
from unittest.mock import patch

import pytest

from tests.components.tts.conftest import (  # noqa: F401, pylint: disable=unused-import
    init_tts_cache_dir_side_effect_fixture,
    mock_tts_cache_dir_fixture,
    mock_tts_get_cache_files_fixture,
    mock_tts_init_cache_dir_fixture,
    tts_mutagen_mock_fixture,
)


@pytest.fixture(scope="session", autouse=True)
def patch_zeroconf_multiple_catcher() -> Generator[None, None, None]:
    """Patch zeroconf wrapper that detects if multiple instances are used."""
    with patch(
        "homeassistant.components.zeroconf.install_multiple_zeroconf_catcher",
        side_effect=lambda zc: None,
    ):
        yield


@pytest.fixture(autouse=True)
def prevent_io() -> Generator[None, None, None]:
    """Fixture to prevent certain I/O from happening."""
    with patch(
        "homeassistant.components.http.ban.load_yaml_config_file",
    ):
        yield


@pytest.fixture
def entity_registry_enabled_by_default() -> Generator[None, None, None]:
    """Test fixture that ensures all entities are enabled in the registry."""
    with patch(
        "homeassistant.helpers.entity.Entity.entity_registry_enabled_default",
        return_value=True,
    ):
        yield
