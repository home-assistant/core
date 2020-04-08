"""Tests for the SmartThings component init module."""
from uuid import uuid4

from aiohttp import ClientConnectionError, ClientResponseError
from asynctest import Mock, patch
from pysmartthings import InstalledAppStatus, OAuthToken
import pytest

from homeassistant.components import cloud, smartthings
from homeassistant.components.smartthings.const import (
    CONF_CLOUDHOOK_URL,
    CONF_INSTALLED_APP_ID,
    CONF_REFRESH_TOKEN,
    DATA_BROKERS,
    DOMAIN,
    EVENT_BUTTON,
    SIGNAL_SMARTTHINGS_UPDATE,
    SUPPORTED_PLATFORMS,
)
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry


async def test_migration_creates_new_flow(hass, smartthings_mock, config_entry):
    """Test migration deletes app and creates new flow."""
    assert await async_setup_component(hass, "persistent_notification", {})
    config_entry.version = 1
    config_entry.add_to_hass(hass)

    await smartthings.async_migrate_entry(hass, config_entry)
    await hass.async_block_till_done()

    assert smartthings_mock.delete_installed_app.call_count == 1
    assert smartthings_mock.delete_app.call_count == 1
    assert not hass.config_entries.async_entries(DOMAIN)
    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["handler"] == "smartthings"
    assert flows[0]["context"] == {"source": "import"}


async def test_unrecoverable_api_errors_create_new_flow(
    hass, config_entry, smartthings_mock
):
    """
    Test a new config flow is initiated when there are API errors.

    401 (unauthorized): Occurs when the access token is no longer valid.
    403 (forbidden/not found): Occurs when the app or installed app could
        not be retrieved/found (likely deleted?)
    """
    assert await async_setup_component(hass, "persistent_notification", {})
    config_entry.add_to_hass(hass)
    request_info = Mock(real_url="http://example.com")
    smartthings_mock.app.side_effect = ClientResponseError(
        request_info=request_info, history=None, status=401
    )

    # Assert setup returns false
    result = await smartthings.async_setup_entry(hass, config_entry)
    assert not result

    # Assert entry was removed and new flow created
    await hass.async_block_till_done()
    assert not hass.config_entries.async_entries(DOMAIN)
    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["handler"] == "smartthings"
    assert flows[0]["context"] == {"source": "import"}
    hass.config_entries.flow.async_abort(flows[0]["flow_id"])


async def test_recoverable_api_errors_raise_not_ready(
    hass, config_entry, smartthings_mock
):
    """Test config entry not ready raised for recoverable API errors."""
    config_entry.add_to_hass(hass)
    request_info = Mock(real_url="http://example.com")
    smartthings_mock.app.side_effect = ClientResponseError(
        request_info=request_info, history=None, status=500
    )

    with pytest.raises(ConfigEntryNotReady):
        await smartthings.async_setup_entry(hass, config_entry)


async def test_scenes_api_errors_raise_not_ready(
    hass, config_entry, app, installed_app, smartthings_mock
):
    """Test if scenes are unauthorized we continue to load platforms."""
    config_entry.add_to_hass(hass)
    request_info = Mock(real_url="http://example.com")
    smartthings_mock.app.return_value = app
    smartthings_mock.installed_app.return_value = installed_app
    smartthings_mock.scenes.side_effect = ClientResponseError(
        request_info=request_info, history=None, status=500
    )
    with pytest.raises(ConfigEntryNotReady):
        await smartthings.async_setup_entry(hass, config_entry)


async def test_connection_errors_raise_not_ready(hass, config_entry, smartthings_mock):
    """Test config entry not ready raised for connection errors."""
    config_entry.add_to_hass(hass)
    smartthings_mock.app.side_effect = ClientConnectionError()

    with pytest.raises(ConfigEntryNotReady):
        await smartthings.async_setup_entry(hass, config_entry)


async def test_base_url_no_longer_https_does_not_load(
    hass, config_entry, app, smartthings_mock
):
    """Test base_url no longer valid creates a new flow."""
    hass.config.api.base_url = "http://0.0.0.0"
    config_entry.add_to_hass(hass)
    smartthings_mock.app.return_value = app

    # Assert setup returns false
    result = await smartthings.async_setup_entry(hass, config_entry)
    assert not result


async def test_unauthorized_installed_app_raises_not_ready(
    hass, config_entry, app, installed_app, smartthings_mock
):
    """Test config entry not ready raised when the app isn't authorized."""
    config_entry.add_to_hass(hass)
    installed_app.installed_app_status = InstalledAppStatus.PENDING

    smartthings_mock.app.return_value = app
    smartthings_mock.installed_app.return_value = installed_app

    with pytest.raises(ConfigEntryNotReady):
        await smartthings.async_setup_entry(hass, config_entry)


async def test_scenes_unauthorized_loads_platforms(
    hass,
    config_entry,
    app,
    installed_app,
    device,
    smartthings_mock,
    subscription_factory,
):
    """Test if scenes are unauthorized we continue to load platforms."""
    config_entry.add_to_hass(hass)
    request_info = Mock(real_url="http://example.com")
    smartthings_mock.app.return_value = app
    smartthings_mock.installed_app.return_value = installed_app
    smartthings_mock.devices.return_value = [device]
    smartthings_mock.scenes.side_effect = ClientResponseError(
        request_info=request_info, history=None, status=403
    )
    mock_token = Mock()
    mock_token.access_token.return_value = str(uuid4())
    mock_token.refresh_token.return_value = str(uuid4())
    smartthings_mock.generate_tokens.return_value = mock_token
    subscriptions = [
        subscription_factory(capability) for capability in device.capabilities
    ]
    smartthings_mock.subscriptions.return_value = subscriptions

    with patch.object(hass.config_entries, "async_forward_entry_setup") as forward_mock:
        assert await smartthings.async_setup_entry(hass, config_entry)
        # Assert platforms loaded
        await hass.async_block_till_done()
        assert forward_mock.call_count == len(SUPPORTED_PLATFORMS)


async def test_config_entry_loads_platforms(
    hass,
    config_entry,
    app,
    installed_app,
    device,
    smartthings_mock,
    subscription_factory,
    scene,
):
    """Test config entry loads properly and proxies to platforms."""
    config_entry.add_to_hass(hass)
    smartthings_mock.app.return_value = app
    smartthings_mock.installed_app.return_value = installed_app
    smartthings_mock.devices.return_value = [device]
    smartthings_mock.scenes.return_value = [scene]
    mock_token = Mock()
    mock_token.access_token.return_value = str(uuid4())
    mock_token.refresh_token.return_value = str(uuid4())
    smartthings_mock.generate_tokens.return_value = mock_token
    subscriptions = [
        subscription_factory(capability) for capability in device.capabilities
    ]
    smartthings_mock.subscriptions.return_value = subscriptions

    with patch.object(hass.config_entries, "async_forward_entry_setup") as forward_mock:
        assert await smartthings.async_setup_entry(hass, config_entry)
        # Assert platforms loaded
        await hass.async_block_till_done()
        assert forward_mock.call_count == len(SUPPORTED_PLATFORMS)


async def test_config_entry_loads_unconnected_cloud(
    hass,
    config_entry,
    app,
    installed_app,
    device,
    smartthings_mock,
    subscription_factory,
    scene,
):
    """Test entry loads during startup when cloud isn't connected."""
    config_entry.add_to_hass(hass)
    hass.data[DOMAIN][CONF_CLOUDHOOK_URL] = "https://test.cloud"
    hass.config.api.base_url = "http://0.0.0.0"
    smartthings_mock.app.return_value = app
    smartthings_mock.installed_app.return_value = installed_app
    smartthings_mock.devices.return_value = [device]
    smartthings_mock.scenes.return_value = [scene]
    mock_token = Mock()
    mock_token.access_token.return_value = str(uuid4())
    mock_token.refresh_token.return_value = str(uuid4())
    smartthings_mock.generate_tokens.return_value = mock_token
    subscriptions = [
        subscription_factory(capability) for capability in device.capabilities
    ]
    smartthings_mock.subscriptions.return_value = subscriptions
    with patch.object(hass.config_entries, "async_forward_entry_setup") as forward_mock:
        assert await smartthings.async_setup_entry(hass, config_entry)
        await hass.async_block_till_done()
        assert forward_mock.call_count == len(SUPPORTED_PLATFORMS)


async def test_unload_entry(hass, config_entry):
    """Test entries are unloaded correctly."""
    connect_disconnect = Mock()
    smart_app = Mock()
    smart_app.connect_event.return_value = connect_disconnect
    broker = smartthings.DeviceBroker(hass, config_entry, Mock(), smart_app, [], [])
    broker.connect()
    hass.data[DOMAIN][DATA_BROKERS][config_entry.entry_id] = broker

    with patch.object(
        hass.config_entries, "async_forward_entry_unload", return_value=True
    ) as forward_mock:
        assert await smartthings.async_unload_entry(hass, config_entry)

        assert connect_disconnect.call_count == 1
        assert config_entry.entry_id not in hass.data[DOMAIN][DATA_BROKERS]
        # Assert platforms unloaded
        await hass.async_block_till_done()
        assert forward_mock.call_count == len(SUPPORTED_PLATFORMS)


async def test_remove_entry(hass, config_entry, smartthings_mock):
    """Test that the installed app and app are removed up."""
    # Act
    await smartthings.async_remove_entry(hass, config_entry)
    # Assert
    assert smartthings_mock.delete_installed_app.call_count == 1
    assert smartthings_mock.delete_app.call_count == 1


async def test_remove_entry_cloudhook(hass, config_entry, smartthings_mock):
    """Test that the installed app, app, and cloudhook are removed up."""
    hass.config.components.add("cloud")
    # Arrange
    config_entry.add_to_hass(hass)
    hass.data[DOMAIN][CONF_CLOUDHOOK_URL] = "https://test.cloud"
    # Act
    with patch.object(
        cloud, "async_is_logged_in", return_value=True
    ) as mock_async_is_logged_in, patch.object(
        cloud, "async_delete_cloudhook"
    ) as mock_async_delete_cloudhook:
        await smartthings.async_remove_entry(hass, config_entry)
    # Assert
    assert smartthings_mock.delete_installed_app.call_count == 1
    assert smartthings_mock.delete_app.call_count == 1
    assert mock_async_is_logged_in.call_count == 1
    assert mock_async_delete_cloudhook.call_count == 1


async def test_remove_entry_app_in_use(hass, config_entry, smartthings_mock):
    """Test app is not removed if in use by another config entry."""
    # Arrange
    config_entry.add_to_hass(hass)
    data = config_entry.data.copy()
    data[CONF_INSTALLED_APP_ID] = str(uuid4())
    entry2 = MockConfigEntry(version=2, domain=DOMAIN, data=data)
    entry2.add_to_hass(hass)
    # Act
    await smartthings.async_remove_entry(hass, config_entry)
    # Assert
    assert smartthings_mock.delete_installed_app.call_count == 1
    assert smartthings_mock.delete_app.call_count == 0


async def test_remove_entry_already_deleted(hass, config_entry, smartthings_mock):
    """Test handles when the apps have already been removed."""
    request_info = Mock(real_url="http://example.com")
    # Arrange
    smartthings_mock.delete_installed_app.side_effect = ClientResponseError(
        request_info=request_info, history=None, status=403
    )
    smartthings_mock.delete_app.side_effect = ClientResponseError(
        request_info=request_info, history=None, status=403
    )
    # Act
    await smartthings.async_remove_entry(hass, config_entry)
    # Assert
    assert smartthings_mock.delete_installed_app.call_count == 1
    assert smartthings_mock.delete_app.call_count == 1


async def test_remove_entry_installedapp_api_error(
    hass, config_entry, smartthings_mock
):
    """Test raises exceptions removing the installed app."""
    request_info = Mock(real_url="http://example.com")
    # Arrange
    smartthings_mock.delete_installed_app.side_effect = ClientResponseError(
        request_info=request_info, history=None, status=500
    )
    # Act
    with pytest.raises(ClientResponseError):
        await smartthings.async_remove_entry(hass, config_entry)
    # Assert
    assert smartthings_mock.delete_installed_app.call_count == 1
    assert smartthings_mock.delete_app.call_count == 0


async def test_remove_entry_installedapp_unknown_error(
    hass, config_entry, smartthings_mock
):
    """Test raises exceptions removing the installed app."""
    # Arrange
    smartthings_mock.delete_installed_app.side_effect = Exception
    # Act
    with pytest.raises(Exception):
        await smartthings.async_remove_entry(hass, config_entry)
    # Assert
    assert smartthings_mock.delete_installed_app.call_count == 1
    assert smartthings_mock.delete_app.call_count == 0


async def test_remove_entry_app_api_error(hass, config_entry, smartthings_mock):
    """Test raises exceptions removing the app."""
    # Arrange
    request_info = Mock(real_url="http://example.com")
    smartthings_mock.delete_app.side_effect = ClientResponseError(
        request_info=request_info, history=None, status=500
    )
    # Act
    with pytest.raises(ClientResponseError):
        await smartthings.async_remove_entry(hass, config_entry)
    # Assert
    assert smartthings_mock.delete_installed_app.call_count == 1
    assert smartthings_mock.delete_app.call_count == 1


async def test_remove_entry_app_unknown_error(hass, config_entry, smartthings_mock):
    """Test raises exceptions removing the app."""
    # Arrange
    smartthings_mock.delete_app.side_effect = Exception
    # Act
    with pytest.raises(Exception):
        await smartthings.async_remove_entry(hass, config_entry)
    # Assert
    assert smartthings_mock.delete_installed_app.call_count == 1
    assert smartthings_mock.delete_app.call_count == 1


async def test_broker_regenerates_token(hass, config_entry):
    """Test the device broker regenerates the refresh token."""
    token = Mock(OAuthToken)
    token.refresh_token = str(uuid4())
    stored_action = None

    def async_track_time_interval(hass, action, interval):
        nonlocal stored_action
        stored_action = action

    with patch(
        "homeassistant.components.smartthings.async_track_time_interval",
        new=async_track_time_interval,
    ):
        broker = smartthings.DeviceBroker(hass, config_entry, token, Mock(), [], [])
        broker.connect()

    assert stored_action
    await stored_action(None)  # pylint:disable=not-callable
    assert token.refresh.call_count == 1
    assert config_entry.data[CONF_REFRESH_TOKEN] == token.refresh_token


async def test_event_handler_dispatches_updated_devices(
    hass, config_entry, device_factory, event_request_factory, event_factory
):
    """Test the event handler dispatches updated devices."""
    devices = [
        device_factory("Bedroom 1 Switch", ["switch"]),
        device_factory("Bathroom 1", ["switch"]),
        device_factory("Sensor", ["motionSensor"]),
        device_factory("Lock", ["lock"]),
    ]
    device_ids = [
        devices[0].device_id,
        devices[1].device_id,
        devices[2].device_id,
        devices[3].device_id,
    ]
    event = event_factory(
        devices[3].device_id,
        capability="lock",
        attribute="lock",
        value="locked",
        data={"codeId": "1"},
    )
    request = event_request_factory(device_ids=device_ids, events=[event])
    config_entry.data = {
        **config_entry.data,
        CONF_INSTALLED_APP_ID: request.installed_app_id,
    }
    called = False

    def signal(ids):
        nonlocal called
        called = True
        assert device_ids == ids

    async_dispatcher_connect(hass, SIGNAL_SMARTTHINGS_UPDATE, signal)

    broker = smartthings.DeviceBroker(hass, config_entry, Mock(), Mock(), devices, [])
    broker.connect()

    # pylint:disable=protected-access
    await broker._event_handler(request, None, None)
    await hass.async_block_till_done()

    assert called
    for device in devices:
        assert device.status.values["Updated"] == "Value"
    assert devices[3].status.attributes["lock"].value == "locked"
    assert devices[3].status.attributes["lock"].data == {"codeId": "1"}


async def test_event_handler_ignores_other_installed_app(
    hass, config_entry, device_factory, event_request_factory
):
    """Test the event handler dispatches updated devices."""
    device = device_factory("Bedroom 1 Switch", ["switch"])
    request = event_request_factory([device.device_id])
    called = False

    def signal(ids):
        nonlocal called
        called = True

    async_dispatcher_connect(hass, SIGNAL_SMARTTHINGS_UPDATE, signal)
    broker = smartthings.DeviceBroker(hass, config_entry, Mock(), Mock(), [device], [])
    broker.connect()

    # pylint:disable=protected-access
    await broker._event_handler(request, None, None)
    await hass.async_block_till_done()

    assert not called


async def test_event_handler_fires_button_events(
    hass, config_entry, device_factory, event_factory, event_request_factory
):
    """Test the event handler fires button events."""
    device = device_factory("Button 1", ["button"])
    event = event_factory(
        device.device_id, capability="button", attribute="button", value="pushed"
    )
    request = event_request_factory(events=[event])
    config_entry.data = {
        **config_entry.data,
        CONF_INSTALLED_APP_ID: request.installed_app_id,
    }
    called = False

    def handler(evt):
        nonlocal called
        called = True
        assert evt.data == {
            "component_id": "main",
            "device_id": device.device_id,
            "location_id": event.location_id,
            "value": "pushed",
            "name": device.label,
            "data": None,
        }

    hass.bus.async_listen(EVENT_BUTTON, handler)
    broker = smartthings.DeviceBroker(hass, config_entry, Mock(), Mock(), [device], [])
    broker.connect()

    # pylint:disable=protected-access
    await broker._event_handler(request, None, None)
    await hass.async_block_till_done()

    assert called
