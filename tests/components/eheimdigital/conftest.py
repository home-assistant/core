"""Configurations for the EHEIM Digital tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

from eheimdigital.classic_led_ctrl import EheimDigitalClassicLEDControl
from eheimdigital.hub import EheimDigitalHub
from eheimdigital.types import EheimDeviceType, LightMode
import pytest

from homeassistant.components.eheimdigital.const import DOMAIN
from homeassistant.const import CONF_HOST

from tests.common import MockConfigEntry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        domain=DOMAIN, data={CONF_HOST: "eheimdigital"}, unique_id="00:00:00:00:00:01"
    )


@pytest.fixture
def classic_led_ctrl_mock():
    """Mock a classicLEDcontrol device."""
    classic_led_ctrl_mock = MagicMock(spec=EheimDigitalClassicLEDControl)
    classic_led_ctrl_mock.tankconfig = [["CLASSIC_DAYLIGHT"], []]
    classic_led_ctrl_mock.mac_address = "00:00:00:00:00:01"
    classic_led_ctrl_mock.device_type = (
        EheimDeviceType.VERSION_EHEIM_CLASSIC_LED_CTRL_PLUS_E
    )
    classic_led_ctrl_mock.name = "Mock classicLEDcontrol+e"
    classic_led_ctrl_mock.aquarium_name = "Mock Aquarium"
    classic_led_ctrl_mock.light_mode = LightMode.DAYCL_MODE
    classic_led_ctrl_mock.light_level = (10, 39)
    return classic_led_ctrl_mock


@pytest.fixture
def eheimdigital_hub_mock(classic_led_ctrl_mock: MagicMock) -> Generator[AsyncMock]:
    """Mock eheimdigital hub."""
    with (
        patch(
            "homeassistant.components.eheimdigital.coordinator.EheimDigitalHub",
            spec=EheimDigitalHub,
        ) as eheimdigital_hub_mock,
        patch(
            "homeassistant.components.eheimdigital.config_flow.EheimDigitalHub",
            new=eheimdigital_hub_mock,
        ),
    ):
        eheimdigital_hub_mock.return_value.devices = {
            "00:00:00:00:00:01": classic_led_ctrl_mock
        }
        eheimdigital_hub_mock.return_value.main = classic_led_ctrl_mock
        yield eheimdigital_hub_mock
