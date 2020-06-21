"""Tests for the Withings component."""
import datetime
import re
from typing import Any
from urllib.parse import urlparse

from aiohttp.test_utils import TestClient
from asynctest import MagicMock
import pytest
import requests_mock
from withings_api.common import NotifyAppli, NotifyListProfile, NotifyListResponse

from homeassistant.components.withings.common import (
    ConfigEntryWithingsApi,
    DataManager,
    WebhookConfig,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.config_entry_oauth2_flow import AbstractOAuth2Implementation

from tests.common import MockConfigEntry
from tests.components.withings.common import (
    ComponentFactory,
    get_data_manager_by_user_id,
    new_profile_config,
)
from tests.test_util.aiohttp import AiohttpClientMocker


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
            status_code=200,
            json={"status": 0, "body": {"message": "success"}},
        )

        api = ConfigEntryWithingsApi(hass, config_entry, implementation_mock)
        response = await hass.async_add_executor_job(
            api.request, "test", {"arg1": "val1", "arg2": "val2"}
        )
        assert response == {"message": "success"}


@pytest.mark.parametrize(
    ["user_id", "arg_user_id", "arg_appli", "expected_code"],
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
    aiohttp_client,
    user_id: int,
    arg_user_id: Any,
    arg_appli: Any,
    expected_code: int,
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


async def test_webhook_head(
    hass: HomeAssistant, component_factory: ComponentFactory, aiohttp_client,
) -> None:
    """Test head method on webhook view."""
    person0 = new_profile_config("person0", 0)

    await component_factory.configure_component(profile_configs=(person0,))
    await component_factory.setup_profile(person0.user_id)
    data_manager = get_data_manager_by_user_id(hass, person0.user_id)

    client: TestClient = await aiohttp_client(hass.http.app)
    resp = await client.head(urlparse(data_manager.webhook_config.url).path)
    assert resp.status == 200


async def test_webhook_put(
    hass: HomeAssistant, component_factory: ComponentFactory, aiohttp_client,
) -> None:
    """Test webhook callback."""
    person0 = new_profile_config("person0", 0)

    await component_factory.configure_component(profile_configs=(person0,))
    await component_factory.setup_profile(person0.user_id)
    data_manager = get_data_manager_by_user_id(hass, person0.user_id)

    client: TestClient = await aiohttp_client(hass.http.app)
    resp = await client.put(urlparse(data_manager.webhook_config.url).path)

    # Wait for remaining tasks to complete.
    await hass.async_block_till_done()

    assert resp.status == 200
    data = await resp.json()
    assert data
    assert data["code"] == 2


async def test_data_manager_webhook_subscription(
    hass: HomeAssistant,
    component_factory: ComponentFactory,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test data manager webhook subscriptions."""
    person0 = new_profile_config("person0", 0)
    await component_factory.configure_component(profile_configs=(person0,))

    api: ConfigEntryWithingsApi = MagicMock(spec=ConfigEntryWithingsApi)
    data_manager = DataManager(
        hass,
        "person0",
        api,
        0,
        WebhookConfig(id="1234", url="http://localhost/api/webhook/1234", enabled=True),
    )

    # pylint: disable=protected-access
    data_manager._notify_subscribe_delay = datetime.timedelta(seconds=0)
    data_manager._notify_unsubscribe_delay = datetime.timedelta(seconds=0)

    api.notify_list.return_value = NotifyListResponse(
        profiles=(
            NotifyListProfile(
                appli=NotifyAppli.BED_IN,
                callbackurl="https://not.my.callback/url",
                expires=None,
                comment=None,
            ),
            NotifyListProfile(
                appli=NotifyAppli.BED_IN,
                callbackurl=data_manager.webhook_config.url,
                expires=None,
                comment=None,
            ),
            NotifyListProfile(
                appli=NotifyAppli.BED_OUT,
                callbackurl=data_manager.webhook_config.url,
                expires=None,
                comment=None,
            ),
        )
    )

    aioclient_mock.clear_requests()
    aioclient_mock.request(
        "HEAD", data_manager.webhook_config.url, status=200,
    )

    # Test subscribing
    await data_manager.async_subscribe_webhook()
    api.notify_subscribe.assert_any_call(
        data_manager.webhook_config.url, NotifyAppli.WEIGHT
    )
    api.notify_subscribe.assert_any_call(
        data_manager.webhook_config.url, NotifyAppli.CIRCULATORY
    )
    api.notify_subscribe.assert_any_call(
        data_manager.webhook_config.url, NotifyAppli.ACTIVITY
    )
    api.notify_subscribe.assert_any_call(
        data_manager.webhook_config.url, NotifyAppli.SLEEP
    )
    try:
        api.notify_subscribe.assert_any_call(
            data_manager.webhook_config.url, NotifyAppli.USER
        )
        assert False
    except AssertionError:
        pass
    try:
        api.notify_subscribe.assert_any_call(
            data_manager.webhook_config.url, NotifyAppli.BED_IN
        )
        assert False
    except AssertionError:
        pass
    try:
        api.notify_subscribe.assert_any_call(
            data_manager.webhook_config.url, NotifyAppli.BED_OUT
        )
        assert False
    except AssertionError:
        pass

    # Test unsubscribing.
    await data_manager.async_unsubscribe_webhook()
    api.notify_revoke.assert_any_call(
        data_manager.webhook_config.url, NotifyAppli.BED_IN
    )
    api.notify_revoke.assert_any_call(
        data_manager.webhook_config.url, NotifyAppli.BED_OUT
    )
