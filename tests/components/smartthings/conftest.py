"""Test configuration and mocks for the SmartThings component."""
from collections import defaultdict
from unittest.mock import Mock, patch
from uuid import uuid4

from pysmartthings import (
    CLASSIFICATION_AUTOMATION, AppEntity, AppOAuthClient, AppSettings,
    DeviceEntity, InstalledApp, Location, SceneEntity, Subscription)
from pysmartthings.api import Api
import pytest

from homeassistant.components import webhook
from homeassistant.components.smartthings import DeviceBroker
from homeassistant.components.smartthings.const import (
    APP_NAME_PREFIX, CONF_APP_ID, CONF_INSTALLED_APP_ID, CONF_INSTANCE_ID,
    CONF_LOCATION_ID, CONF_OAUTH_CLIENT_ID, CONF_OAUTH_CLIENT_SECRET,
    CONF_REFRESH_TOKEN, DATA_BROKERS, DOMAIN, SETTINGS_INSTANCE_ID,
    STORAGE_KEY, STORAGE_VERSION)
from homeassistant.config_entries import (
    CONN_CLASS_CLOUD_PUSH, SOURCE_USER, ConfigEntry)
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_WEBHOOK_ID
from homeassistant.setup import async_setup_component

from tests.common import mock_coro


async def setup_platform(hass, platform: str, *,
                         devices=None, scenes=None):
    """Set up the SmartThings platform and prerequisites."""
    hass.config.components.add(DOMAIN)
    config_entry = ConfigEntry(2, DOMAIN, "Test",
                               {CONF_INSTALLED_APP_ID:  str(uuid4())},
                               SOURCE_USER, CONN_CLASS_CLOUD_PUSH)
    broker = DeviceBroker(hass, config_entry, Mock(), Mock(),
                          devices or [], scenes or [])

    hass.data[DOMAIN] = {
        DATA_BROKERS: {
            config_entry.entry_id: broker
        }
    }
    await hass.config_entries.async_forward_entry_setup(
        config_entry, platform)
    await hass.async_block_till_done()
    return config_entry


@pytest.fixture(autouse=True)
async def setup_component(hass, config_file, hass_storage):
    """Load the SmartThing component."""
    hass_storage[STORAGE_KEY] = {'data': config_file,
                                 "version": STORAGE_VERSION}
    await async_setup_component(hass, 'smartthings', {})
    hass.config.api.base_url = 'https://test.local'


def _create_location():
    loc = Location()
    loc.apply_data({
        'name': 'Test Location',
        'locationId': str(uuid4())
    })
    return loc


@pytest.fixture(name='location')
def location_fixture():
    """Fixture for a single location."""
    return _create_location()


@pytest.fixture(name='locations')
def locations_fixture(location):
    """Fixture for 2 locations."""
    return [location, _create_location()]


@pytest.fixture(name="app")
def app_fixture(hass, config_file):
    """Fixture for a single app."""
    app = AppEntity(Mock())
    app.apply_data({
        'appName': APP_NAME_PREFIX + str(uuid4()),
        'appId': str(uuid4()),
        'appType': 'WEBHOOK_SMART_APP',
        'classifications': [CLASSIFICATION_AUTOMATION],
        'displayName': 'Home Assistant',
        'description':
            hass.config.location_name + " at " + hass.config.api.base_url,
        'singleInstance': True,
        'webhookSmartApp': {
            'targetUrl': webhook.async_generate_url(
                hass, hass.data[DOMAIN][CONF_WEBHOOK_ID]),
            'publicKey': ''}
    })
    app.refresh = Mock()
    app.refresh.return_value = mock_coro()
    app.save = Mock()
    app.save.return_value = mock_coro()
    settings = AppSettings(app.app_id)
    settings.settings[SETTINGS_INSTANCE_ID] = config_file[CONF_INSTANCE_ID]
    app.settings = Mock()
    app.settings.return_value = mock_coro(return_value=settings)
    return app


@pytest.fixture(name="app_oauth_client")
def app_oauth_client_fixture():
    """Fixture for a single app's oauth."""
    return AppOAuthClient({
        'oauthClientId': str(uuid4()),
        'oauthClientSecret': str(uuid4())
    })


@pytest.fixture(name='app_settings')
def app_settings_fixture(app, config_file):
    """Fixture for an app settings."""
    settings = AppSettings(app.app_id)
    settings.settings[SETTINGS_INSTANCE_ID] = config_file[CONF_INSTANCE_ID]
    return settings


def _create_installed_app(location_id, app_id):
    item = InstalledApp()
    item.apply_data(defaultdict(str, {
        'installedAppId': str(uuid4()),
        'installedAppStatus': 'AUTHORIZED',
        'installedAppType': 'UNKNOWN',
        'appId': app_id,
        'locationId': location_id
    }))
    return item


@pytest.fixture(name='installed_app')
def installed_app_fixture(location, app):
    """Fixture for a single installed app."""
    return _create_installed_app(location.location_id, app.app_id)


@pytest.fixture(name='installed_apps')
def installed_apps_fixture(installed_app, locations, app):
    """Fixture for 2 installed apps."""
    return [installed_app,
            _create_installed_app(locations[1].location_id, app.app_id)]


@pytest.fixture(name='config_file')
def config_file_fixture():
    """Fixture representing the local config file contents."""
    return {
        CONF_INSTANCE_ID: str(uuid4()),
        CONF_WEBHOOK_ID: webhook.generate_secret()
    }


@pytest.fixture(name='smartthings_mock')
def smartthings_mock_fixture(locations):
    """Fixture to mock smartthings API calls."""
    def _location(location_id):
        return mock_coro(
            return_value=next(location for location in locations
                              if location.location_id == location_id))

    with patch("pysmartthings.SmartThings", autospec=True) as mock:
        mock.return_value.location.side_effect = _location
        yield mock


@pytest.fixture(name='device')
def device_fixture(location):
    """Fixture representing devices loaded."""
    item = DeviceEntity(None)
    item.status.refresh = Mock()
    item.status.refresh.return_value = mock_coro()
    item.apply_data({
        "deviceId": "743de49f-036f-4e9c-839a-2f89d57607db",
        "name": "GE In-Wall Smart Dimmer",
        "label": "Front Porch Lights",
        "deviceManufacturerCode": "0063-4944-3038",
        "locationId": location.location_id,
        "deviceTypeId": "8a9d4b1e3b9b1fe3013b9b206a7f000d",
        "deviceTypeName": "Dimmer Switch",
        "deviceNetworkType": "ZWAVE",
        "components": [
            {
                "id": "main",
                "capabilities": [
                    {
                        "id": "switch",
                        "version": 1
                    },
                    {
                        "id": "switchLevel",
                        "version": 1
                    },
                    {
                        "id": "refresh",
                        "version": 1
                    },
                    {
                        "id": "indicator",
                        "version": 1
                    },
                    {
                        "id": "sensor",
                        "version": 1
                    },
                    {
                        "id": "actuator",
                        "version": 1
                    },
                    {
                        "id": "healthCheck",
                        "version": 1
                    },
                    {
                        "id": "light",
                        "version": 1
                    }
                ]
            }
        ],
        "dth": {
            "deviceTypeId": "8a9d4b1e3b9b1fe3013b9b206a7f000d",
            "deviceTypeName": "Dimmer Switch",
            "deviceNetworkType": "ZWAVE",
            "completedSetup": False
        },
        "type": "DTH"
    })
    return item


@pytest.fixture(name='config_entry')
def config_entry_fixture(hass, installed_app, location):
    """Fixture representing a config entry."""
    data = {
        CONF_ACCESS_TOKEN: str(uuid4()),
        CONF_INSTALLED_APP_ID: installed_app.installed_app_id,
        CONF_APP_ID: installed_app.app_id,
        CONF_LOCATION_ID: location.location_id,
        CONF_REFRESH_TOKEN: str(uuid4()),
        CONF_OAUTH_CLIENT_ID: str(uuid4()),
        CONF_OAUTH_CLIENT_SECRET: str(uuid4())
    }
    return ConfigEntry(2, DOMAIN, location.name, data, SOURCE_USER,
                       CONN_CLASS_CLOUD_PUSH)


@pytest.fixture(name="subscription_factory")
def subscription_factory_fixture():
    """Fixture for creating mock subscriptions."""
    def _factory(capability):
        sub = Subscription()
        sub.capability = capability
        return sub
    return _factory


@pytest.fixture(name="device_factory")
def device_factory_fixture():
    """Fixture for creating mock devices."""
    api = Mock(spec=Api)
    api.post_device_command.side_effect = \
        lambda *args, **kwargs: mock_coro(return_value={})

    def _factory(label, capabilities, status: dict = None):
        device_data = {
            "deviceId": str(uuid4()),
            "name": "Device Type Handler Name",
            "label": label,
            "deviceManufacturerCode": "9135fc86-0929-4436-bf73-5d75f523d9db",
            "locationId": "fcd829e9-82f4-45b9-acfd-62fda029af80",
            "components": [
                {
                    "id": "main",
                    "capabilities": [
                        {"id": capability, "version": 1}
                        for capability in capabilities
                    ]
                }
            ],
            "dth": {
                "deviceTypeId": "b678b29d-2726-4e4f-9c3f-7aa05bd08964",
                "deviceTypeName": "Switch",
                "deviceNetworkType": "ZWAVE"
            },
            "type": "DTH"
        }
        device = DeviceEntity(api, data=device_data)
        if status:
            for attribute, value in status.items():
                device.status.apply_attribute_update(
                    'main', '', attribute, value)
        return device
    return _factory


@pytest.fixture(name="scene_factory")
def scene_factory_fixture(location):
    """Fixture for creating mock devices."""
    api = Mock(spec=Api)
    api.execute_scene.side_effect = \
        lambda *args, **kwargs: mock_coro(return_value={})

    def _factory(name):
        scene_data = {
            'sceneId': str(uuid4()),
            'sceneName': name,
            'sceneIcon': '',
            'sceneColor': '',
            'locationId': location.location_id
        }
        return SceneEntity(api, scene_data)
    return _factory


@pytest.fixture(name="scene")
def scene_fixture(scene_factory):
    """Fixture for an individual scene."""
    return scene_factory('Test Scene')


@pytest.fixture(name="event_factory")
def event_factory_fixture():
    """Fixture for creating mock devices."""
    def _factory(device_id, event_type="DEVICE_EVENT", capability='',
                 attribute='Updated', value='Value', data=None):
        event = Mock()
        event.event_type = event_type
        event.device_id = device_id
        event.component_id = 'main'
        event.capability = capability
        event.attribute = attribute
        event.value = value
        event.data = data
        event.location_id = str(uuid4())
        return event
    return _factory


@pytest.fixture(name="event_request_factory")
def event_request_factory_fixture(event_factory):
    """Fixture for creating mock smartapp event requests."""
    def _factory(device_ids=None, events=None):
        request = Mock()
        request.installed_app_id = uuid4()
        if events is None:
            events = []
        if device_ids:
            events.extend([event_factory(id) for id in device_ids])
            events.append(event_factory(uuid4()))
            events.append(event_factory(device_ids[0], event_type="OTHER"))
        request.events = events
        return request
    return _factory
