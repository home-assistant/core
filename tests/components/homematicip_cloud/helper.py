"""Helper for HomematicIP Cloud Tests."""
import json

from asynctest import Mock
from homematicip.aio.class_maps import (
    TYPE_CLASS_MAP,
    TYPE_GROUP_MAP,
    TYPE_SECURITY_EVENT_MAP,
)
from homematicip.aio.device import AsyncDevice
from homematicip.aio.group import AsyncGroup
from homematicip.aio.home import AsyncHome
from homematicip.home import Home

from homeassistant.components.homematicip_cloud.device import (
    ATTR_IS_GROUP,
    ATTR_MODEL_TYPE,
)

from tests.common import load_fixture

HAPID = "3014F7110000000000000001"
HAPPIN = "5678"
AUTH_TOKEN = "1234"
HOME_JSON = "homematicip_cloud.json"


def get_and_check_entity_basics(
    hass, default_mock_hap, entity_id, entity_name, device_model
):
    """Get and test basic device."""
    ha_state = hass.states.get(entity_id)
    assert ha_state is not None
    if device_model:
        assert ha_state.attributes[ATTR_MODEL_TYPE] == device_model
    assert ha_state.name == entity_name

    hmip_device = default_mock_hap.hmip_device_by_entity_id.get(entity_id)

    if hmip_device:
        if isinstance(hmip_device, AsyncDevice):
            assert ha_state.attributes[ATTR_IS_GROUP] is False
        elif isinstance(hmip_device, AsyncGroup):
            assert ha_state.attributes[ATTR_IS_GROUP] is True
    return ha_state, hmip_device


async def async_manipulate_test_data(
    hass, hmip_device, attribute, new_value, channel=1, fire_device=None
):
    """Set new value on hmip device."""
    if channel == 1:
        setattr(hmip_device, attribute, new_value)
    if hasattr(hmip_device, "functionalChannels"):
        functional_channel = hmip_device.functionalChannels[channel]
        setattr(functional_channel, attribute, new_value)

    fire_target = hmip_device if fire_device is None else fire_device

    if isinstance(fire_target, AsyncHome):
        fire_target.fire_update_event(fire_target._rawJSONData)  # pylint: disable=W0212
    else:
        fire_target.fire_update_event()

    await hass.async_block_till_done()


class HomeTemplate(Home):
    """
    Home template as builder for home mock.

    It is based on the upstream libs home class to generate hmip devices
    and groups based on the given homematicip_cloud.json.

    All further testing activities should be done by using the AsyncHome mock,
    that is generated by get_async_home_mock(self).

    The class also generated mocks of devices and groups for further testing.
    """

    _typeClassMap = TYPE_CLASS_MAP
    _typeGroupMap = TYPE_GROUP_MAP
    _typeSecurityEventMap = TYPE_SECURITY_EVENT_MAP

    def __init__(self, connection=None, home_name=""):
        """Init template with connection."""
        super().__init__(connection=connection)
        self.label = "Access Point"
        self.name = home_name
        self.model_type = "HmIP-HAP"
        self.init_json_state = None

    def init_home(self, json_path=HOME_JSON):
        """Init template with json."""
        self.init_json_state = json.loads(load_fixture(HOME_JSON), encoding="UTF-8")
        self.update_home(json_state=self.init_json_state, clearConfig=True)
        return self

    def update_home(self, json_state, clearConfig: bool = False):
        """Update home and ensure that mocks are created."""
        result = super().update_home(json_state, clearConfig)
        self._generate_mocks()
        return result

    def _generate_mocks(self):
        """Generate mocks for groups and devices."""
        mock_devices = []
        for device in self.devices:
            mock_devices.append(_get_mock(device))
        self.devices = mock_devices

        mock_groups = []
        for group in self.groups:
            mock_groups.append(_get_mock(group))
        self.groups = mock_groups

    def download_configuration(self):
        """Return the initial json config."""
        return self.init_json_state

    def get_async_home_mock(self):
        """
        Create Mock for Async_Home. based on template to be used for testing.

        It adds collections of mocked devices and groups to the home objects,
        and sets required attributes.
        """
        mock_home = Mock(
            spec=AsyncHome, wraps=self, label="Access Point", modelType="HmIP-HAP"
        )
        mock_home.__dict__.update(self.__dict__)

        return mock_home


def _get_mock(instance):
    """Create a mock and copy instance attributes over mock."""
    if isinstance(instance, Mock):
        instance.__dict__.update(instance._mock_wraps.__dict__)  # pylint: disable=W0212
        return instance

    mock = Mock(spec=instance, wraps=instance)
    mock.__dict__.update(instance.__dict__)
    return mock
