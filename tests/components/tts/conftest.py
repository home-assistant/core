"""Conftest for TTS tests.

From http://doc.pytest.org/en/latest/example/simple.html#making-test-result-information-available-in-fixtures
"""
from unittest.mock import patch

import pytest

from homeassistant.components.tts import _get_cache_files


@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """Add test report to node."""
    # execute all other hooks to obtain the report object
    outcome = yield
    rep = outcome.get_result()

    # set a report attribute for each phase of a call, which can
    # be "setup", "call", "teardown"
    setattr(item, f"rep_{rep.when}", rep)


@pytest.fixture(autouse=True)
def mock_get_cache_files():
    """Mock the list TTS cache function."""
    with patch(
        "homeassistant.components.tts._get_cache_files", return_value={}
    ) as mock_cache_files:
        yield mock_cache_files


@pytest.fixture(autouse=True)
def mock_init_cache_dir():
    """Mock the TTS cache dir in memory."""
    with patch(
        "homeassistant.components.tts._init_tts_cache_dir",
        side_effect=lambda hass, cache_dir: hass.config.path(cache_dir),
    ) as mock_cache_dir:
        yield mock_cache_dir


@pytest.fixture
def empty_cache_dir(tmp_path, mock_init_cache_dir, mock_get_cache_files, request):
    """Mock the TTS cache dir with empty dir."""
    mock_init_cache_dir.side_effect = None
    mock_init_cache_dir.return_value = str(tmp_path)

    # Restore original get cache files behavior, we're working with a real dir.
    mock_get_cache_files.side_effect = _get_cache_files

    yield tmp_path

    if request.node.rep_call.passed:
        return

    # Print contents of dir if failed
    print("Content of dir for", request.node.nodeid)  # noqa: T201
    for fil in tmp_path.iterdir():
        print(fil.relative_to(tmp_path))  # noqa: T201

    # To show the log.
    pytest.fail("Test failed, see log for details")


@pytest.fixture(autouse=True)
def mutagen_mock():
    """Mock writing tags."""
    with patch(
        "homeassistant.components.tts.SpeechManager.write_tags",
        side_effect=lambda *args: args[1],
    ) as mock_write_tags:
        yield mock_write_tags
