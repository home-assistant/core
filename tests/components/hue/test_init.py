"""Test Hue setup process."""

from unittest.mock import AsyncMock, Mock, patch

import aiohue.v2 as aiohue_v2
import pytest

from homeassistant import config_entries
from homeassistant.components import hue
from homeassistant.components.hue import DOMAIN
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.setup import async_setup_component
from homeassistant.util.json import JsonArrayType

from .conftest import setup_platform

from tests.common import MockConfigEntry, async_get_persistent_notifications

# The `Wall switch with 2 controls` device and its zigbee mac
WALL_SWITCH_ID = "3ff06175-29e8-44a8-8fe7-af591b0025da"
WALL_SWITCH_ZIGBEE_MAC = "00:17:88:01:0b:aa:bb:99"


@pytest.fixture
def mock_bridge_setup():
    """Mock bridge setup."""
    with patch.object(hue, "HueBridge") as mock_bridge:
        mock_bridge.return_value.api_version = 2
        mock_bridge.return_value.async_initialize_bridge = AsyncMock(return_value=True)
        mock_bridge.return_value.api.config = Mock(
            bridge_id="mock-id",
            mac_address="00:00:00:00:00:00",
            model_id="BSB002",
            software_version="1.0.0",
            bridge_device=Mock(
                id="4a507550-8742-4087-8bf5-c2334f29891c",
                product_data=Mock(manufacturer_name="Mock"),
            ),
            spec=aiohue_v2.ConfigController,
        )
        mock_bridge.return_value.api.config.name = "Mock Hue bridge"
        yield mock_bridge.return_value


async def test_setup_with_no_config(hass: HomeAssistant) -> None:
    """Test that we do not discover anything or try to set up a bridge."""
    assert await async_setup_component(hass, hue.DOMAIN, {}) is True

    # No flows started
    assert len(hass.config_entries.flow.async_progress()) == 0

    # No configs stored
    assert not hass.config_entries.async_entries(hue.DOMAIN)


async def test_unload_entry(hass: HomeAssistant, mock_bridge_setup) -> None:
    """Test being able to unload an entry."""
    entry = MockConfigEntry(
        domain=hue.DOMAIN,
        data={"host": "0.0.0.0", "api_version": 2},
        minor_version=2,
    )
    entry.add_to_hass(hass)

    assert await async_setup_component(hass, hue.DOMAIN, {}) is True
    assert len(mock_bridge_setup.mock_calls) == 1

    entry.runtime_data = mock_bridge_setup

    async def mock_reset():
        delattr(entry, "runtime_data")
        return True

    mock_bridge_setup.async_reset = mock_reset
    assert await hass.config_entries.async_unload(entry.entry_id)
    assert not hasattr(entry, "runtime_data")


async def test_setting_unique_id(hass: HomeAssistant, mock_bridge_setup) -> None:
    """Test we set unique ID if not set yet."""
    entry = MockConfigEntry(
        domain=hue.DOMAIN,
        data={"host": "0.0.0.0", "api_version": 2},
        minor_version=2,
    )
    entry.add_to_hass(hass)
    assert await async_setup_component(hass, hue.DOMAIN, {}) is True
    assert entry.unique_id == "mock-id"


async def test_fixing_unique_id_no_other(
    hass: HomeAssistant, mock_bridge_setup
) -> None:
    """Test we set unique ID if not set yet."""
    entry = MockConfigEntry(
        domain=hue.DOMAIN,
        data={"host": "0.0.0.0", "api_version": 2},
        unique_id="invalid-id",
        minor_version=2,
    )
    entry.add_to_hass(hass)
    assert await async_setup_component(hass, hue.DOMAIN, {}) is True
    assert entry.unique_id == "mock-id"


async def test_fixing_unique_id_other_ignored(
    hass: HomeAssistant, mock_bridge_setup
) -> None:
    """Test we set unique ID if not set yet."""
    MockConfigEntry(
        domain=hue.DOMAIN,
        data={"host": "0.0.0.0", "api_version": 2},
        unique_id="mock-id",
        source=config_entries.SOURCE_IGNORE,
        minor_version=2,
    ).add_to_hass(hass)
    entry = MockConfigEntry(
        domain=hue.DOMAIN,
        data={"host": "0.0.0.0", "api_version": 2},
        unique_id="invalid-id",
        minor_version=2,
    )
    entry.add_to_hass(hass)
    assert await async_setup_component(hass, hue.DOMAIN, {}) is True
    await hass.async_block_till_done()
    assert entry.unique_id == "mock-id"
    assert hass.config_entries.async_entries() == [entry]


async def test_fixing_unique_id_other_correct(
    hass: HomeAssistant, mock_bridge_setup
) -> None:
    """Test we remove config entry if another one has correct ID."""
    correct_entry = MockConfigEntry(
        domain=hue.DOMAIN,
        data={"host": "0.0.0.0", "api_version": 2},
        unique_id="mock-id",
        minor_version=2,
    )
    correct_entry.add_to_hass(hass)
    entry = MockConfigEntry(
        domain=hue.DOMAIN,
        data={"host": "0.0.0.0", "api_version": 2},
        unique_id="invalid-id",
        minor_version=2,
    )
    entry.add_to_hass(hass)
    assert await async_setup_component(hass, hue.DOMAIN, {}) is True
    await hass.async_block_till_done()
    assert hass.config_entries.async_entries() == [correct_entry]


async def test_security_vuln_check(hass: HomeAssistant) -> None:
    """Test that we report security vulnerabilities."""
    entry = MockConfigEntry(
        domain=hue.DOMAIN, data={"host": "0.0.0.0", "api_version": 1}
    )
    entry.add_to_hass(hass)

    config = Mock(
        bridge_id="",
        mac_address="",
        model_id="BSB002",
        software_version="1935144020",
    )
    config.name = "Hue"

    with (
        patch.object(hue.migration, "is_v2_bridge", return_value=False),
        patch.object(
            hue,
            "HueBridge",
            Mock(
                return_value=Mock(
                    async_initialize_bridge=AsyncMock(return_value=True),
                    api=Mock(config=config),
                    api_version=1,
                )
            ),
        ),
    ):
        assert await async_setup_component(hass, DOMAIN, {})

    await hass.async_block_till_done()

    notifications = async_get_persistent_notifications(hass)
    assert "hue_hub_firmware" in notifications
    assert "CVE-2020-6007" in notifications["hue_hub_firmware"]["message"]


async def test_zigbee_connection(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_bridge_v2: Mock,
    v2_resources_test_data: JsonArrayType,
) -> None:
    """Test that the zigbee mac is added as a zigbee connection."""
    await mock_bridge_v2.api.load_test_data(v2_resources_test_data)
    await setup_platform(hass, mock_bridge_v2, Platform.LIGHT)

    device = device_registry.async_get_device(
        identifiers={(hue.DOMAIN, WALL_SWITCH_ID)}
    )
    assert device is not None
    assert device.connections == {(dr.CONNECTION_ZIGBEE, WALL_SWITCH_ZIGBEE_MAC)}
