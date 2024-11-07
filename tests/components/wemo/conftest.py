"""Fixtures for pywemo."""

from collections.abc import Generator
import contextlib
from unittest.mock import MagicMock, create_autospec, patch

import pytest
import pywemo

from homeassistant.components.wemo import CONF_DISCOVERY, CONF_STATIC
from homeassistant.components.wemo.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component

MOCK_HOST = "127.0.0.1"
MOCK_PORT = 50000
MOCK_NAME = "WemoDeviceName"
MOCK_SERIAL_NUMBER = "WemoSerialNumber"
MOCK_FIRMWARE_VERSION = "WeMo_WW_2.00.XXXXX.PVT-OWRT"
MOCK_INSIGHT_CURRENT_WATTS = 0.01
MOCK_INSIGHT_TODAY_KWH = 3.33
MOCK_INSIGHT_STATE_THRESHOLD_POWER = 8.0


@pytest.fixture(name="pywemo_model")
def pywemo_model_fixture() -> str:
    """Fixture containing a pywemo class name used by pywemo_device_fixture."""
    return "LightSwitch"


@pytest.fixture(name="pywemo_registry", autouse=True)
def async_pywemo_registry_fixture() -> Generator[MagicMock]:
    """Fixture for SubscriptionRegistry instances."""
    registry = create_autospec(pywemo.SubscriptionRegistry, instance=True)

    registry.callbacks = {}

    def on_func(device, type_filter, callback):
        registry.callbacks[device.name] = callback

    registry.on.side_effect = on_func
    registry.is_subscribed.return_value = False

    with patch("pywemo.SubscriptionRegistry", return_value=registry):
        yield registry


@pytest.fixture(name="pywemo_discovery_responder", autouse=True)
def pywemo_discovery_responder_fixture():
    """Fixture for the DiscoveryResponder instance."""
    with patch("pywemo.ssdp.DiscoveryResponder", autospec=True):
        yield


@contextlib.contextmanager
def create_pywemo_device(
    pywemo_registry: MagicMock, pywemo_model: str
) -> pywemo.WeMoDevice:
    """Create a WeMoDevice instance."""
    cls = getattr(pywemo, pywemo_model)
    device = create_autospec(cls, instance=True)
    device.host = MOCK_HOST
    device.port = MOCK_PORT
    device.name = MOCK_NAME
    device.serial_number = MOCK_SERIAL_NUMBER
    device.model_name = pywemo_model.replace("LongPress", "")
    device.model = device.model_name
    device.udn = f"uuid:{device.model_name}-1_0-{device.serial_number}"
    device.firmware_version = MOCK_FIRMWARE_VERSION
    device.get_state.return_value = 0  # Default to Off
    device.supports_long_press.return_value = cls.supports_long_press()

    if issubclass(cls, pywemo.Insight):
        device.standby_state = pywemo.StandbyState.OFF
        device.current_power_watts = MOCK_INSIGHT_CURRENT_WATTS
        device.today_kwh = MOCK_INSIGHT_TODAY_KWH
        device.threshold_power_watts = MOCK_INSIGHT_STATE_THRESHOLD_POWER
        device.on_for = 1234
        device.today_on_time = 5678
        device.total_on_time = 9012

    if issubclass(cls, pywemo.Maker):
        device.has_sensor = 1
        device.sensor_state = 1
        device.switch_mode = 1
        device.switch_state = 0

    url = f"http://{MOCK_HOST}:{MOCK_PORT}/setup.xml"
    with (
        patch("pywemo.setup_url_for_address", return_value=url),
        patch("pywemo.discovery.device_from_description", return_value=device),
    ):
        yield device


@pytest.fixture(name="pywemo_device")
def pywemo_device_fixture(
    pywemo_registry: MagicMock, pywemo_model: str
) -> Generator[pywemo.WeMoDevice]:
    """Fixture for WeMoDevice instances."""
    with create_pywemo_device(pywemo_registry, pywemo_model) as pywemo_device:
        yield pywemo_device


@pytest.fixture(name="pywemo_dli_device")
def pywemo_dli_device_fixture(
    pywemo_registry: MagicMock, pywemo_model: str
) -> Generator[pywemo.WeMoDevice]:
    """Fixture for Digital Loggers emulated instances."""
    with create_pywemo_device(pywemo_registry, pywemo_model) as pywemo_dli_device:
        pywemo_dli_device.model_name = "DLI emulated Belkin Socket"
        pywemo_dli_device.serial_number = "1234567891"
        yield pywemo_dli_device


@pytest.fixture(name="wemo_entity_suffix")
def wemo_entity_suffix_fixture() -> str:
    """Fixture to select a specific entity for wemo_entity."""
    return ""


async def async_create_wemo_entity(
    hass: HomeAssistant, pywemo_device: pywemo.WeMoDevice, wemo_entity_suffix: str
) -> er.RegistryEntry | None:
    """Create a hass entity for a wemo device."""
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
        if entry.entity_id.endswith(wemo_entity_suffix or pywemo_device.name.lower()):
            return entry

    return None


@pytest.fixture(name="wemo_entity")
async def async_wemo_entity_fixture(
    hass: HomeAssistant, pywemo_device: pywemo.WeMoDevice, wemo_entity_suffix: str
) -> er.RegistryEntry | None:
    """Fixture for a Wemo entity in hass."""
    return await async_create_wemo_entity(hass, pywemo_device, wemo_entity_suffix)


@pytest.fixture(name="wemo_dli_entity")
async def async_wemo_dli_entity_fixture(
    hass: HomeAssistant, pywemo_dli_device: pywemo.WeMoDevice, wemo_entity_suffix: str
) -> er.RegistryEntry | None:
    """Fixture for a Wemo entity in hass."""
    return await async_create_wemo_entity(hass, pywemo_dli_device, wemo_entity_suffix)
