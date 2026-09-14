"""Test the cloud component."""

from collections.abc import Callable, Coroutine
from typing import Any
from unittest.mock import MagicMock, patch

from hass_nabucasa import (
    AutoLoginController,
    LoginEvent,
    LoginFailedEvent,
    LoginFailedReason,
    LogoutEvent,
)
import pytest

from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.components.cloud import (
    CloudConnectionState,
    CloudNotAvailable,
    CloudNotConnected,
    async_get_or_create_cloudhook,
    async_listen_cloudhook_change,
    async_listen_connection_change,
    async_remote_ui_url,
)
from homeassistant.components.cloud.const import (
    DATA_CLOUD,
    DATA_PENDING_AUTO_LOGIN,
    DOMAIN,
    EVENT_CLOUD_EVENT,
    MODE_DEV,
    PREF_CLOUDHOOKS,
)
from homeassistant.components.cloud.prefs import STORAGE_KEY
from homeassistant.const import CONF_MODE, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import Context, HomeAssistant, callback
from homeassistant.exceptions import Unauthorized
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry, MockUser

REMOTE_UI_UNIQUE_ID = "cloud-remote-ui-connectivity"


async def test_constructor_loads_info_from_config(hass: HomeAssistant) -> None:
    """Test non-dev mode loads info from SERVERS constant."""
    with patch("hass_nabucasa.Cloud.initialize"):
        result = await async_setup_component(
            hass,
            DOMAIN,
            {
                "http": {},
                "cloud": {
                    CONF_MODE: MODE_DEV,
                    "cognito_client_id": "test-cognito_client_id",
                    "user_pool_id": "test-user_pool_id",
                    "region": "test-region",
                    "api_server": "test-api-server",
                    "relayer_server": "test-relayer-server",
                    "acme_server": "test-acme-server",
                    "remotestate_server": "test-remotestate-server",
                    "discovery_service_actions": {
                        "lorem_ipsum": "https://lorem.ipsum/test-url"
                    },
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
    assert cl.acme_server == "test-acme-server"
    assert cl.api_server == "test-api-server"
    assert cl.remotestate_server == "test-remotestate-server"
    assert (
        cl.service_discovery._action_overrides["lorem_ipsum"]
        == "https://lorem.ipsum/test-url"
    )


@pytest.mark.usefixtures("mock_cloud_fixture")
async def test_disabling_remote_without_backend(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test disabling remote before the remote backend is initialized.

    Preferences are reset when a new user logs in, which disables remote while
    hass_nabucasa has no backend to disconnect from.
    """
    prefs = hass.data[DATA_CLOUD].client.prefs

    with patch("hass_nabucasa.remote.RemoteUI.connect"):
        await prefs.async_update(remote_enabled=True)
        await hass.async_block_till_done()

    await prefs.async_update(remote_enabled=False)
    await hass.async_block_till_done()

    assert not prefs.remote_enabled
    assert "RemoteNotConnected" not in caplog.text


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
            DOMAIN,
            {
                "http": {},
                "cloud": {
                    CONF_MODE: MODE_DEV,
                    "cognito_client_id": "test-cognito_client_id",
                    "user_pool_id": "test-user_pool_id",
                    "region": "test-region",
                    "relayer_server": "test-relayer-serer",
                    "api_server": "test-api-server",
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
    assert await async_setup_component(hass, DOMAIN, {"cloud": {}})
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


async def test_setup_removes_stale_config_entry(
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
    assert not hass.config_entries.async_entries(DOMAIN)


async def test_logout_removes_config_entry(
    hass: HomeAssistant,
    cloud: MagicMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the config entry is removed on logout and recreated on login."""
    assert await async_setup_component(hass, DOMAIN, {"cloud": {}})
    await hass.async_block_till_done()

    assert not hass.config_entries.async_entries(DOMAIN)

    await cloud.login("test-user", "test-pass")
    await hass.async_block_till_done()

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert entity_registry.async_get_entity_id(
        BINARY_SENSOR_DOMAIN, DOMAIN, REMOTE_UI_UNIQUE_ID
    )

    await cloud.logout()
    await hass.async_block_till_done()

    assert not hass.config_entries.async_entries(DOMAIN)
    assert not entity_registry.async_get_entity_id(
        BINARY_SENSOR_DOMAIN, DOMAIN, REMOTE_UI_UNIQUE_ID
    )

    await cloud.login("test-user", "test-pass")
    await hass.async_block_till_done()

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert entity_registry.async_get_entity_id(
        BINARY_SENSOR_DOMAIN, DOMAIN, REMOTE_UI_UNIQUE_ID
    )


@pytest.fixture(name="pending_auto_login")
async def pending_auto_login_fixture(
    hass: HomeAssistant, cloud: MagicMock
) -> AutoLoginController:
    """Set up cloud with a registration waiting for its confirmation."""
    assert await async_setup_component(hass, DOMAIN, {"cloud": {}})
    await hass.async_block_till_done()

    controller = cloud.register_and_auto_login.return_value
    controller.email = "hello@bla.com"
    hass.data[DATA_PENDING_AUTO_LOGIN] = controller
    return controller


def _track_cloud_events(hass: HomeAssistant) -> list[dict[str, Any]]:
    """Collect the payloads pushed on the cloud event signal."""
    events: list[dict[str, Any]] = []

    @callback
    def collect(event: dict[str, Any]) -> None:
        events.append(event)

    async_dispatcher_connect(hass, EVENT_CLOUD_EVENT, collect)
    return events


@pytest.mark.usefixtures("pending_auto_login")
async def test_login_event_clears_pending_auto_login(
    hass: HomeAssistant,
    cloud: MagicMock,
) -> None:
    """Test a successful login forgets the registration and tells the frontend."""
    events = _track_cloud_events(hass)

    await cloud.events.publish(LoginEvent(auto=True))

    assert hass.data[DATA_PENDING_AUTO_LOGIN] is None
    assert events == [{"type": "login"}]
    assert cloud.register_and_auto_login.return_value.cancel.call_count == 0


@pytest.mark.usefixtures("pending_auto_login")
async def test_logout_event_clears_pending_auto_login(
    hass: HomeAssistant,
    cloud: MagicMock,
) -> None:
    """Test a logout forgets the registration without pushing an event."""
    events = _track_cloud_events(hass)

    await cloud.events.publish(LogoutEvent())

    assert hass.data[DATA_PENDING_AUTO_LOGIN] is None
    assert events == []


async def test_auto_login_failed_event_keeps_controller(
    hass: HomeAssistant,
    cloud: MagicMock,
    pending_auto_login: AutoLoginController,
) -> None:
    """Test giving up pushes the reason and leaves the controller in place."""
    events = _track_cloud_events(hass)

    pending_auto_login.failed_reason = LoginFailedReason.CLOUD_ERROR
    pending_auto_login.active = False
    await cloud.events.publish(
        LoginFailedEvent(auto=True, reason=LoginFailedReason.CLOUD_ERROR)
    )

    assert hass.data[DATA_PENDING_AUTO_LOGIN] is pending_auto_login
    assert events == [
        {
            "type": "auto_login_failed",
            "translation_key": "auto_login_failed_cloud_error",
        }
    ]


@pytest.mark.usefixtures("pending_auto_login")
async def test_interactive_login_failed_event_ignored(
    hass: HomeAssistant,
    cloud: MagicMock,
) -> None:
    """Test a failed interactive login is left to the caller that asked for it."""
    events = _track_cloud_events(hass)

    await cloud.events.publish(
        LoginFailedEvent(reason=LoginFailedReason.UNEXPECTED_ERROR)
    )

    assert events == []


async def test_async_listen_cloudhook_change(
    hass: HomeAssistant,
    cloud: MagicMock,
    set_cloud_prefs: Callable[[dict[str, Any]], Coroutine[Any, Any, None]],
) -> None:
    """Test async_listen_cloudhook_change."""
    assert await async_setup_component(hass, DOMAIN, {"cloud": {}})
    await hass.async_block_till_done()
    await cloud.login("test-user", "test-pass")

    webhook_id = "mock-webhook-id"
    cloudhook_url = "https://cloudhook.nabu.casa/abcdefg"

    # Set up initial cloudhooks state
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

    # Track cloudhook changes
    changes = []
    changeInvoked = False

    def on_change(cloudhook: dict[str, Any] | None) -> None:
        """Handle cloudhook change."""
        nonlocal changeInvoked
        changes.append(cloudhook)
        changeInvoked = True

    # Register the change listener
    unsubscribe = async_listen_cloudhook_change(hass, webhook_id, on_change)

    # Verify no changes yet
    assert len(changes) == 0
    assert changeInvoked is False

    # Delete the cloudhook by updating prefs
    await set_cloud_prefs({PREF_CLOUDHOOKS: {}})
    await hass.async_block_till_done()

    # Verify deletion callback was called with None
    assert len(changes) == 1
    assert changes[-1] is None
    assert changeInvoked is True

    # Reset changeInvoked to detect next change
    changeInvoked = False

    # Add cloudhook back
    cloudhook_data = {
        "webhook_id": webhook_id,
        "cloudhook_id": "random-id",
        "cloudhook_url": cloudhook_url,
        "managed": True,
    }
    await set_cloud_prefs({PREF_CLOUDHOOKS: {webhook_id: cloudhook_data}})
    await hass.async_block_till_done()

    # Verify callback called with cloudhook data
    assert len(changes) == 2
    assert changes[-1] == cloudhook_data
    assert changeInvoked is True

    # Reset changeInvoked to detect next change
    changeInvoked = False

    # Update cloudhook data with same cloudhook should not trigger callback
    await set_cloud_prefs({PREF_CLOUDHOOKS: {webhook_id: cloudhook_data}})
    await hass.async_block_till_done()

    assert changeInvoked is False

    # Unsubscribe from listener
    unsubscribe()

    # Delete cloudhook again
    await set_cloud_prefs({PREF_CLOUDHOOKS: {}})
    await hass.async_block_till_done()

    # Verify change callback was NOT called after unsubscribe
    assert len(changes) == 2
    assert changeInvoked is False


async def test_async_listen_cloudhook_change_cloud_setup_later(
    hass: HomeAssistant,
    cloud: MagicMock,
    set_cloud_prefs: Callable[[dict[str, Any]], Coroutine[Any, Any, None]],
) -> None:
    """Test cloudhook change listener with late cloud setup."""
    webhook_id = "mock-webhook-id"
    cloudhook_url = "https://cloudhook.nabu.casa/abcdefg"

    # Track cloudhook changes
    changes: list[dict[str, Any] | None] = []

    def on_change(cloudhook: dict[str, Any] | None) -> None:
        """Handle cloudhook change."""
        changes.append(cloudhook)

    # Register listener BEFORE cloud is set up
    unsubscribe = async_listen_cloudhook_change(hass, webhook_id, on_change)

    # Verify it returns a callable
    assert callable(unsubscribe)

    # No changes yet since cloud isn't set up
    assert len(changes) == 0

    # Now set up cloud
    assert await async_setup_component(hass, DOMAIN, {"cloud": {}})
    await hass.async_block_till_done()
    await cloud.login("test-user", "test-pass")

    # Add a cloudhook - this should trigger the listener
    cloudhook_data = {
        "webhook_id": webhook_id,
        "cloudhook_id": "random-id",
        "cloudhook_url": cloudhook_url,
        "managed": True,
    }
    await set_cloud_prefs({PREF_CLOUDHOOKS: {webhook_id: cloudhook_data}})
    await hass.async_block_till_done()

    # Verify the listener received the update
    assert len(changes) == 1
    assert changes[-1] == cloudhook_data

    # Unsubscribe and verify no more updates
    unsubscribe()

    await set_cloud_prefs({PREF_CLOUDHOOKS: {}})
    await hass.async_block_till_done()

    # Should not receive update after unsubscribe
    assert len(changes) == 1
