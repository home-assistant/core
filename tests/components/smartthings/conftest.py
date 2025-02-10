"""Test configuration and mocks for the SmartThings component."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

from pysmartthings.models import DeviceResponse, DeviceStatus
import pytest

from homeassistant.components.smartthings.const import CONF_LOCATION_ID, DOMAIN
from homeassistant.const import CONF_ACCESS_TOKEN

from tests.common import MockConfigEntry, load_fixture
from tests.components.light.conftest import mock_light_profiles  # noqa: F401

# COMPONENT_PREFIX = "homeassistant.components.smartthings."
#
#
# async def setup_platform(
#     hass: HomeAssistant, platform: str, *, devices=None, scenes=None
# ):
#     """Set up the SmartThings platform and prerequisites."""
#     hass.config.components.add(DOMAIN)
#     config_entry = MockConfigEntry(
#         version=2,
#         domain=DOMAIN,
#         title="Test",
#         data={CONF_INSTALLED_APP_ID: str(uuid4())},
#     )
#     config_entry.add_to_hass(hass)
#     broker = DeviceBroker(
#         hass, config_entry, Mock(), Mock(), devices or [], scenes or []
#     )
#
#     hass.data[DOMAIN] = {DATA_BROKERS: {config_entry.entry_id: broker}}
#     config_entry.mock_state(hass, ConfigEntryState.LOADED)
#     await hass.config_entries.async_forward_entry_setups(config_entry, [platform])
#     await hass.async_block_till_done()
#     return config_entry
#
#
# @pytest.fixture(autouse=True)
# async def setup_component(
#     hass: HomeAssistant, config_file: dict[str, str], hass_storage: dict[str, Any]
# ) -> None:
#     """Load the SmartThing component."""
#     hass_storage[STORAGE_KEY] = {"data": config_file, "version": STORAGE_VERSION}
#     await async_process_ha_core_config(
#         hass,
#         {"external_url": "https://test.local"},
#     )
#     await async_setup_component(hass, "smartthings", {})
#
#
# def _create_location() -> Mock:
#     loc = Mock(Location)
#     loc.name = "Test Location"
#     loc.location_id = str(uuid4())
#     return loc
#
#
# @pytest.fixture(name="location")
# def location_fixture() -> Mock:
#     """Fixture for a single location."""
#     return _create_location()
#
#
# @pytest.fixture(name="locations")
# def locations_fixture(location: Mock) -> list[Mock]:
#     """Fixture for 2 locations."""
#     return [location, _create_location()]
#
#
# @pytest.fixture(name="app")
# async def app_fixture(hass: HomeAssistant, config_file: dict[str, str]) -> Mock:
#     """Fixture for a single app."""
#     app = Mock(AppEntity)
#     app.app_name = APP_NAME_PREFIX + str(uuid4())
#     app.app_id = str(uuid4())
#     app.app_type = "WEBHOOK_SMART_APP"
#     app.classifications = [CLASSIFICATION_AUTOMATION]
#     app.display_name = "Home Assistant"
#     app.description = f"{hass.config.location_name} at https://test.local"
#     app.single_instance = True
#     app.webhook_target_url = webhook.async_generate_url(
#         hass, hass.data[DOMAIN][CONF_WEBHOOK_ID]
#     )
#
#     settings = Mock(AppSettings)
#     settings.app_id = app.app_id
#     settings.settings = {SETTINGS_INSTANCE_ID: config_file[CONF_INSTANCE_ID]}
#     app.settings.return_value = settings
#     return app
#
#
# @pytest.fixture(name="app_oauth_client")
# def app_oauth_client_fixture() -> Mock:
#     """Fixture for a single app's oauth."""
#     client = Mock(AppOAuthClient)
#     client.client_id = str(uuid4())
#     client.client_secret = str(uuid4())
#     return client
#
#
# @pytest.fixture(name="app_settings")
# def app_settings_fixture(app, config_file):
#     """Fixture for an app settings."""
#     settings = Mock(AppSettings)
#     settings.app_id = app.app_id
#     settings.settings = {SETTINGS_INSTANCE_ID: config_file[CONF_INSTANCE_ID]}
#     return settings
#
#
# def _create_installed_app(location_id: str, app_id: str) -> Mock:
#     item = Mock(InstalledApp)
#     item.installed_app_id = str(uuid4())
#     item.installed_app_status = InstalledAppStatus.AUTHORIZED
#     item.installed_app_type = InstalledAppType.WEBHOOK_SMART_APP
#     item.app_id = app_id
#     item.location_id = location_id
#     return item
#
#
# @pytest.fixture(name="installed_app")
# def installed_app_fixture(location: Mock, app: Mock) -> Mock:
#     """Fixture for a single installed app."""
#     return _create_installed_app(location.location_id, app.app_id)
#
#
# @pytest.fixture(name="installed_apps")
# def installed_apps_fixture(installed_app, locations, app):
#     """Fixture for 2 installed apps."""
#     return [installed_app, _create_installed_app(locations[1].location_id, app.app_id)]
#
#
# @pytest.fixture(name="config_file")
# def config_file_fixture() -> dict[str, str]:
#     """Fixture representing the local config file contents."""
#     return {CONF_INSTANCE_ID: str(uuid4()), CONF_WEBHOOK_ID: secrets.token_hex()}
#
#
# @pytest.fixture(name="smartthings_mock")
# def smartthings_mock_fixture(locations):
#     """Fixture to mock smartthings API calls."""
#
#     async def _location(location_id):
#         return next(
#             location for location in locations if location.location_id == location_id
#         )
#
#     smartthings_mock = Mock(SmartThings)
#     smartthings_mock.location.side_effect = _location
#     mock = Mock(return_value=smartthings_mock)
#     with (
#         patch(COMPONENT_PREFIX + "SmartThings", new=mock),
#         patch(COMPONENT_PREFIX + "config_flow.SmartThings", new=mock),
#         patch(COMPONENT_PREFIX + "smartapp.SmartThings", new=mock),
#     ):
#         yield smartthings_mock
#
#
# @pytest.fixture(name="device")
# def device_fixture(location):
#     """Fixture representing devices loaded."""
#     item = Mock(DeviceEntity)
#     item.device_id = "743de49f-036f-4e9c-839a-2f89d57607db"
#     item.name = "GE In-Wall Smart Dimmer"
#     item.label = "Front Porch Lights"
#     item.location_id = location.location_id
#     item.capabilities = [
#         "switch",
#         "switchLevel",
#         "refresh",
#         "indicator",
#         "sensor",
#         "actuator",
#         "healthCheck",
#         "light",
#     ]
#     item.components = {"main": item.capabilities}
#     item.status = Mock(DeviceStatus)
#     return item
#
#
# @pytest.fixture(name="config_entry")
# def config_entry_fixture(installed_app: Mock, location: Mock) -> MockConfigEntry:
#     """Fixture representing a config entry."""
#     data = {
#         CONF_ACCESS_TOKEN: str(uuid4()),
#         CONF_INSTALLED_APP_ID: installed_app.installed_app_id,
#         CONF_APP_ID: installed_app.app_id,
#         CONF_LOCATION_ID: location.location_id,
#         CONF_REFRESH_TOKEN: str(uuid4()),
#         CONF_CLIENT_ID: str(uuid4()),
#         CONF_CLIENT_SECRET: str(uuid4()),
#     }
#     return MockConfigEntry(
#         domain=DOMAIN,
#         data=data,
#         title=location.name,
#         version=2,
#         source=SOURCE_USER,
#     )
#
#
# @pytest.fixture(name="subscription_factory")
# def subscription_factory_fixture():
#     """Fixture for creating mock subscriptions."""
#
#     def _factory(capability):
#         sub = Subscription()
#         sub.capability = capability
#         return sub
#
#     return _factory
#
#
# @pytest.fixture(name="device_factory")
# def device_factory_fixture():
#     """Fixture for creating mock devices."""
#     api = Mock(Api)
#     api.post_device_command.return_value = {"results": [{"status": "ACCEPTED"}]}
#
#     def _factory(label, capabilities, status: dict | None = None):
#         device_data = {
#             "deviceId": str(uuid4()),
#             "name": "Device Type Handler Name",
#             "label": label,
#             "deviceManufacturerCode": "9135fc86-0929-4436-bf73-5d75f523d9db",
#             "locationId": "fcd829e9-82f4-45b9-acfd-62fda029af80",
#             "components": [
#                 {
#                     "id": "main",
#                     "capabilities": [
#                         {"id": capability, "version": 1} for capability in capabilities
#                     ],
#                 }
#             ],
#             "dth": {
#                 "deviceTypeId": "b678b29d-2726-4e4f-9c3f-7aa05bd08964",
#                 "deviceTypeName": "Switch",
#                 "deviceNetworkType": "ZWAVE",
#             },
#             "type": "DTH",
#         }
#         device = DeviceEntity(api, data=device_data)
#         if status:
#             for attribute, value in status.items():
#                 device.status.apply_attribute_update("main", "", attribute, value)
#         return device
#
#     return _factory
#
#
# @pytest.fixture(name="scene_factory")
# def scene_factory_fixture(location):
#     """Fixture for creating mock devices."""
#
#     def _factory(name):
#         scene = Mock(SceneEntity)
#         scene.scene_id = str(uuid4())
#         scene.name = name
#         scene.icon = None
#         scene.color = None
#         scene.location_id = location.location_id
#         return scene
#
#     return _factory
#
#
# @pytest.fixture(name="scene")
# def scene_fixture(scene_factory):
#     """Fixture for an individual scene."""
#     return scene_factory("Test Scene")
#
#
# @pytest.fixture(name="event_factory")
# def event_factory_fixture():
#     """Fixture for creating mock devices."""
#
#     def _factory(
#         device_id,
#         event_type="DEVICE_EVENT",
#         capability="",
#         attribute="Updated",
#         value="Value",
#         data=None,
#     ):
#         event = Mock()
#         event.event_type = event_type
#         event.device_id = device_id
#         event.component_id = "main"
#         event.capability = capability
#         event.attribute = attribute
#         event.value = value
#         event.data = data
#         event.location_id = str(uuid4())
#         return event
#
#     return _factory
#
#
# @pytest.fixture(name="event_request_factory")
# def event_request_factory_fixture(event_factory):
#     """Fixture for creating mock smartapp event requests."""
#
#     def _factory(device_ids=None, events=None):
#         request = Mock()
#         request.installed_app_id = uuid4()
#         if events is None:
#             events = []
#         if device_ids:
#             events.extend([event_factory(device_id) for device_id in device_ids])
#             events.append(event_factory(uuid4()))
#             events.append(event_factory(device_ids[0], event_type="OTHER"))
#         request.events = events
#         return request
#
#     return _factory


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.smartthings.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_smartthings() -> Generator[AsyncMock]:
    """Mock a SmartThings client."""
    with (
        patch(
            "homeassistant.components.smartthings.SmartThings",
            autospec=True,
        ) as mock_client,
    ):
        client = mock_client.return_value

        yield client


@pytest.fixture(
    params=[
        "da_ac_rac_000001",
        "da_ac_rac_01001",
        "multipurpose_sensor",
        "contact_sensor",
        "base_electric_meter",
        "smart_plug",
        "vd_stv_2017_k",
        "c2c_arlo_pro_3_switch",
        "yale_push_button_deadbolt_lock",
        "ge_in_wall_smart_dimmer",
        "centralite",
        "da_ref_normal_000001",
        "vd_network_audio_002s",
        "iphone",
        "da_wm_dw_000001",
        "da_wm_wd_000001",
        "da_wm_wm_000001",
    ]
)
def devices(
    mock_smartthings: AsyncMock, request: pytest.FixtureRequest
) -> Generator[AsyncMock]:
    """Return a list of AirGradient devices."""
    mock_smartthings.get_devices.return_value = DeviceResponse.from_json(
        load_fixture(f"devices/{request.param}.json", DOMAIN)
    ).items
    mock_smartthings.get_device_status.return_value = DeviceStatus.from_json(
        load_fixture(f"device_status/{request.param}.json", DOMAIN)
    ).components
    return mock_smartthings


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Mock a config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="SmartThings",
        data={CONF_ACCESS_TOKEN: "abc", CONF_LOCATION_ID: "123"},
        version=3,
    )
