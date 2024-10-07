"""Configure tests for the LGThinQ integration."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from thinqconnect import ThinQAPIException

from homeassistant.components.lg_thinq.const import CONF_CONNECT_CLIENT_ID, DOMAIN
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_COUNTRY

from .const import MOCK_CONNECT_CLIENT_ID, MOCK_COUNTRY, MOCK_PAT, MOCK_UUID

from tests.common import MockConfigEntry


def mock_thinq_api_response(
    *,
    status: int = 200,
    body: dict | None = None,
    error_code: str | None = None,
    error_message: str | None = None,
) -> MagicMock:
    """Create a mock thinq api response."""
    response = MagicMock()
    response.status = status
    response.body = body
    response.error_code = error_code
    response.error_message = error_message
    return response


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Create a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title=f"Test {DOMAIN}",
        unique_id=MOCK_PAT,
        data={
            CONF_ACCESS_TOKEN: MOCK_PAT,
            CONF_CONNECT_CLIENT_ID: MOCK_CONNECT_CLIENT_ID,
            CONF_COUNTRY: MOCK_COUNTRY,
        },
    )


@pytest.fixture
def mock_uuid() -> Generator[AsyncMock]:
    """Mock a uuid."""
    with (
        patch("uuid.uuid4", autospec=True, return_value=MOCK_UUID) as mock_uuid,
        patch(
            "homeassistant.components.lg_thinq.config_flow.uuid.uuid4",
            new=mock_uuid,
        ),
    ):
        yield mock_uuid.return_value


@pytest.fixture
def mock_thinq_api() -> Generator[AsyncMock]:
    """Mock a thinq api."""
    with (
        patch("thinqconnect.ThinQApi", autospec=True) as mock_api,
        patch(
            "homeassistant.components.lg_thinq.config_flow.ThinQApi",
            new=mock_api,
        ),
    ):
        thinq_api = mock_api.return_value
        thinq_api.async_get_device_list = AsyncMock(
            return_value=mock_thinq_api_response(status=200, body={})
        )
        yield thinq_api


@pytest.fixture
def mock_invalid_thinq_api(mock_thinq_api: AsyncMock) -> AsyncMock:
    """Mock an invalid thinq api."""
    mock_thinq_api.async_get_device_list = AsyncMock(
        side_effect=ThinQAPIException(
            code="1309", message="Not allowed api call", headers=None
        )
    )
    return mock_thinq_api
