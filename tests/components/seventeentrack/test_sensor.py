"""Tests for the seventeentrack sensor."""

import os
import shutil
import unittest
from unittest.mock import patch
from typing import Union

from mock import MagicMock
from py17track.package import Package

from homeassistant.components.seventeentrack.sensor \
    import CONF_SHOW_ARCHIVED, CONF_SHOW_DELIVERED, SeventeenTrackData
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD
from homeassistant.setup import setup_component
from tests.common import get_test_home_assistant, MockDependency, \
    get_test_config_dir

VALID_CONFIG_MINIMAL = {
    'sensor': {
        'platform': 'seventeentrack',
        CONF_USERNAME: 'test',
        CONF_PASSWORD: 'test'
    }
}

INVALID_CONFIG = {
    'sensor': {
        'platform': 'seventeentrack',
        'boom': 'test',
    }
}

VALID_CONFIG_FULL = {
    'sensor': {
        'platform': 'seventeentrack',
        CONF_USERNAME: 'test',
        CONF_PASSWORD: 'test',
        CONF_SHOW_ARCHIVED: True,
        CONF_SHOW_DELIVERED: True
    }
}

VALID_CONFIG_FULL_NO_DELIVERED = {
    'sensor': {
        'platform': 'seventeentrack',
        CONF_USERNAME: 'test',
        CONF_PASSWORD: 'test',
        CONF_SHOW_ARCHIVED: False,
        CONF_SHOW_DELIVERED: False
    }
}

DEFAULT_SUMMARY = {
    "Not Found": 0,
    "In Transit": 0,
    "Expired": 0,
    "Ready to be Picked Up": 0,
    "Undelivered": 0,
    "Delivered": 0,
    "Returned": 0
}

NEW_SUMMARY_DATA = {
    "Not Found": 1,
    "In Transit": 1,
    "Expired": 1,
    "Ready to be Picked Up": 1,
    "Undelivered": 1,
    "Delivered": 1,
    "Returned": 1
}


class ClientMock:
    """Mock the py17track client to inject the ProfileMock."""

    def __init__(self, websession) -> None:
        """Mock the profile."""
        self.profile = ProfileMock()


class ProfileMock:
    """ProfileMock will mock data coming from 17track."""

    package_list = []
    login_result = True
    summary_data = DEFAULT_SUMMARY
    account_id = '123'

    @classmethod
    def reset(cls):
        """Reset data to defaults."""
        cls.package_list = []
        cls.login_result = True
        cls.summary_data = DEFAULT_SUMMARY
        cls.account_id = '123'

    def __init__(self) -> None:
        """Override Account id."""
        self.account_id = self.__class__.account_id

    async def login(self, email: str, password: str) -> bool:
        """Login mock."""
        return self.__class__.login_result

    async def packages(self, package_state: Union[int, str] = '',
                       show_archived: bool = False) -> list:
        """Packages mock."""
        return self.__class__.package_list[:]

    async def summary(self, show_archived: bool = False) -> dict:
        """Summary mock."""
        return self.__class__.summary_data


class SeventeenTrackDataMock(SeventeenTrackData):
    """Remove the throttling on the async_update function."""

    block = True
    first = True

    @classmethod
    def reset(cls):
        """Block update as throttling would do."""
        SeventeenTrackDataMock.block = True
        SeventeenTrackDataMock.first = True

    def __init__(self, hass, client, async_add_entities, scan_interval,
                 show_archived, show_delivered):
        """Override constructor to preserve _async_update."""
        super().__init__(hass, client, async_add_entities, scan_interval,
                         show_archived, show_delivered)
        self.async_update = self.new_async_update

    async def new_async_update(self):
        """Mock method for update."""
        if SeventeenTrackDataMock.block and not SeventeenTrackDataMock.first:
            return
        SeventeenTrackDataMock.first = False
        return await super()._async_update()


class TestSeventeentrack(unittest.TestCase):
    """Main test class."""

    def setUp(self):
        """Start hass."""
        self.hass = get_test_home_assistant()

    def tearDown(self):
        """Clean stuff."""
        ProfileMock.reset()
        SeventeenTrackDataMock.reset()
        self.hass.stop()
        storage_dir = get_test_config_dir('.storage')
        if os.path.isdir(storage_dir):
            shutil.rmtree(storage_dir)

    def setup_component(self, config):
        """Set up component using config."""
        ProfileMock.summary_data = {}
        assert setup_component(self.hass, 'sensor', config)
        self.hass.block_till_done()

    @MockDependency('py17track')
    @patch('py17track.Client', new=ClientMock)
    def test_full_valid_config(self, py17track_mock):
        """Ensure everything starts correctly."""
        assert setup_component(self.hass, 'sensor', VALID_CONFIG_FULL)
        self.hass.block_till_done()

        assert len(self.hass.states.entity_ids()) == len(
            ProfileMock.summary_data.keys())

    @MockDependency('py17track')
    @patch('py17track.Client', new=ClientMock)
    def test_valid_config(self, py17track_mock):
        """Ensure everything starts correctly."""
        assert setup_component(self.hass, 'sensor', VALID_CONFIG_MINIMAL)
        self.hass.block_till_done()

        assert len(self.hass.states.entity_ids()) == len(
            ProfileMock.summary_data.keys())

    @MockDependency('py17track')
    @patch('py17track.Client', new=ClientMock)
    def test_invalid_config(self, py17track_mock):
        """Ensure nothing is created when config is wrong."""
        assert setup_component(self.hass, 'sensor', INVALID_CONFIG)
        self.hass.block_till_done()

        assert not self.hass.states.entity_ids()

    @MockDependency('py17track')
    @patch('py17track.Client', new=ClientMock)
    @patch('homeassistant.components.seventeentrack.sensor.SeventeenTrackData',
           new=SeventeenTrackDataMock)
    def test_add_package(self, py17track_mock):
        """Ensure package is added correctly when user add a new package."""
        package = Package('456', 206, 'friendly name 1', 'info text 1',
                          'location 1', 206, 2)
        ProfileMock.package_list = [package]

        self.setup_component(VALID_CONFIG_MINIMAL)
        assert self.hass.states.get(
            'sensor.seventeentrack_package_456') is not None
        assert len(self.hass.states.entity_ids()) == 1

        package2 = Package('789', 206, 'friendly name 2', 'info text 2',
                           'location 2', 206, 2)
        ProfileMock.package_list = [package, package2]
        SeventeenTrackDataMock.reset()

        self.hass.async_create_task(
            self.hass.data['entity_components']['sensor'].get_entity(
                'sensor.seventeentrack_package_456')
            .async_update_ha_state(force_refresh=True))
        self.hass.block_till_done()

        assert self.hass.states.get(
            'sensor.seventeentrack_package_789') is not None
        assert len(self.hass.states.entity_ids()) == 2

    @MockDependency('py17track')
    @patch('py17track.Client', new=ClientMock)
    @patch('homeassistant.components.seventeentrack.sensor.SeventeenTrackData',
           new=SeventeenTrackDataMock)
    def test_remove_package(self, py17track_mock):
        """Ensure entity is not there anymore if package is not there."""
        package1 = Package('456', 206, 'friendly name 1', 'info text 1',
                           'location 1', 206, 2)
        package2 = Package('789', 206, 'friendly name 2', 'info text 2',
                           'location 2', 206, 2)

        ProfileMock.package_list = [package1, package2]

        self.setup_component(VALID_CONFIG_MINIMAL)

        assert self.hass.states.get(
            'sensor.seventeentrack_package_456') is not None
        assert self.hass.states.get(
            'sensor.seventeentrack_package_789') is not None
        assert len(self.hass.states.entity_ids()) == 2

        ProfileMock.package_list = [package2]
        SeventeenTrackDataMock.reset()

        self.hass.async_create_task(
            self.hass.data['entity_components']['sensor'].get_entity(
                'sensor.seventeentrack_package_456')
            .async_update_ha_state(force_refresh=True))
        self.hass.block_till_done()

        assert self.hass.states.get(
            'sensor.seventeentrack_package_456') is None

        assert self.hass.states.get(
            'sensor.seventeentrack_package_789') is not None
        assert len(self.hass.states.entity_ids()) == 1

    @MockDependency('py17track')
    @patch('py17track.Client', new=ClientMock)
    @patch('homeassistant.components.seventeentrack.sensor.SeventeenTrackData',
           new=SeventeenTrackDataMock)
    def test_friendly_name_changed(self, py17track_mock):
        """Test friendly name change"""
        package = Package('456', 206, 'friendly name 1', 'info text 1',
                          'location 1', 206, 2)
        ProfileMock.package_list = [package]

        self.setup_component(VALID_CONFIG_MINIMAL)

        assert self.hass.states.get(
            'sensor.seventeentrack_package_456') is not None
        assert len(self.hass.states.entity_ids()) == 1

        package = Package('456', 206, 'friendly name 2', 'info text 1',
                          'location 1', 206, 2)
        ProfileMock.package_list = [package]
        SeventeenTrackDataMock.reset()

        self.hass.async_create_task(
            self.hass.data['entity_components']['sensor'].get_entity(
                'sensor.seventeentrack_package_456')
            .async_update_ha_state(force_refresh=True))
        self.hass.block_till_done()

        assert self.hass.states.get(
            'sensor.seventeentrack_package_456') is not None
        entity = self.hass.data['entity_components']['sensor'].get_entity(
            'sensor.seventeentrack_package_456')
        assert entity.name == 'Seventeentrack Package: friendly name 2'
        assert len(self.hass.states.entity_ids()) == 1

    @MockDependency('py17track')
    @patch('py17track.Client', new=ClientMock)
    @patch('homeassistant.components.seventeentrack.sensor.SeventeenTrackData',
           new=SeventeenTrackDataMock)
    def test_delivered_not_shown(self, py17track_mock):
        """Ensure delivered packages are not shown."""
        package = Package('456', 206, 'friendly name 1', 'info text 1',
                          'location 1', 206, 2, 40)
        ProfileMock.package_list = [package]

        self.hass.components.persistent_notification = MagicMock()
        self.setup_component(VALID_CONFIG_FULL_NO_DELIVERED)
        assert not self.hass.states.entity_ids()
        self.hass.components.persistent_notification.create.assert_called()

    @MockDependency('py17track')
    @patch('py17track.Client', new=ClientMock)
    @patch('homeassistant.components.seventeentrack.sensor.SeventeenTrackData',
           new=SeventeenTrackDataMock)
    def test_delivered_shown(self, py17track_mock):
        """Ensure delivered packages are show when user choose to show them."""
        package = Package('456', 206, 'friendly name 1', 'info text 1',
                          'location 1', 206, 2, 40)
        ProfileMock.package_list = [package]
        self.hass.components.persistent_notification = MagicMock()
        self.setup_component(VALID_CONFIG_FULL)

        assert self.hass.states.get(
            'sensor.seventeentrack_package_456') is not None
        assert len(self.hass.states.entity_ids()) == 1
        self.hass.components.persistent_notification.create.assert_not_called()

    @MockDependency('py17track')
    @patch('py17track.Client', new=ClientMock)
    @patch('homeassistant.components.seventeentrack.sensor.SeventeenTrackData',
           new=SeventeenTrackDataMock)
    def test_becomes_delivered_not_shown_notification(self, py17track_mock):
        """Ensure notification is triggered when package becomes delivered."""
        package = Package('456', 206, 'friendly name 1', 'info text 1',
                          'location 1', 206, 2)
        ProfileMock.package_list = [package]

        self.setup_component(VALID_CONFIG_FULL_NO_DELIVERED)

        assert self.hass.states.get(
            'sensor.seventeentrack_package_456') is not None
        assert len(self.hass.states.entity_ids()) == 1

        package_delivered = Package('456', 206, 'friendly name 1',
                                    'info text 1', 'location 1', 206, 2, 40)
        ProfileMock.package_list = [package_delivered]
        self.hass.components.persistent_notification = MagicMock()
        SeventeenTrackDataMock.reset()

        self.hass.async_create_task(
            self.hass.data['entity_components']['sensor'].get_entity(
                'sensor.seventeentrack_package_456')
            .async_update_ha_state(force_refresh=True))
        self.hass.block_till_done()

        self.hass.components.persistent_notification.create.assert_called()

    @MockDependency('py17track')
    @patch('py17track.Client', new=ClientMock)
    @patch('homeassistant.components.seventeentrack.sensor.SeventeenTrackData',
           new=SeventeenTrackDataMock)
    def test_summary_no_correctly_updated(self, py17track_mock):
        """Ensure summary entities are not duplicated."""
        assert setup_component(self.hass, 'sensor', VALID_CONFIG_MINIMAL)
        self.hass.block_till_done()

        assert len(self.hass.states.entity_ids()) == 7
        for state in self.hass.states.all():
            assert state.state == '0'

        SeventeenTrackDataMock.reset()
        ProfileMock.summary_data = NEW_SUMMARY_DATA

        for entity_id in self.hass.states.entity_ids():
            self.hass.async_create_task(
                self.hass.data['entity_components']['sensor'].get_entity(
                    entity_id).async_update_ha_state(force_refresh=True))
        self.hass.block_till_done()

        assert len(self.hass.states.entity_ids()) == 7
        for state in self.hass.states.all():
            assert state.state == '1'
