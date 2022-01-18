"""Tests for the Wemo sensor entity."""

from datetime import datetime, timezone
from unittest.mock import create_autospec, patch

import pytest
from pywemo.ouimeaux_device.api.service import Action, Service

from .conftest import (
    MOCK_HOST,
    MOCK_INSIGHT_CURRENT_WATTS,
    MOCK_INSIGHT_TODAY_KWH,
    MOCK_PORT,
)
from .entity_test_helpers import EntityTestHelpers


class Template:
    """Template class used for testing individual sensor entities."""

    ENTITY_ID_SUFFIX: str
    EXPECTED_STATE_VALUE: str

    @classmethod
    @pytest.fixture
    def wemo_entity_suffix(cls):
        """Select the appropriate entity for the test."""
        return cls.ENTITY_ID_SUFFIX

    async def test_state_value(self, hass, wemo_entity):
        """Test the sensor state value."""
        assert hass.states.get(wemo_entity.entity_id).state == self.EXPECTED_STATE_VALUE


class Common:
    """Test sensors that are common among WeMo devices."""

    PYWEMO_MODEL: str

    @classmethod
    @pytest.fixture
    def pywemo_model(cls):
        """Fixture containing a pywemo class name used by pywemo_device fixture."""
        return cls.PYWEMO_MODEL

    class TestIpAddressSensor(Template):
        """Test the IP Address sensor."""

        ENTITY_ID_SUFFIX = "_ip_address"
        EXPECTED_STATE_VALUE = MOCK_HOST

    class TestUPnPPortSensor(Template):
        """Test the UPnp Port sensor."""

        ENTITY_ID_SUFFIX = "_upnp_port"
        EXPECTED_STATE_VALUE = str(MOCK_PORT)


class TestHumidifierSensors(Common):
    """Test the sensors for the Humidifier device."""

    PYWEMO_MODEL = "Humidifier"


class TestDimmerSensors(Common):
    """Test the sensors for the Dimmer device."""

    PYWEMO_MODEL = "Dimmer"


class TestMakerSensors(Common):
    """Test the sensors for the Maker device."""

    PYWEMO_MODEL = "Maker"


class TestMotionSensors(Common):
    """Test the sensors for the Motion detector device."""

    PYWEMO_MODEL = "Motion"


class TestLightSwitchSensors(Common):
    """Test the sensors for the Light Switch device."""

    PYWEMO_MODEL = "LightSwitch"


class TestInsightSensors(Common):
    """Test sensors for the Insight device."""

    PYWEMO_MODEL = "Insight"

    class TestInsightCurrentPower(Template, EntityTestHelpers):
        """Test the Current Power sensor."""

        ENTITY_ID_SUFFIX = "_current_power"
        EXPECTED_STATE_VALUE = str(MOCK_INSIGHT_CURRENT_WATTS)

    class TestInsightTodayEnergy(Template, EntityTestHelpers):
        """Test the Today Energy sensor."""

        ENTITY_ID_SUFFIX = "_today_energy"
        EXPECTED_STATE_VALUE = str(MOCK_INSIGHT_TODAY_KWH)


class TestWiFiSignalSensor(Template):
    """Test the Wifi Signal sensor."""

    @pytest.fixture
    def pywemo_device(self, pywemo_device):
        """Add GetSignalStrength action to device."""
        action = create_autospec(Action, instance=True)
        action.return_value = {"SignalStrength": "80"}
        pywemo_device.basicevent = create_autospec(Service, instance=True)
        pywemo_device.basicevent.GetSignalStrength = action
        yield pywemo_device

    ENTITY_ID_SUFFIX = "_wifi_signal"
    EXPECTED_STATE_VALUE = "-58"


class TestBootTimeSensor(Template):
    """Test the Boot Time sensor."""

    @pytest.fixture
    def pywemo_device(self, pywemo_device):
        """Add GetExtMetaInfo action to device."""
        action = create_autospec(Action, instance=True)
        action.return_value = {
            "ExtMetaInfo": "1|0|1|0|1579:8:42|4|1640081818|123456|1|Insight"
        }
        pywemo_device.metainfo = create_autospec(Service, instance=True)
        pywemo_device.metainfo.GetExtMetaInfo = action
        with patch("homeassistant.components.wemo.sensor.dt") as mock_dt:
            mock_dt.utcnow.return_value = datetime.fromtimestamp(
                1640081818, tz=timezone.utc
            )
            yield pywemo_device

    ENTITY_ID_SUFFIX = "_boot_time"
    EXPECTED_STATE_VALUE = "2021-10-16T15:08:16+00:00"
