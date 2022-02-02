"""Fixtures for pywemo."""
import asyncio
from unittest.mock import create_autospec, patch

import pytest
import pywemo

from homeassistant.components.wemo import CONF_DISCOVERY, CONF_STATIC
from homeassistant.components.wemo.const import DOMAIN
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component

MOCK_HOST = "127.0.0.1"
MOCK_PORT = 50000
MOCK_NAME = "WemoDeviceName"
MOCK_SERIAL_NUMBER = "WemoSerialNumber"
MOCK_FIRMWARE_VERSION = "WeMo_WW_2.00.XXXXX.PVT-OWRT"


@pytest.fixture(name="pywemo_model")
def pywemo_model_fixture():
    """Fixture containing a pywemo class name used by pywemo_device_fixture."""
    return "LightSwitch"


@pytest.fixture(name="pywemo_registry", autouse=True)
async def async_pywemo_registry_fixture():
    """Fixture for SubscriptionRegistry instances."""
    registry = create_autospec(pywemo.SubscriptionRegistry, instance=True)

    registry.callbacks = {}
    registry.semaphore = asyncio.Semaphore(value=0)

    def on_func(device, type_filter, callback):
        registry.callbacks[device.name] = callback
        registry.semaphore.release()

    registry.on.side_effect = on_func
    registry.is_subscribed.return_value = False

    with patch("pywemo.SubscriptionRegistry", return_value=registry):
        yield registry


@pytest.fixture(name="pywemo_discovery_responder", autouse=True)
def pywemo_discovery_responder_fixture():
    """Fixture for the DiscoveryResponder instance."""
    with patch("pywemo.ssdp.DiscoveryResponder", autospec=True):
        yield


@pytest.fixture(name="pywemo_device")
def pywemo_device_fixture(pywemo_registry, pywemo_model):
    """Fixture for WeMoDevice instances."""
    cls = getattr(pywemo, pywemo_model)
    device = create_autospec(cls, instance=True)
    device.host = MOCK_HOST
    device.port = MOCK_PORT
    device.name = MOCK_NAME
    device.serialnumber = MOCK_SERIAL_NUMBER
    device.model_name = pywemo_model.replace("LongPress", "")
    device.udn = f"uuid:{device.model_name}-1_0-{device.serialnumber}"
    device.firmware_version = MOCK_FIRMWARE_VERSION
    device.get_state.return_value = 0  # Default to Off
    device.supports_long_press.return_value = cls.supports_long_press()

    url = f"http://{MOCK_HOST}:{MOCK_PORT}/setup.xml"
    with patch("pywemo.setup_url_for_address", return_value=url), patch(
        "pywemo.discovery.device_from_description", return_value=device
    ):
        yield device


@pytest.fixture(name="wemo_entity_suffix")
def wemo_entity_suffix_fixture():
    """Fixture to select a specific entity for wemo_entity."""
    return ""


@pytest.fixture(name="wemo_entity")
async def async_wemo_entity_fixture(hass, pywemo_device, wemo_entity_suffix):
    """Fixture for a Wemo entity in hass."""
    assert await async_setup_component(
        hass,
        DOMAIN,
        {
            DOMAIN: {
                CONF_DISCOVERY: False,
                CONF_STATIC: [f"{MOCK_HOST}:{MOCK_PORT}"],
            },
        },
    )
    await hass.async_block_till_done()

    entity_registry = er.async_get(hass)
    for entry in entity_registry.entities.values():
        if entry.entity_id.endswith(wemo_entity_suffix):
            return entry

    return None
