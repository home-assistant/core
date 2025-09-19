"""Conftest module for ekeybionyx."""

from http import HTTPStatus
from unittest.mock import patch

import pytest

from homeassistant.components.ekeybionyx.const import DOMAIN
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker


def dummy_systems(
    num_systems: int, free_wh: int, used_wh: int, own_system: bool = True
) -> list[dict]:
    """Create dummy systems."""
    return [
        {
            "systemName": f"System {i + 1}",
            "systemId": f"946DA01F-9ABD-4D9D-80C7-02AF85C822A{i + 8}",
            "ownSystem": own_system,
            "functionWebhookQuotas": {"free": free_wh, "used": used_wh},
        }
        for i in range(num_systems)
    ]


@pytest.fixture(name="system")
def mock_systems(
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Fixture to setup fake requests made to Ekey Bionyx API during config flow."""
    aioclient_mock.get(
        "https://api.bionyx.io/3rd-party/api/systems",
        json=dummy_systems(2, 5, 0),
    )


@pytest.fixture(name="no_own_system")
def mock_no_own_systems(
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Fixture to setup fake requests made to Ekey Bionyx API during config flow."""
    aioclient_mock.get(
        "https://api.bionyx.io/3rd-party/api/systems",
        json=dummy_systems(1, 1, 0, False),
    )


@pytest.fixture(name="no_response")
def mock_no_response(
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Fixture to setup fake requests made to Ekey Bionyx API during config flow."""
    aioclient_mock.get(
        "https://api.bionyx.io/3rd-party/api/systems",
        status=HTTPStatus.INTERNAL_SERVER_ERROR,
    )


@pytest.fixture(name="no_available_webhooks")
def mock_no_available_webhooks(
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Fixture to setup fake requests made to Ekey Bionyx API during config flow."""
    aioclient_mock.get(
        "https://api.bionyx.io/3rd-party/api/systems",
        json=dummy_systems(1, 0, 0),
    )


@pytest.fixture(name="already_set_up")
def mock_already_set_up(
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Fixture to setup fake requests made to Ekey Bionyx API during config flow."""
    aioclient_mock.get(
        "https://api.bionyx.io/3rd-party/api/systems",
        json=dummy_systems(1, 0, 1),
    )


@pytest.fixture(name="webhooks")
def mock_webhooks(
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Fixture to setup fake requests made to Ekey Bionyx API during config flow."""
    aioclient_mock.get(
        "https://api.bionyx.io/3rd-party/api/systems/946DA01F-9ABD-4D9D-80C7-02AF85C822A8/function-webhooks",
        json=[
            {
                "functionWebhookId": "946DA01F-9ABD-4D9D-80C7-02AF85C822B9",
                "integrationName": "Home Assistant",
                "locationName": "A simple string containing 0 to 128 word, space and punctuation characters.",
                "functionName": "A simple string containing 0 to 50 word, space and punctuation characters.",
                "expiresAt": "2022-05-16T04:11:28.0000000+00:00",
                "modificationState": None,
            }
        ],
    )


@pytest.fixture(name="webhook_deletion")
def mock_webhook_deletion(
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Fixture to setup fake requests made to Ekey Bionyx API during config flow."""
    aioclient_mock.delete(
        "https://api.bionyx.io/3rd-party/api/systems/946DA01F-9ABD-4D9D-80C7-02AF85C822A8/function-webhooks/946DA01F-9ABD-4D9D-80C7-02AF85C822B9",
        status=HTTPStatus.ACCEPTED,
    )


@pytest.fixture(name="add_webhook", autouse=True)
def mock_add_webhook(
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Fixture to setup fake requests made to Ekey Bionyx API during config flow."""
    aioclient_mock.post(
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


@pytest.fixture(name="token_hex")
def mock_token_hex():
    """Mock auth property."""
    with patch(
        "secrets.token_hex",
        return_value="f2156edca7fc6871e13845314a6fc68622e5ad7c58f17663a487ed28cac247f7",
    ):
        yield


@pytest.fixture(name="config_entry")
def mock_config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Create mocked config entry."""
    return MockConfigEntry(
        title="test@test.com",
        domain=DOMAIN,
        data={
            "webhooks": [
                {
                    "webhook_id": "a2156edca7fb6671e13845314f6fc68622e5dd7c58f17663a487bd28cac247e7",
                    "name": "Test1",
                    "auth": "f2156edca7fc6871e13845314a6fc68622e5ad7c58f17663a487ed28cac247f7",
                    "ekey_id": "946DA01F-9ABD-4D9D-80C7-02AF85C822A8",
                }
            ]
        },
        unique_id="946DA01F-9ABD-4D9D-80C7-02AF85C822A8",
        version=1,
        minor_version=1,
    )
