"""Fixtures for component testing."""

from __future__ import annotations

from collections.abc import Callable, Generator
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock, patch

import pytest

from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant

if TYPE_CHECKING:
    from .conversation import MockAgent
    from .device_tracker.common import MockScanner
    from .light.common import MockLight
    from .sensor.common import MockSensor
    from .switch.common import MockSwitch


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


@pytest.fixture(name="mock_conversation_agent")
def mock_conversation_agent_fixture(hass: HomeAssistant) -> MockAgent:
    """Mock a conversation agent."""
    from tests.components.conversation.common import (
        mock_conversation_agent_fixture_helper,
    )

    return mock_conversation_agent_fixture_helper(hass)


@pytest.fixture(scope="session", autouse=True)
def prevent_ffmpeg_subprocess() -> Generator[None, None, None]:
    """Prevent ffmpeg from creating a subprocess."""
    with patch(
        "homeassistant.components.ffmpeg.FFVersion.get_version", return_value="6.0"
    ):
        yield


@pytest.fixture
def mock_light_entities() -> list[MockLight]:
    """Return mocked light entities."""
    from tests.components.light.common import MockLight

    return [
        MockLight("Ceiling", STATE_ON),
        MockLight("Ceiling", STATE_OFF),
        MockLight(None, STATE_OFF),
    ]


@pytest.fixture
def mock_sensor_entities() -> dict[str, MockSensor]:
    """Return mocked sensor entities."""
    from tests.components.sensor.common import get_mock_sensor_entities

    return get_mock_sensor_entities()


@pytest.fixture
def mock_switch_entities() -> list[MockSwitch]:
    """Return mocked toggle entities."""
    from tests.components.switch.common import get_mock_switch_entities

    return get_mock_switch_entities()


@pytest.fixture
def mock_legacy_device_scanner() -> MockScanner:
    """Return mocked legacy device scanner entity."""
    from tests.components.device_tracker.common import MockScanner

    return MockScanner()


@pytest.fixture
def mock_legacy_device_tracker_setup() -> Callable[[HomeAssistant, MockScanner], None]:
    """Return setup callable for legacy device tracker setup."""
    from tests.components.device_tracker.common import mock_legacy_device_tracker_setup

    return mock_legacy_device_tracker_setup
