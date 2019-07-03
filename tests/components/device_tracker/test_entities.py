"""Tests for fan platforms."""

import unittest
import pytest

from homeassistant.components.device_tracker.config_entry import (
    BaseTrackerEntity, ScannerEntity
)
from homeassistant.components.device_tracker.const import (
    SOURCE_TYPE_ROUTER, ATTR_SOURCE_TYPE
)
from homeassistant.const import (
    STATE_HOME,
    STATE_NOT_HOME,
    ATTR_BATTERY_LEVEL
)


class TestScannerEntity(unittest.TestCase):
    """Test coverage for base ScannerEntity entity class."""

    def setUp(self):
        """Set up test data."""
        self.entity = ScannerEntity()

    def tearDown(self):
        """Tear down unit test data."""
        self.entity = None

    def test_scannerentity(self):
        """Test scanner entity methods."""
        with pytest.raises(NotImplementedError):
            assert self.entity.source_type is None
        with pytest.raises(NotImplementedError):
            assert self.entity.is_connected is None
        with pytest.raises(NotImplementedError):
            assert self.entity.state == STATE_NOT_HOME
        assert self.entity.battery_level is None


class TestScannerImplementation(ScannerEntity):
    """Test implementation of a ScannerEntity."""

    def __init__(self):
        """Init."""
        self.connected = False

    @property
    def source_type(self):
        """Return the source type, eg gps or router, of the device."""
        return SOURCE_TYPE_ROUTER

    @property
    def battery_level(self):
        """Return the battery level of the device.

        Percentage from 0-100.
        """
        return 100

    @property
    def is_connected(self):
        """Return true if the device is connected to the network."""
        return self.connected


class TestScannerEntityImpl(unittest.TestCase):
    """Test coverage for base ScannerEntity entity class."""

    def setUp(self):
        """Set up test data."""
        self.entity = TestScannerImplementation()

    def tearDown(self):
        """Tear down unit test data."""
        self.entity = None

    def test_scannerentity(self):
        """Test scanner entity methods."""
        assert self.entity.source_type == SOURCE_TYPE_ROUTER
        assert self.entity.is_connected is False
        assert self.entity.state == STATE_NOT_HOME
        self.entity.connected = True
        assert self.entity.is_connected is True
        assert self.entity.state == STATE_HOME
        assert self.entity.battery_level == 100
        assert self.entity.state_attributes == {
            ATTR_SOURCE_TYPE: SOURCE_TYPE_ROUTER,
            ATTR_BATTERY_LEVEL: 100
        }


class TestBaseTrackerEntity(unittest.TestCase):
    """Test coverage for base BaseTrackerEntity entity class."""

    def setUp(self):
        """Set up test data."""
        self.entity = BaseTrackerEntity()

    def tearDown(self):
        """Tear down unit test data."""
        self.entity = None

    def test_basetrackerentity(self):
        """Test BaseTrackerEntity entity methods."""
        with pytest.raises(NotImplementedError):
            assert self.entity.source_type is None
        assert self.entity.battery_level is None
        with pytest.raises(NotImplementedError):
            assert self.entity.state_attributes is None
