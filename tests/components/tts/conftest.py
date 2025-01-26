"""Conftest for TTS tests.

From http://doc.pytest.org/en/latest/example/simple.html#making-test-result-information-available-in-fixtures
"""

from collections.abc import Generator, Iterable
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from homeassistant.config_entries import ConfigFlow
from homeassistant.core import HomeAssistant
from homeassistant.core_config import async_process_ha_core_config

from .common import (
    DEFAULT_LANG,
    TEST_DOMAIN,
    MockTTS,
    MockTTSEntity,
    MockTTSProvider,
    mock_config_entry_setup,
    mock_setup,
)

from tests.common import MockModule, mock_config_flow, mock_integration, mock_platform


@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """Add test report to node."""
    # execute all other hooks to obtain the report object
    outcome = yield
    rep = outcome.get_result()

    # set a report attribute for each phase of a call, which can
    # be "setup", "call", "teardown"
    setattr(item, f"rep_{rep.when}", rep)


@pytest.fixture(autouse=True, name="mock_tts_cache_dir")
def mock_tts_cache_dir_fixture_autouse(mock_tts_cache_dir: Path) -> Path:
    """Mock the TTS cache dir with empty dir."""
    return mock_tts_cache_dir


@pytest.fixture(autouse=True)
def tts_mutagen_mock_fixture_autouse(tts_mutagen_mock: MagicMock) -> None:
    """Mock writing tags."""


@pytest.fixture(autouse=True)
async def internal_url_mock(hass: HomeAssistant) -> None:
    """Mock internal URL of the instance."""
    await async_process_ha_core_config(
        hass,
        {"internal_url": "http://example.local:8123"},
    )


@pytest.fixture
async def mock_tts(hass: HomeAssistant, mock_provider) -> None:
    """Mock TTS."""
    mock_integration(hass, MockModule(domain="test"))
    mock_platform(hass, "test.tts", MockTTS(mock_provider))


@pytest.fixture
def mock_provider() -> MockTTSProvider:
    """Test TTS provider."""
    return MockTTSProvider(DEFAULT_LANG)


@pytest.fixture
def mock_tts_entity() -> MockTTSEntity:
    """Test TTS entity."""
    return MockTTSEntity(DEFAULT_LANG)


class TTSFlow(ConfigFlow):
    """Test flow."""


@pytest.fixture(name="config_flow_test_domains")
def config_flow_test_domain_fixture() -> Iterable[str]:
    """Test domain fixture."""
    return (TEST_DOMAIN,)


@pytest.fixture(autouse=True)
def config_flow_fixture(
    hass: HomeAssistant, config_flow_test_domains: Iterable[str]
) -> Generator[None]:
    """Mock config flow."""
    for domain in config_flow_test_domains:
        mock_platform(hass, f"{domain}.config_flow")

    with ExitStack() as stack:
        for domain in config_flow_test_domains:
            stack.enter_context(mock_config_flow(domain, TTSFlow))
        yield


@pytest.fixture(name="setup")
async def setup_fixture(
    hass: HomeAssistant,
    request: pytest.FixtureRequest,
    mock_provider: MockTTSProvider,
    mock_tts_entity: MockTTSEntity,
) -> None:
    """Set up the test environment."""
    if request.param == "mock_setup":
        await mock_setup(hass, mock_provider)
    elif request.param == "mock_config_entry_setup":
        await mock_config_entry_setup(hass, mock_tts_entity)
    else:
        raise RuntimeError("Invalid setup fixture")
