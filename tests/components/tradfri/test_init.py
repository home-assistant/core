"""Tests for Tradfri setup."""
from unittest.mock import patch

from homeassistant import config_entries
from homeassistant.components import tradfri
from homeassistant.helpers import device_registry as dr
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
    assert progress[0]["context"] == {"source": config_entries.SOURCE_IMPORT}


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


async def test_config_json_host_imported(
    hass, mock_gateway_info, mock_entry_setup, gateway_id
):
    """Test that we import a configured host."""
    mock_gateway_info.side_effect = lambda hass, host, identity, key: {
        "host": host,
        "identity": identity,
        "key": key,
        "gateway_id": gateway_id,
    }

    with patch(
        "homeassistant.components.tradfri.load_json",
        return_value={"mock-host": {"key": "some-info"}},
    ):
        assert await async_setup_component(hass, "tradfri", {"tradfri": {}})
        await hass.async_block_till_done()

    config_entry = mock_entry_setup.mock_calls[0][1][1]
    assert config_entry.domain == "tradfri"
    assert config_entry.source == config_entries.SOURCE_IMPORT
    assert config_entry.title == "mock-host"


async def test_entry_setup_unload(hass, api_factory, gateway_id):
    """Test config entry setup and unload."""
    entry = MockConfigEntry(
        domain=tradfri.DOMAIN,
        data={
            tradfri.CONF_HOST: "mock-host",
            tradfri.CONF_IDENTITY: "mock-identity",
            tradfri.CONF_KEY: "mock-key",
            tradfri.CONF_IMPORT_GROUPS: True,
            tradfri.CONF_GATEWAY_ID: gateway_id,
        },
    )

    entry.add_to_hass(hass)
    with patch.object(
        hass.config_entries, "async_forward_entry_setup", return_value=True
    ) as setup:
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        assert setup.call_count == len(tradfri.PLATFORMS)

    dev_reg = dr.async_get(hass)
    dev_entries = dr.async_entries_for_config_entry(dev_reg, entry.entry_id)

    assert dev_entries
    dev_entry = dev_entries[0]
    assert dev_entry.identifiers == {
        (tradfri.DOMAIN, entry.data[tradfri.CONF_GATEWAY_ID])
    }
    assert dev_entry.manufacturer == tradfri.ATTR_TRADFRI_MANUFACTURER
    assert dev_entry.name == tradfri.ATTR_TRADFRI_GATEWAY
    assert dev_entry.model == tradfri.ATTR_TRADFRI_GATEWAY_MODEL

    with patch.object(
        hass.config_entries, "async_forward_entry_unload", return_value=True
    ) as unload:
        assert await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()
        assert unload.call_count == len(tradfri.PLATFORMS)
        assert api_factory.shutdown.call_count == 1
