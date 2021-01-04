"""Test configuration for Shelly."""
from unittest.mock import Mock, patch

import pytest

from homeassistant.components.shelly import ShellyDeviceWrapper
from homeassistant.components.shelly.const import (
    COAP,
    DATA_CONFIG_ENTRY,
    DOMAIN,
    EVENT_SHELLY_CLICK,
)
from homeassistant.core import callback as ha_callback
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry, async_mock_service, mock_device_registry

MOCK_SETTINGS = {
    "name": "Test name",
    "device": {
        "mac": "test-mac",
        "hostname": "test-host",
        "type": "SHSW-25",
        "num_outputs": 2,
    },
    "coiot": {"update_period": 15},
    "fw": "20201124-092159/v1.9.0@57ac4ad8",
    "relays": [{"btn_type": "momentary"}, {"btn_type": "toggle"}],
}

MOCK_BLOCKS = [
    Mock(sensor_ids={"inputEvent": "S", "inputEventCnt": 2}, channel="0", type="relay")
]


@pytest.fixture(autouse=True)
def mock_coap():
    """Mock out coap."""
    with patch("homeassistant.components.shelly.get_coap_context"):
        yield


@pytest.fixture
def device_reg(hass):
    """Return an empty, loaded, registry."""
    return mock_device_registry(hass)


@pytest.fixture
def calls(hass):
    """Track calls to a mock service."""
    return async_mock_service(hass, "test", "automation")


@pytest.fixture
def events(hass):
    """Yield caught shelly_click events."""
    ha_events = []
    hass.bus.async_listen(EVENT_SHELLY_CLICK, ha_callback(ha_events.append))
    yield ha_events


@pytest.fixture
async def coap_wrapper(hass):
    """Setups a coap wrapper with mocked device."""
    await async_setup_component(hass, "shelly", {})

    config_entry = MockConfigEntry(domain=DOMAIN, data={})
    config_entry.add_to_hass(hass)

    device = Mock(blocks=MOCK_BLOCKS, settings=MOCK_SETTINGS)

    hass.data[DOMAIN] = {DATA_CONFIG_ENTRY: {}}
    hass.data[DOMAIN][DATA_CONFIG_ENTRY][config_entry.entry_id] = {}
    wrapper = hass.data[DOMAIN][DATA_CONFIG_ENTRY][config_entry.entry_id][
        COAP
    ] = ShellyDeviceWrapper(hass, config_entry, device)

    await wrapper.async_setup()

    return wrapper
