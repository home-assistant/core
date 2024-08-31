"""Test the cloud component."""

from collections.abc import Callable, Coroutine
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components.cloud import (
    CloudConnectionState,
    CloudNotAvailable,
    CloudNotConnected,
    async_get_or_create_cloudhook,
    async_listen_connection_change,
    async_remote_ui_url,
)
from homeassistant.components.cloud.const import (
    DATA_CLOUD,
    DOMAIN,
    MODE_DEV,
    PREF_CLOUDHOOKS,
)
from homeassistant.components.cloud.prefs import STORAGE_KEY
from homeassistant.const import CONF_MODE, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import Context, HomeAssistant
from homeassistant.exceptions import Unauthorized
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry, MockUser


async def test_constructor_loads_info_from_config(hass: HomeAssistant) -> None:
    """Test non-dev mode loads info from SERVERS constant."""
    with patch("hass_nabucasa.Cloud.initialize"):
        result = await async_setup_component(
            hass,
            "cloud",
            {
                "http": {},
                "cloud": {
                    CONF_MODE: MODE_DEV,
                    "cognito_client_id": "test-cognito_client_id",
                    "user_pool_id": "test-user_pool_id",
                    "region": "test-region",
                    "relayer_server": "test-relayer-server",
                    "accounts_server": "test-acounts-server",
                    "cloudhook_server": "test-cloudhook-server",
                    "alexa_server": "test-alexa-server",
                    "acme_server": "test-acme-server",
                    "remotestate_server": "test-remotestate-server",
                },
            },
        )
        assert result

    cl = hass.data[DATA_CLOUD]
    assert cl.mode == MODE_DEV
    assert cl.cognito_client_id == "test-cognito_client_id"
    assert cl.user_pool_id == "test-user_pool_id"
    assert cl.region == "test-region"
    assert cl.relayer_server == "test-relayer-server"
    assert cl.iot.ws_server_url == "wss://test-relayer-server/websocket"
    assert cl.accounts_server == "test-acounts-server"
    assert cl.cloudhook_server == "test-cloudhook-server"
    assert cl.alexa_server == "test-alexa-server"
    assert cl.acme_server == "test-acme-server"
    assert cl.remotestate_server == "test-remotestate-server"


@pytest.mark.usefixtures("mock_cloud_fixture")
async def test_remote_services(
    hass: HomeAssistant, hass_read_only_user: MockUser
) -> None:
    """Setup cloud component and test services."""
    cloud = hass.data[DATA_CLOUD]

    assert hass.services.has_service(DOMAIN, "remote_connect")
    assert hass.services.has_service(DOMAIN, "remote_disconnect")

    with patch("hass_nabucasa.remote.RemoteUI.connect") as mock_connect:
        await hass.services.async_call(DOMAIN, "remote_connect", blocking=True)
        await hass.async_block_till_done()

    assert mock_connect.called
    assert cloud.client.remote_autostart

    with patch("hass_nabucasa.remote.RemoteUI.disconnect") as mock_disconnect:
        await hass.services.async_call(DOMAIN, "remote_disconnect", blocking=True)
        await hass.async_block_till_done()

    assert mock_disconnect.called
    assert not cloud.client.remote_autostart

    # Test admin access required
    non_admin_context = Context(user_id=hass_read_only_user.id)

    with (
        patch("hass_nabucasa.remote.RemoteUI.connect") as mock_connect,
        pytest.raises(Unauthorized),
    ):
        await hass.services.async_call(
            DOMAIN, "remote_connect", blocking=True, context=non_admin_context
        )

    assert mock_connect.called is False

    with (
        patch("hass_nabucasa.remote.RemoteUI.disconnect") as mock_disconnect,
        pytest.raises(Unauthorized),
    ):
        await hass.services.async_call(
            DOMAIN, "remote_disconnect", blocking=True, context=non_admin_context
        )

    assert mock_disconnect.called is False


@pytest.mark.usefixtures("mock_cloud_fixture")
async def test_shutdown_event(hass: HomeAssistant) -> None:
    """Test if the cloud will stop on shutdown event."""
    with patch("hass_nabucasa.Cloud.stop") as mock_stop:
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
        await hass.async_block_till_done()

    assert mock_stop.called


async def test_setup_existing_cloud_user(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """Test setup with API push default data."""
    user = await hass.auth.async_create_system_user("Cloud test")
    hass_storage[STORAGE_KEY] = {"version": 1, "data": {"cloud_user": user.id}}
    with patch("hass_nabucasa.Cloud.initialize"):
        result = await async_setup_component(
            hass,
            "cloud",
            {
                "http": {},
                "cloud": {
                    CONF_MODE: MODE_DEV,
                    "cognito_client_id": "test-cognito_client_id",
                    "user_pool_id": "test-user_pool_id",
                    "region": "test-region",
                    "relayer_server": "test-relayer-serer",
                },
            },
        )
        assert result

    assert hass_storage[STORAGE_KEY]["data"]["cloud_user"] == user.id


@pytest.mark.usefixtures("mock_cloud_fixture")
async def test_on_connect(hass: HomeAssistant) -> None:
    """Test cloud on connect triggers."""
    cl = hass.data[DATA_CLOUD]

    assert len(cl.iot._on_connect) == 3

    assert len(hass.states.async_entity_ids("binary_sensor")) == 0

    cloud_states = []

    def handle_state(cloud_state):
        nonlocal cloud_states
        cloud_states.append(cloud_state)

    async_listen_connection_change(hass, handle_state)

    assert "async_setup" in str(cl.iot._on_connect[-1])
    await cl.iot._on_connect[-1]()
    await hass.async_block_till_done()

    assert len(hass.states.async_entity_ids("binary_sensor")) == 0

    # The on_start callback discovers the binary sensor platform
    assert "async_setup" in str(cl._on_start[-1])
    await cl._on_start[-1]()
    await hass.async_block_till_done()

    assert len(hass.states.async_entity_ids("binary_sensor")) == 1

    with patch("homeassistant.helpers.discovery.async_load_platform") as mock_load:
        await cl._on_start[-1]()
        await hass.async_block_till_done()

    assert len(mock_load.mock_calls) == 0

    assert len(cloud_states) == 1
    assert cloud_states[-1] == CloudConnectionState.CLOUD_CONNECTED

    await cl.iot._on_connect[-1]()
    await hass.async_block_till_done()
    assert len(cloud_states) == 2
    assert cloud_states[-1] == CloudConnectionState.CLOUD_CONNECTED

    assert len(cl.iot._on_disconnect) == 2
    assert "async_setup" in str(cl.iot._on_disconnect[-1])
    await cl.iot._on_disconnect[-1]()
    await hass.async_block_till_done()

    assert len(cloud_states) == 3
    assert cloud_states[-1] == CloudConnectionState.CLOUD_DISCONNECTED

    await cl.iot._on_disconnect[-1]()
    await hass.async_block_till_done()
    assert len(cloud_states) == 4
    assert cloud_states[-1] == CloudConnectionState.CLOUD_DISCONNECTED


@pytest.mark.usefixtures("mock_cloud_fixture")
async def test_remote_ui_url(hass: HomeAssistant) -> None:
    """Test getting remote ui url."""
    cl = hass.data[DATA_CLOUD]

    # Not logged in
    with pytest.raises(CloudNotAvailable):
        async_remote_ui_url(hass)

    with patch("homeassistant.components.cloud.async_is_logged_in", return_value=True):
        # Remote not enabled
        with pytest.raises(CloudNotAvailable):
            async_remote_ui_url(hass)

        with patch.object(cl.remote, "connect"):
            await cl.client.prefs.async_update(remote_enabled=True)
            await hass.async_block_till_done()

        # No instance domain
        with pytest.raises(CloudNotAvailable):
            async_remote_ui_url(hass)

        # Remote finished initializing
        cl.client.prefs._prefs["remote_domain"] = "example.com"

        assert async_remote_ui_url(hass) == "https://example.com"


async def test_async_get_or_create_cloudhook(
    hass: HomeAssistant,
    cloud: MagicMock,
    set_cloud_prefs: Callable[[dict[str, Any]], Coroutine[Any, Any, None]],
) -> None:
    """Test async_get_or_create_cloudhook."""
    assert await async_setup_component(hass, "cloud", {"cloud": {}})
    await hass.async_block_till_done()
    await cloud.login("test-user", "test-pass")

    webhook_id = "mock-webhook-id"
    cloudhook_url = "https://cloudhook.nabu.casa/abcdefg"

    with patch(
        "homeassistant.components.cloud.async_create_cloudhook",
        return_value=cloudhook_url,
    ) as async_create_cloudhook_mock:
        # create cloudhook as it does not exist
        assert (await async_get_or_create_cloudhook(hass, webhook_id)) == cloudhook_url
        async_create_cloudhook_mock.assert_called_once_with(hass, webhook_id)

        await set_cloud_prefs(
            {
                PREF_CLOUDHOOKS: {
                    webhook_id: {
                        "webhook_id": webhook_id,
                        "cloudhook_id": "random-id",
                        "cloudhook_url": cloudhook_url,
                        "managed": True,
                    }
                }
            }
        )

        async_create_cloudhook_mock.reset_mock()

        # get cloudhook as it exists
        assert await async_get_or_create_cloudhook(hass, webhook_id) == cloudhook_url
        async_create_cloudhook_mock.assert_not_called()

    # Simulate logged out
    await cloud.logout()

    # Not logged in
    with pytest.raises(CloudNotAvailable):
        await async_get_or_create_cloudhook(hass, webhook_id)

    # Simulate disconnected
    cloud.iot.state = "disconnected"

    # Not connected
    with pytest.raises(CloudNotConnected):
        await async_get_or_create_cloudhook(hass, webhook_id)


async def test_cloud_logout(
    hass: HomeAssistant,
    cloud: MagicMock,
) -> None:
    """Test cloud setup with existing config entry when user is logged out."""
    assert cloud.is_logged_in is False

    mock_config_entry = MockConfigEntry(domain=DOMAIN)
    mock_config_entry.add_to_hass(hass)
    assert await async_setup_component(hass, DOMAIN, {"cloud": {}})
    await hass.async_block_till_done()

    assert cloud.is_logged_in is False
