"""Common fixtures for the Route53 tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.route53.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_boto3_client() -> Generator[MagicMock]:
    """Mock boto3 client."""
    with patch(
        "homeassistant.components.route53.config_flow.boto3.client"
    ) as mock_client:
        mock_client.return_value.get_hosted_zone.return_value = True
        mock_client.return_value.change_resource_record_sets.return_value = {
            "ResponseMetadata": {"HTTPStatusCode": 200}
        }
        yield mock_client
