"""Test Hue setup process."""
from unittest.mock import AsyncMock, Mock, patch

import aiohue.v2 as aiohue_v2
import pytest

from homeassistant import config_entries
from homeassistant.components import hue
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry


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


async def test_setup_with_no_config(hass):
    """Test that we do not discover anything or try to set up a bridge."""
    assert await async_setup_component(hass, hue.DOMAIN, {}) is True

    # No flows started
    assert len(hass.config_entries.flow.async_progress()) == 0

    # No configs stored
    assert hue.DOMAIN not in hass.data


async def test_unload_entry(hass, mock_bridge_setup):
    """Test being able to unload an entry."""
    entry = MockConfigEntry(
        domain=hue.DOMAIN, data={"host": "0.0.0.0", "api_version": 2}
    )
    entry.add_to_hass(hass)

    assert await async_setup_component(hass, hue.DOMAIN, {}) is True
    assert len(mock_bridge_setup.mock_calls) == 1

    hass.data[hue.DOMAIN] = {entry.entry_id: mock_bridge_setup}

    async def mock_reset():
        hass.data[hue.DOMAIN].pop(entry.entry_id)
        return True

    mock_bridge_setup.async_reset = mock_reset
    assert await hue.async_unload_entry(hass, entry)
    assert hue.DOMAIN not in hass.data


async def test_setting_unique_id(hass, mock_bridge_setup):
    """Test we set unique ID if not set yet."""
    entry = MockConfigEntry(
        domain=hue.DOMAIN, data={"host": "0.0.0.0", "api_version": 2}
    )
    entry.add_to_hass(hass)
    assert await async_setup_component(hass, hue.DOMAIN, {}) is True
    assert entry.unique_id == "mock-id"


async def test_fixing_unique_id_no_other(hass, mock_bridge_setup):
    """Test we set unique ID if not set yet."""
    entry = MockConfigEntry(
        domain=hue.DOMAIN,
        data={"host": "0.0.0.0", "api_version": 2},
        unique_id="invalid-id",
    )
    entry.add_to_hass(hass)
    assert await async_setup_component(hass, hue.DOMAIN, {}) is True
    assert entry.unique_id == "mock-id"


async def test_fixing_unique_id_other_ignored(hass, mock_bridge_setup):
    """Test we set unique ID if not set yet."""
    MockConfigEntry(
        domain=hue.DOMAIN,
        data={"host": "0.0.0.0", "api_version": 2},
        unique_id="mock-id",
        source=config_entries.SOURCE_IGNORE,
    ).add_to_hass(hass)
    entry = MockConfigEntry(
        domain=hue.DOMAIN,
        data={"host": "0.0.0.0", "api_version": 2},
        unique_id="invalid-id",
    )
    entry.add_to_hass(hass)
    assert await async_setup_component(hass, hue.DOMAIN, {}) is True
    await hass.async_block_till_done()
    assert entry.unique_id == "mock-id"
    assert hass.config_entries.async_entries() == [entry]


async def test_fixing_unique_id_other_correct(hass, mock_bridge_setup):
    """Test we remove config entry if another one has correct ID."""
    correct_entry = MockConfigEntry(
        domain=hue.DOMAIN,
        data={"host": "0.0.0.0", "api_version": 2},
        unique_id="mock-id",
    )
    correct_entry.add_to_hass(hass)
    entry = MockConfigEntry(
        domain=hue.DOMAIN,
        data={"host": "0.0.0.0", "api_version": 2},
        unique_id="invalid-id",
    )
    entry.add_to_hass(hass)
    assert await async_setup_component(hass, hue.DOMAIN, {}) is True
    await hass.async_block_till_done()
    assert hass.config_entries.async_entries() == [correct_entry]


async def test_security_vuln_check(hass):
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

    with patch.object(hue.migration, "is_v2_bridge", return_value=False), patch.object(
        hue,
        "HueBridge",
        Mock(
            return_value=Mock(
                async_initialize_bridge=AsyncMock(return_value=True),
                api=Mock(config=config),
                api_version=1,
            )
        ),
    ):

        assert await async_setup_component(hass, "hue", {})

    await hass.async_block_till_done()

    state = hass.states.get("persistent_notification.hue_hub_firmware")
    assert state is not None
    assert "CVE-2020-6007" in state.attributes["message"]
