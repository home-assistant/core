"""Tests for the Withings component."""
from http import HTTPStatus
import re
from typing import Any
from unittest.mock import MagicMock
from urllib.parse import urlparse

from aiohttp.test_utils import TestClient
import pytest
import requests_mock
from withings_api.common import NotifyAppli

from homeassistant.components.withings.common import ConfigEntryWithingsApi
from homeassistant.core import HomeAssistant
from homeassistant.helpers.config_entry_oauth2_flow import AbstractOAuth2Implementation

from .common import ComponentFactory, get_data_manager_by_user_id, new_profile_config

from tests.common import MockConfigEntry
from tests.typing import ClientSessionGenerator


async def test_config_entry_withings_api(hass: HomeAssistant) -> None:
    """Test ConfigEntryWithingsApi."""
    config_entry = MockConfigEntry(
        data={"token": {"access_token": "mock_access_token", "expires_at": 1111111}}
    )
    config_entry.add_to_hass(hass)

    implementation_mock = MagicMock(spec=AbstractOAuth2Implementation)
    implementation_mock.async_refresh_token.return_value = {
        "expires_at": 1111111,
        "access_token": "mock_access_token",
    }

    with requests_mock.mock() as rqmck:
        rqmck.get(
            re.compile(".*"),
            status_code=HTTPStatus.OK,
            json={"status": 0, "body": {"message": "success"}},
        )

        api = ConfigEntryWithingsApi(hass, config_entry, implementation_mock)
        response = await hass.async_add_executor_job(
            api.request, "test", {"arg1": "val1", "arg2": "val2"}
        )
        assert response == {"message": "success"}


@pytest.mark.parametrize(
    ("user_id", "arg_user_id", "arg_appli", "expected_code"),
    [
        [0, 0, NotifyAppli.WEIGHT.value, 0],  # Success
        [0, None, 1, 0],  # Success, we ignore the user_id.
        [0, None, None, 12],  # No request body.
        [0, "GG", None, 20],  # appli not provided.
        [0, 0, None, 20],  # appli not provided.
        [0, 0, 99, 21],  # Invalid appli.
        [0, 11, NotifyAppli.WEIGHT.value, 0],  # Success, we ignore the user_id
    ],
)
async def test_webhook_post(
    hass: HomeAssistant,
    component_factory: ComponentFactory,
    aiohttp_client: ClientSessionGenerator,
    user_id: int,
    arg_user_id: Any,
    arg_appli: Any,
    expected_code: int,
    current_request_with_host: None,
) -> None:
    """Test webhook callback."""
    person0 = new_profile_config("person0", user_id)

    await component_factory.configure_component(profile_configs=(person0,))
    await component_factory.setup_profile(person0.user_id)
    data_manager = get_data_manager_by_user_id(hass, user_id)

    client: TestClient = await aiohttp_client(hass.http.app)

    post_data = {}
    if arg_user_id is not None:
        post_data["userid"] = arg_user_id
    if arg_appli is not None:
        post_data["appli"] = arg_appli

    resp = await client.post(
        urlparse(data_manager.webhook_config.url).path, data=post_data
    )

    # Wait for remaining tasks to complete.
    await hass.async_block_till_done()

    data = await resp.json()
    resp.close()

    assert data["code"] == expected_code
