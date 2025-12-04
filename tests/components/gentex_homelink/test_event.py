"""Test that the devices and entities are correctly configured."""

from unittest.mock import patch

from homelink.model.button import Button
from homelink.model.device import Device
import pytest

from homeassistant.components.gentex_homelink import async_setup_entry
from homeassistant.components.gentex_homelink.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
import homeassistant.helpers.device_registry as dr
import homeassistant.helpers.entity_registry as er

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker
from tests.typing import ClientSessionGenerator

CLIENT_ID = "1234"
CLIENT_SECRET = "5678"
TEST_CONFIG_ENTRY_ID = "ABC123"

"""Mock classes for testing."""


deviceInst = Device(id="TestDevice", name="TestDevice")
deviceInst.buttons = [
    Button(id="1", name="Button 1", device=deviceInst),
    Button(id="2", name="Button 2", device=deviceInst),
    Button(id="3", name="Button 3", device=deviceInst),
]


@pytest.fixture
async def test_setup_config(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Setup config entry."""
    with patch(
        "homeassistant.components.gentex_homelink.MQTTProvider", autospec=True
    ) as MockProvider:
        instance = MockProvider.return_value
        instance.discover.return_value = [deviceInst]
        config_entry = MockConfigEntry(
            domain=DOMAIN,
            unique_id=None,
            version=1,
            data={"auth_implementation": "gentex_homelink"},
            state=ConfigEntryState.LOADED,
        )
        config_entry.add_to_hass(hass)
        result = await async_setup_entry(hass, config_entry)

        # Assert configuration worked without errors
        assert result


async def test_device_registered(hass: HomeAssistant, test_setup_config) -> None:
    """Check if a device is registered."""
    # Assert we got a device with the test ID
    device_registry = dr.async_get(hass)
    device = device_registry.async_get_device([(DOMAIN, "TestDevice")])
    assert device
    assert device.name == "TestDevice"


def test_entities_registered(hass: HomeAssistant, test_setup_config) -> None:
    """Check if the entities are registered."""
    comp = er.async_get(hass)
    button_names = {"Button 1", "Button 2", "Button 3"}
    registered_button_names = {b.original_name for b in comp.entities.values()}

    assert button_names == registered_button_names
