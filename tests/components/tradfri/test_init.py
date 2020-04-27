"""Tests for Tradfri setup."""
from asynctest import patch

from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry


async def test_config_yaml_host_not_imported(hass):
    """Test that we don't import a configured host."""
    MockConfigEntry(domain="tradfri", data={"host": "mock-host"}).add_to_hass(hass)

    with patch(
        "homeassistant.components.tradfri.load_json", return_value={}
    ), patch.object(hass.config_entries.flow, "async_init") as mock_init:
        assert await async_setup_component(
            hass, "tradfri", {"tradfri": {"host": "mock-host"}}
        )
        await hass.async_block_till_done()

    assert len(mock_init.mock_calls) == 0


async def test_config_yaml_host_imported(hass):
    """Test that we import a configured host."""
    with patch("homeassistant.components.tradfri.load_json", return_value={}):
        assert await async_setup_component(
            hass, "tradfri", {"tradfri": {"host": "mock-host"}}
        )
        await hass.async_block_till_done()

    progress = hass.config_entries.flow.async_progress()
    assert len(progress) == 1
    assert progress[0]["handler"] == "tradfri"
    assert progress[0]["context"] == {"source": "import"}


async def test_config_json_host_not_imported(hass):
    """Test that we don't import a configured host."""
    MockConfigEntry(domain="tradfri", data={"host": "mock-host"}).add_to_hass(hass)

    with patch(
        "homeassistant.components.tradfri.load_json",
        return_value={"mock-host": {"key": "some-info"}},
    ), patch.object(hass.config_entries.flow, "async_init") as mock_init:
        assert await async_setup_component(hass, "tradfri", {"tradfri": {}})
        await hass.async_block_till_done()

    assert len(mock_init.mock_calls) == 0


async def test_config_json_host_imported(hass, mock_gateway_info, mock_entry_setup):
    """Test that we import a configured host."""
    mock_gateway_info.side_effect = lambda hass, host, identity, key: {
        "host": host,
        "identity": identity,
        "key": key,
        "gateway_id": "mock-gateway",
    }

    with patch(
        "homeassistant.components.tradfri.load_json",
        return_value={"mock-host": {"key": "some-info"}},
    ):
        assert await async_setup_component(hass, "tradfri", {"tradfri": {}})
        await hass.async_block_till_done()

    config_entry = mock_entry_setup.mock_calls[0][1][1]
    assert config_entry.domain == "tradfri"
    assert config_entry.source == "import"
    assert config_entry.title == "mock-host"
