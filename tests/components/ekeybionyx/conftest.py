"""Conftest module for ekeybionyx."""

from http import HTTPStatus
from unittest.mock import patch

import pytest

from tests.test_util.aiohttp import AiohttpClientMocker


@pytest.fixture(name="system")
def mock_systems(
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Fixture to setup fake requests made to Fitbit API during config flow."""
    aioclient_mock.request(
        "GET",
        "https://api.bionyx.io/3rd-party/api/systems",
        status=HTTPStatus.OK,
        json=[
            {
                "systemName": "A simple string containing 0 to 128 word, space and punctuation characters.",
                "systemId": "946DA01F-9ABD-4D9D-80C7-02AF85C822A8",
                "ownSystem": True,
                "functionWebhookQuotas": {"free": 1, "used": 0},
            },
            {
                "systemName": "A simple string containing 0 to 128 word, space and punctuation characters.",
                "systemId": "946DA01F-9ABD-4D9D-80C7-02AF85C822A9",
                "ownSystem": True,
                "functionWebhookQuotas": {"free": 1, "used": 0},
            },
        ],
    )


@pytest.fixture(name="no_own_system")
def mock_no_own_systems(
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Fixture to setup fake requests made to Fitbit API during config flow."""
    aioclient_mock.request(
        "GET",
        "https://api.bionyx.io/3rd-party/api/systems",
        status=HTTPStatus.OK,
        json=[
            {
                "systemName": "A simple string containing 0 to 128 word, space and punctuation characters.",
                "systemId": "946DA01F-9ABD-4D9D-80C7-02AF85C822A8",
                "ownSystem": False,
                "functionWebhookQuotas": {"free": 1, "used": 0},
            }
        ],
    )


@pytest.fixture(name="add_webhook", autouse=True)
def mock_add_webhook(
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Fixture to setup fake requests made to Fitbit API during config flow."""
    aioclient_mock.request(
        "POST",
        "https://api.bionyx.io/3rd-party/api/systems/946DA01F-9ABD-4D9D-80C7-02AF85C822A8/function-webhooks",
        status=HTTPStatus.CREATED,
        json={
            "functionWebhookId": "946DA01F-9ABD-4D9D-80C7-02AF85C822A8",
            "integrationName": "Home Assistant",
            "locationName": "Home Assistant",
            "functionName": "Test",
            "expiresAt": "2022-05-16T04:11:28.0000000+00:00",
            "modificationState": None,
        },
    )


@pytest.fixture(name="webhook_id")
def mock_webhook_id():
    """Mock webhook_id."""
    with patch(
        "homeassistant.components.webhook.async_generate_id", return_value="1234567890"
    ):
        yield
