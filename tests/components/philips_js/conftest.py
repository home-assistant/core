"""Standard setup for tests."""
from unittest.mock import Mock, patch

from pytest import fixture

from homeassistant import setup
from homeassistant.components.philips_js.const import DOMAIN

from . import MOCK_CONFIG, MOCK_ENTITY_ID, MOCK_NAME, MOCK_SERIAL_NO, MOCK_SYSTEM

from tests.common import MockConfigEntry, mock_device_registry


@fixture(autouse=True)
async def setup_notification(hass):
    """Configure notification system."""
    await setup.async_setup_component(hass, "persistent_notification", {})


@fixture(autouse=True)
def mock_tv():
    """Disable component actual use."""
    tv = Mock(autospec="philips_js.PhilipsTV")
    tv.sources = {}
    tv.channels = {}
    tv.system = MOCK_SYSTEM

    with patch(
        "homeassistant.components.philips_js.config_flow.PhilipsTV", return_value=tv
    ), patch("homeassistant.components.philips_js.PhilipsTV", return_value=tv):
        yield tv


@fixture
async def mock_config_entry(hass):
    """Get standard player."""
    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG, title=MOCK_NAME)
    config_entry.add_to_hass(hass)
    return config_entry


@fixture
def mock_device_reg(hass):
    """Get standard device."""
    return mock_device_registry(hass)


@fixture
async def mock_entity(hass, mock_device_reg, mock_config_entry):
    """Get standard player."""
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    return MOCK_ENTITY_ID


@fixture
def mock_device(hass, mock_device_reg, mock_entity, mock_config_entry):
    """Get standard device."""
    return mock_device_reg.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={(DOMAIN, MOCK_SERIAL_NO)},
    )
