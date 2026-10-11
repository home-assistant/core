"""Standard setup for tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, create_autospec, patch

from haphilipsjs import PhilipsTV
import pytest

from homeassistant.components.philips_js.const import (
    CONF_ALLOW_NOTIFY,
    CONF_MENU_NODES,
    DOMAIN,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from . import (
    MOCK_CONFIG,
    MOCK_CONFIG_PAIRED,
    MOCK_ENTITY_ID,
    MOCK_MENU_CURRENT,
    MOCK_MENU_ENTRY_ID,
    MOCK_MENU_ROOT,
    MOCK_MENU_SELECTED,
    MOCK_MENU_STRINGS,
    MOCK_MENU_UNIQUE_ID,
    MOCK_NAME,
    MOCK_SERIAL_NO,
    MOCK_SYSTEM,
)

from tests.common import MockConfigEntry


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Disable component setup."""
    with (
        patch(
            "homeassistant.components.philips_js.async_setup_entry", return_value=True
        ) as mock_setup_entry,
        patch(
            "homeassistant.components.philips_js.async_unload_entry", return_value=True
        ),
    ):
        yield mock_setup_entry


@pytest.fixture(autouse=True)
def mock_tv():
    """Disable component actual use."""
    tv = create_autospec(PhilipsTV)
    tv.sources = {}
    tv.channels = {}
    tv.application = None
    tv.applications = {}
    tv.system = MOCK_SYSTEM
    tv.name = MOCK_NAME
    tv.api_version = 1
    tv.api_version_detected = None
    tv.on = True
    tv.notify_change_supported = False
    tv.pairing_type = None
    tv.powerstate = None
    tv.screenstate = None
    tv.source_id = None
    tv.ambilight_current_configuration = None
    tv.ambilight_styles = {}
    tv.ambilight_cached = {}
    tv.huelamp_power = None
    tv.settings = None
    tv.settings_version = 0

    with (
        patch(
            "homeassistant.components.philips_js.config_flow.PhilipsTV", return_value=tv
        ),
        patch("homeassistant.components.philips_js.PhilipsTV", return_value=tv),
    ):
        yield tv


@pytest.fixture
async def mock_config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Get standard player."""
    config_entry = MockConfigEntry(
        domain=DOMAIN, data=MOCK_CONFIG, title=MOCK_NAME, unique_id=MOCK_SERIAL_NO
    )
    config_entry.add_to_hass(hass)
    return config_entry


@pytest.fixture
async def mock_entity(hass: HomeAssistant, mock_config_entry: MockConfigEntry) -> str:
    """Get standard player."""
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    return MOCK_ENTITY_ID


@pytest.fixture
def mock_device(
    device_registry: dr.DeviceRegistry,
    mock_entity: str,
    mock_config_entry: MockConfigEntry,
) -> dr.DeviceEntry:
    """Get standard device."""
    return device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={(DOMAIN, MOCK_SERIAL_NO)},
    )


@pytest.fixture
def mock_tv_menu(mock_tv: MagicMock) -> MagicMock:
    """Return a mock tv with menu settings."""
    mock_tv.json_feature_supported.return_value = True
    mock_tv.settings = {"node": MOCK_MENU_ROOT}
    mock_tv.getMenuItemsSettingsCurrentValue.side_effect = lambda node_ids: {
        node_id: MOCK_MENU_CURRENT.get(node_id) for node_id in node_ids
    }
    # Like the library, untranslated strings map to themselves
    mock_tv.getStringsCached.side_effect = lambda string_ids: {
        string_id: MOCK_MENU_STRINGS.get(string_id, string_id)
        for string_id in string_ids
    }
    return mock_tv


@pytest.fixture
def mock_menu_config_entry(
    hass: HomeAssistant, mock_tv_menu: MagicMock
) -> MockConfigEntry:
    """Return a config entry with selected menu nodes."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        entry_id=MOCK_MENU_ENTRY_ID,
        unique_id=MOCK_MENU_UNIQUE_ID,
        data=MOCK_CONFIG_PAIRED,
        options={CONF_ALLOW_NOTIFY: True, CONF_MENU_NODES: MOCK_MENU_SELECTED},
    )
    config_entry.add_to_hass(hass)
    return config_entry
