"""Fixtures for Met Office Weather Warnings tests."""

from collections.abc import Generator
from unittest.mock import patch

import pytest

from homeassistant.components.metoffice_warnings.const import CONF_REGION, DOMAIN

from tests.common import MockConfigEntry, load_fixture
from tests.test_util.aiohttp import AiohttpClientMocker

TEST_REGION = "sw"
TEST_URL = f"https://weather.metoffice.gov.uk/public/data/PWSCache/WarningsRSS/Region/{TEST_REGION}"


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id=TEST_REGION,
        title="South West England",
        data={CONF_REGION: TEST_REGION},
    )


@pytest.fixture
def mock_warnings_response(aioclient_mock: AiohttpClientMocker) -> AiohttpClientMocker:
    """Mock a response with one warning."""
    aioclient_mock.get(
        TEST_URL,
        text=load_fixture("warnings.xml", DOMAIN),
    )
    return aioclient_mock


@pytest.fixture
def mock_multiple_warnings_response(
    aioclient_mock: AiohttpClientMocker,
) -> AiohttpClientMocker:
    """Mock a response with multiple warnings."""
    aioclient_mock.get(
        TEST_URL,
        text=load_fixture("multiple_warnings.xml", DOMAIN),
    )
    return aioclient_mock


@pytest.fixture
def mock_no_warnings_response(
    aioclient_mock: AiohttpClientMocker,
) -> AiohttpClientMocker:
    """Mock a response with no warnings."""
    aioclient_mock.get(
        TEST_URL,
        text=load_fixture("no_warnings.xml", DOMAIN),
    )
    return aioclient_mock


@pytest.fixture
def mock_no_channel_response(
    aioclient_mock: AiohttpClientMocker,
) -> AiohttpClientMocker:
    """Mock a response with valid XML but no channel element."""
    aioclient_mock.get(
        TEST_URL,
        text=load_fixture("no_channel.xml", DOMAIN),
    )
    return aioclient_mock


@pytest.fixture
def mock_edge_cases_response(
    aioclient_mock: AiohttpClientMocker,
) -> AiohttpClientMocker:
    """Mock a response with edge-case warnings."""
    aioclient_mock.get(
        TEST_URL,
        text=load_fixture("warning_edge_cases.xml", DOMAIN),
    )
    return aioclient_mock


@pytest.fixture
def mock_setup_entry() -> Generator[None]:
    """Mock async_setup_entry."""
    with patch(
        "homeassistant.components.metoffice_warnings.async_setup_entry",
        return_value=True,
    ):
        yield
