"""Provide common fixtures."""

import asyncio
from unittest.mock import patch

import pytest

from homeassistant.components.ohme.const import DOMAIN

from tests.common import load_json_value_fixture
from tests.test_util.aiohttp import AiohttpClientMocker


@pytest.fixture(name="mock_session")
def mock_session():
    """Mock aiohttp.ClientSession."""
    mocker = AiohttpClientMocker()

    mocker.post(
        "https://www.googleapis.com/identitytoolkit/v3/relyingparty/verifyPassword",
        json={"idToken": "", "refreshToken": ""},
    )

    mocker.get(
        "/v1/users/me/account", json=load_json_value_fixture("account.json", DOMAIN)
    )

    mocker.get(
        "/v1/chargeSessions",
        json=load_json_value_fixture("charge_sessions.json", DOMAIN),
    )

    mocker.get(
        "/v1/chargeRules", json=load_json_value_fixture("charge_rules.json", DOMAIN)
    )

    mocker.get(
        "/v1/chargeDevices/chargerid/advancedSettings",
        json=load_json_value_fixture("advanced_settings.json", DOMAIN),
    )

    with patch(
        "aiohttp.ClientSession",
        side_effect=lambda *args, **kwargs: mocker.create_session(
            asyncio.get_event_loop()
        ),
    ):
        yield mocker
