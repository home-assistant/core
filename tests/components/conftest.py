"""Fixtures for component testing."""

from collections.abc import Callable, Generator
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock, patch

import pytest

from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from tests.common import MockEntity, MockPlatform, mock_platform

if TYPE_CHECKING:
    from tests.components.light.common import MockLight, SetupLightPlatformCallable


@pytest.fixture(scope="session", autouse=True)
def patch_zeroconf_multiple_catcher() -> Generator[None, None, None]:
    """Patch zeroconf wrapper that detects if multiple instances are used."""
    with patch(
        "homeassistant.components.zeroconf.install_multiple_zeroconf_catcher",
        side_effect=lambda zc: None,
    ):
        yield


@pytest.fixture(scope="session", autouse=True)
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


# Blueprint test fixtures
@pytest.fixture(name="stub_blueprint_populate")
def stub_blueprint_populate_fixture() -> Generator[None, Any, None]:
    """Stub copying the blueprints to the config folder."""
    from tests.components.blueprint.common import stub_blueprint_populate_fixture_helper

    yield from stub_blueprint_populate_fixture_helper()


# TTS test fixtures
@pytest.fixture(name="mock_tts_get_cache_files")
def mock_tts_get_cache_files_fixture():
    """Mock the list TTS cache function."""
    from tests.components.tts.common import mock_tts_get_cache_files_fixture_helper

    yield from mock_tts_get_cache_files_fixture_helper()


@pytest.fixture(name="mock_tts_init_cache_dir")
def mock_tts_init_cache_dir_fixture(
    init_tts_cache_dir_side_effect: Any,
) -> Generator[MagicMock, None, None]:
    """Mock the TTS cache dir in memory."""
    from tests.components.tts.common import mock_tts_init_cache_dir_fixture_helper

    yield from mock_tts_init_cache_dir_fixture_helper(init_tts_cache_dir_side_effect)


@pytest.fixture(name="init_tts_cache_dir_side_effect")
def init_tts_cache_dir_side_effect_fixture() -> Any:
    """Return the cache dir."""
    from tests.components.tts.common import (
        init_tts_cache_dir_side_effect_fixture_helper,
    )

    return init_tts_cache_dir_side_effect_fixture_helper()


@pytest.fixture(name="mock_tts_cache_dir")
def mock_tts_cache_dir_fixture(
    tmp_path, mock_tts_init_cache_dir, mock_tts_get_cache_files, request
):
    """Mock the TTS cache dir with empty dir."""
    from tests.components.tts.common import mock_tts_cache_dir_fixture_helper

    yield from mock_tts_cache_dir_fixture_helper(
        tmp_path, mock_tts_init_cache_dir, mock_tts_get_cache_files, request
    )


@pytest.fixture(name="tts_mutagen_mock")
def tts_mutagen_mock_fixture():
    """Mock writing tags."""
    from tests.components.tts.common import tts_mutagen_mock_fixture_helper

    yield from tts_mutagen_mock_fixture_helper()


@pytest.fixture(scope="session", autouse=True)
def prevent_ffmpeg_subprocess() -> Generator[None, None, None]:
    """Prevent ffmpeg from creating a subprocess."""
    with patch(
        "homeassistant.components.ffmpeg.FFVersion.get_version", return_value="6.0"
    ):
        yield


@pytest.fixture
def mock_light_entities() -> list["MockLight"]:
    """Return mocked light entities."""
    from tests.components.light.common import MockLight

    return [
        MockLight("Ceiling", STATE_ON),
        MockLight("Ceiling", STATE_OFF),
        MockLight(None, STATE_OFF),
    ]


@pytest.fixture
def setup_light_platform() -> "SetupLightPlatformCallable":
    """Return a callable to set up the mock light entity component."""
    from tests.components.light.common import setup_light_platform

    return setup_light_platform


SetupEntityPlatformCallable = Callable[
    [HomeAssistant, str, list[MockEntity], bool | None], MockPlatform
]


@pytest.fixture
async def setup_entity_platform() -> SetupEntityPlatformCallable:
    """Mock the entity platform for tests."""

    def _setup(
        hass: HomeAssistant,
        domain: str,
        entities: list[MockEntity],
        from_config_entry: bool | None = None,
    ) -> MockPlatform:
        """Set up entity test platform."""

        async def _async_setup_platform(
            hass: HomeAssistant,
            config: ConfigType,
            async_add_entities: AddEntitiesCallback,
            discovery_info: DiscoveryInfoType | None = None,
        ) -> None:
            """Set up entity test platform."""
            async_add_entities(entities)

        platform = MockPlatform(
            async_setup_platform=_async_setup_platform,
        )

        # avoid loading config_entry if not needed
        if from_config_entry:
            from homeassistant.config_entries import ConfigEntry

            async def _async_setup_entry(
                hass: HomeAssistant,
                entry: ConfigEntry,
                async_add_entities: AddEntitiesCallback,
            ) -> None:
                """Set up entity test platform."""
                async_add_entities(entities)

            platform.async_setup_entry = _async_setup_entry
            platform.async_setup_platform = None

        mock_platform(
            hass,
            f"test.{domain}",
            platform,
        )
        return platform

    return _setup
