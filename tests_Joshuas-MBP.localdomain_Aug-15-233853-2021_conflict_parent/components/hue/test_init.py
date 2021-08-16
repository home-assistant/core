"""Test Hue setup process."""
from unittest.mock import AsyncMock, Mock, patch

import pytest

from homeassistant import config_entries
from homeassistant.components import hue
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry


@pytest.fixture
def mock_bridge_setup():
    """Mock bridge setup."""
    with patch.object(hue, "HueBridge") as mock_bridge:
        mock_bridge.return_value.async_setup = AsyncMock(return_value=True)
        mock_bridge.return_value.api.config = Mock(bridgeid="mock-id")
        yield mock_bridge.return_value


async def test_setup_with_no_config(hass):
    """Test that we do not discover anything or try to set up a bridge."""
    assert await async_setup_component(hass, hue.DOMAIN, {}) is True

    # No flows started
    assert len(hass.config_entries.flow.async_progress()) == 0

    # No configs stored
    assert hass.data[hue.DOMAIN] == {}


async def test_unload_entry(hass, mock_bridge_setup):
    """Test being able to unload an entry."""
    entry = MockConfigEntry(domain=hue.DOMAIN, data={"host": "0.0.0.0"})
    entry.add_to_hass(hass)

    assert await async_setup_component(hass, hue.DOMAIN, {}) is True
    assert len(mock_bridge_setup.mock_calls) == 1

    mock_bridge_setup.async_reset = AsyncMock(return_value=True)
    assert await hue.async_unload_entry(hass, entry)
    assert len(mock_bridge_setup.async_reset.mock_calls) == 1
    assert hass.data[hue.DOMAIN] == {}


async def test_setting_unique_id(hass, mock_bridge_setup):
    """Test we set unique ID if not set yet."""
    entry = MockConfigEntry(domain=hue.DOMAIN, data={"host": "0.0.0.0"})
    entry.add_to_hass(hass)
    assert await async_setup_component(hass, hue.DOMAIN, {}) is True
    assert entry.unique_id == "mock-id"


async def test_fixing_unique_id_no_other(hass, mock_bridge_setup):
    """Test we set unique ID if not set yet."""
    entry = MockConfigEntry(
        domain=hue.DOMAIN, data={"host": "0.0.0.0"}, unique_id="invalid-id"
    )
    entry.add_to_hass(hass)
    assert await async_setup_component(hass, hue.DOMAIN, {}) is True
    assert entry.unique_id == "mock-id"


async def test_fixing_unique_id_other_ignored(hass, mock_bridge_setup):
    """Test we set unique ID if not set yet."""
    MockConfigEntry(
        domain=hue.DOMAIN,
        data={"host": "0.0.0.0"},
        unique_id="mock-id",
        source=config_entries.SOURCE_IGNORE,
    ).add_to_hass(hass)
    entry = MockConfigEntry(
        domain=hue.DOMAIN,
        data={"host": "0.0.0.0"},
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
        data={"host": "0.0.0.0"},
        unique_id="mock-id",
    )
    correct_entry.add_to_hass(hass)
    entry = MockConfigEntry(
        domain=hue.DOMAIN,
        data={"host": "0.0.0.0"},
        unique_id="invalid-id",
    )
    entry.add_to_hass(hass)
    assert await async_setup_component(hass, hue.DOMAIN, {}) is True
    await hass.async_block_till_done()
    assert hass.config_entries.async_entries() == [correct_entry]


async def test_security_vuln_check(hass):
    """Test that we report security vulnerabilities."""
    assert await async_setup_component(hass, "persistent_notification", {})
    entry = MockConfigEntry(domain=hue.DOMAIN, data={"host": "0.0.0.0"})
    entry.add_to_hass(hass)

    config = Mock(bridgeid="", mac="", modelid="BSB002", swversion="1935144020")
    config.name = "Hue"

    with patch.object(
        hue,
        "HueBridge",
        Mock(
            return_value=Mock(
                async_setup=AsyncMock(return_value=True), api=Mock(config=config)
            )
        ),
    ):

        assert await async_setup_component(hass, "hue", {})

    await hass.async_block_till_done()

    state = hass.states.get("persistent_notification.hue_hub_firmware")
    assert state is not None
    assert "CVE-2020-6007" in state.attributes["message"]
