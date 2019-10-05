"""Helper for HomematicIP Cloud Tests."""
import json
from pathlib import Path
from unittest.mock import Mock

from homematicip.aio.class_maps import (
    TYPE_CLASS_MAP,
    TYPE_GROUP_MAP,
    TYPE_SECURITY_EVENT_MAP,
)
from homematicip.aio.home import AsyncHome
from homematicip.home import Home

HAPID = "Mock_HAP"
AUTH_TOKEN = "1234"
HOME_JSON = "json_data/home.json"


def get_and_check_entity_basics(
    hass, default_mock_hap, entity_id, entity_name, device_model
):
    """Get and test basic device."""
    ha_entity = hass.states.get(entity_id)
    assert ha_entity is not None
    assert ha_entity.attributes["model_type"] == device_model
    assert ha_entity.name == entity_name

    hmip_device = default_mock_hap.home.template.search_mock_device_by_id(
        ha_entity.attributes["id"]
    )
    assert hmip_device is not None
    return ha_entity, hmip_device


async def async_manipulate_test_data(
    hass, hmip_device, attribute, new_value, channel=1
):
    """Set new value on hmip device."""
    if channel == 1:
        setattr(hmip_device, attribute, new_value)
    functional_channel = hmip_device.functionalChannels[channel]
    setattr(functional_channel, attribute, new_value)

    hmip_device.fire_update_event()
    await hass.async_block_till_done()


class HomeTemplate(Home):
    """Home template as builder for home mock."""

    _typeClassMap = TYPE_CLASS_MAP
    _typeGroupMap = TYPE_GROUP_MAP
    _typeSecurityEventMap = TYPE_SECURITY_EVENT_MAP

    def __init__(self, connection=None):
        """Init template with connection."""
        super().__init__(connection=connection)
        self.mock_devices = []
        self.mock_groups = []

    def init_home(self, json_path=HOME_JSON):
        """Init template with json."""
        with open(Path(__file__).parent.joinpath(json_path), encoding="utf-8") as file:
            json_state = json.load(file, encoding="UTF-8")
            self.update_home(json_state=json_state, clearConfig=True)

        self._generate_mocks()
        return self

    def _generate_mocks(self):
        """Generate mocks for groups and devices."""
        for device in self.devices:
            self.mock_devices.append(_get_mock(device))
        for group in self.groups:
            self.mock_groups.append(_get_mock(group))

    def search_mock_device_by_id(self, device_id):
        """Search a device by given id."""
        for device in self.mock_devices:
            if device.id == device_id:
                return device
        return None

    def search_mock_group_by_id(self, group_id):
        """Search a group by given id."""
        for group in self.mock_groups:
            if group.id == group_id:
                return group
        return None

    def get_async_home_mock(self):
        """Create Mock for Async_Home based on template."""
        mock_home = Mock(
            check_connection=self._connection,
            id=HAPID,
            connected=True,
            dutyCycle=self.dutyCycle,
            devices=self.mock_devices,
            groups=self.mock_groups,
            weather=self.weather,
            location=self.location,
            label="home label",
            template=self,
            spec=AsyncHome,
        )
        mock_home.name = ""
        return mock_home


def _get_mock(instance):
    """Create a mock and copy instance attributes over mock."""
    mock = Mock(spec=instance, wraps=instance)
    mock.__dict__.update(instance.__dict__)
    return mock
