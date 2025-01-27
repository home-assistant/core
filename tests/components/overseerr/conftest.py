"""Overseerr tests configuration."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest
from python_overseerr import MovieDetails, RequestCount, RequestResponse
from python_overseerr.models import TVDetails, WebhookNotificationConfig

from homeassistant.components.overseerr import CONF_CLOUDHOOK_URL
from homeassistant.components.overseerr.const import DOMAIN
from homeassistant.const import (
    CONF_API_KEY,
    CONF_HOST,
    CONF_PORT,
    CONF_SSL,
    CONF_WEBHOOK_ID,
)

from .const import WEBHOOK_ID

from tests.common import MockConfigEntry, load_fixture


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.overseerr.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_overseerr_client() -> Generator[AsyncMock]:
    """Mock an Overseerr client."""
    with (
        patch(
            "homeassistant.components.overseerr.coordinator.OverseerrClient",
            autospec=True,
        ) as mock_client,
        patch(
            "homeassistant.components.overseerr.config_flow.OverseerrClient",
            new=mock_client,
        ),
    ):
        client = mock_client.return_value
        client.get_request_count.return_value = RequestCount.from_json(
            load_fixture("request_count.json", DOMAIN)
        )
        client.get_webhook_notification_config.return_value = (
            WebhookNotificationConfig.from_json(
                load_fixture("webhook_config.json", DOMAIN)
            )
        )
        client.test_webhook_notification_config.return_value = True
        client.get_requests.return_value = RequestResponse.from_json(
            load_fixture("requests.json", DOMAIN)
        ).results
        client.get_movie_details.return_value = MovieDetails.from_json(
            load_fixture("movie.json", DOMAIN)
        )
        client.get_tv_details.return_value = TVDetails.from_json(
            load_fixture("tv.json", DOMAIN)
        )
        yield client


@pytest.fixture
def mock_overseerr_client_needs_change(
    mock_overseerr_client: AsyncMock,
) -> Generator[AsyncMock]:
    """Mock an Overseerr client."""
    mock_overseerr_client.get_webhook_notification_config.return_value.types = 0
    return mock_overseerr_client


@pytest.fixture
def mock_overseerr_client_cloudhook(
    mock_overseerr_client: AsyncMock,
) -> Generator[AsyncMock]:
    """Mock an Overseerr client."""
    mock_overseerr_client.get_webhook_notification_config.return_value.options.webhook_url = "https://hooks.nabu.casa/ABCD"
    return mock_overseerr_client


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Mock a config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Overseerr",
        data={
            CONF_HOST: "overseerr.test",
            CONF_PORT: 80,
            CONF_SSL: False,
            CONF_API_KEY: "test-key",
            CONF_WEBHOOK_ID: WEBHOOK_ID,
        },
        entry_id="01JG00V55WEVTJ0CJHM0GAD7PC",
    )


@pytest.fixture
def mock_cloudhook_config_entry() -> MockConfigEntry:
    """Mock a config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Overseerr",
        data={
            CONF_HOST: "overseerr.test",
            CONF_PORT: 80,
            CONF_SSL: False,
            CONF_API_KEY: "test-key",
            CONF_WEBHOOK_ID: WEBHOOK_ID,
            CONF_CLOUDHOOK_URL: "https://hooks.nabu.casa/ABCD",
        },
        entry_id="01JG00V55WEVTJ0CJHM0GAD7PC",
    )
