"""Common fixtures for the Route53 tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.route53.const import (
    CONF_ACCESS_KEY_ID,
    CONF_RECORDS,
    CONF_SECRET_ACCESS_KEY,
    DEFAULT_TTL,
    DOMAIN,
)
from homeassistant.components.route53.helpers import IPIFY_URL
from homeassistant.const import CONF_DOMAIN, CONF_TTL, CONF_ZONE

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker

OK_RESPONSE = {"ResponseMetadata": {"HTTPStatusCode": 200}}


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.route53.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a Route53 config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="example.com",
        unique_id="test-zone_example.com",
        data={
            CONF_ACCESS_KEY_ID: "test-key",
            CONF_SECRET_ACCESS_KEY: "test-secret",
            CONF_ZONE: "test-zone",
            CONF_DOMAIN: "example.com",
            CONF_RECORDS: ["test1"],
            CONF_TTL: DEFAULT_TTL,
        },
    )


@pytest.fixture
def mock_boto3_client() -> Generator[MagicMock]:
    """Mock the boto3 client used by the config flow and the updater."""
    client = MagicMock()
    client.get_hosted_zone.return_value = {
        "HostedZone": {"Id": "/hostedzone/test-zone"}
    }
    client.change_resource_record_sets.return_value = OK_RESPONSE
    with (
        patch(
            "homeassistant.components.route53.config_flow.boto3.client",
            return_value=client,
        ),
        patch(
            "homeassistant.components.route53.helpers.boto3.client",
            return_value=client,
        ),
    ):
        yield client


@pytest.fixture
def mock_ipify(aioclient_mock: AiohttpClientMocker) -> AiohttpClientMocker:
    """Return a public IP address from the ipify service."""
    aioclient_mock.get(IPIFY_URL, text="1.2.3.4")
    return aioclient_mock
