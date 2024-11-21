"""Test Dynalite __init__."""

from unittest.mock import call, patch

import pytest
from voluptuous import MultipleInvalid

import homeassistant.components.dynalite.const as dynalite
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry


async def test_empty_config(hass: HomeAssistant) -> None:
    """Test with an empty config."""
    assert await async_setup_component(hass, dynalite.DOMAIN, {}) is True
    assert len(hass.config_entries.flow.async_progress()) == 0
    assert len(hass.config_entries.async_entries(dynalite.DOMAIN)) == 0


async def test_service_request_area_preset(hass: HomeAssistant) -> None:
    """Test requesting and area preset via service call."""
    entry = MockConfigEntry(
        domain=dynalite.DOMAIN,
        data={CONF_HOST: "1.2.3.4"},
    )
    entry2 = MockConfigEntry(
        domain=dynalite.DOMAIN,
        data={CONF_HOST: "5.6.7.8"},
    )
    entry.add_to_hass(hass)
    entry2.add_to_hass(hass)
    with (
        patch(
            "homeassistant.components.dynalite.bridge.DynaliteDevices.async_setup",
            return_value=True,
        ),
        patch(
            "dynalite_devices_lib.dynalite.Dynalite.request_area_preset",
            return_value=True,
        ) as mock_req_area_pres,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        await hass.services.async_call(
            dynalite.DOMAIN,
            "request_area_preset",
            {"host": "1.2.3.4", "area": 2},
        )
        await hass.async_block_till_done()
        mock_req_area_pres.assert_called_once_with(2, 1)
        mock_req_area_pres.reset_mock()
        await hass.services.async_call(
            dynalite.DOMAIN,
            "request_area_preset",
            {"area": 3},
        )
        await hass.async_block_till_done()
        assert mock_req_area_pres.mock_calls == [call(3, 1), call(3, 1)]
        mock_req_area_pres.reset_mock()
        await hass.services.async_call(
            dynalite.DOMAIN,
            "request_area_preset",
            {"host": "5.6.7.8", "area": 4},
        )
        await hass.async_block_till_done()
        mock_req_area_pres.assert_called_once_with(4, 1)
        mock_req_area_pres.reset_mock()
        await hass.services.async_call(
            dynalite.DOMAIN,
            "request_area_preset",
            {"host": "6.5.4.3", "area": 5},
        )
        await hass.async_block_till_done()
        mock_req_area_pres.assert_not_called()
        mock_req_area_pres.reset_mock()
        await hass.services.async_call(
            dynalite.DOMAIN,
            "request_area_preset",
            {"host": "1.2.3.4", "area": 6, "channel": 9},
        )
        await hass.async_block_till_done()
        mock_req_area_pres.assert_called_once_with(6, 9)
        mock_req_area_pres.reset_mock()
        await hass.services.async_call(
            dynalite.DOMAIN,
            "request_area_preset",
            {"host": "1.2.3.4", "area": 7},
        )
        await hass.async_block_till_done()
        mock_req_area_pres.assert_called_once_with(7, 1)


async def test_service_request_channel_level(hass: HomeAssistant) -> None:
    """Test requesting the level of a channel via service call."""
    entry = MockConfigEntry(
        domain=dynalite.DOMAIN,
        data={CONF_HOST: "1.2.3.4"},
    )
    entry2 = MockConfigEntry(
        domain=dynalite.DOMAIN,
        data={CONF_HOST: "5.6.7.8"},
    )
    entry.add_to_hass(hass)
    entry2.add_to_hass(hass)
    with (
        patch(
            "homeassistant.components.dynalite.bridge.DynaliteDevices.async_setup",
            return_value=True,
        ),
        patch(
            "dynalite_devices_lib.dynalite.Dynalite.request_channel_level",
            return_value=True,
        ) as mock_req_chan_lvl,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        assert len(hass.config_entries.async_entries(dynalite.DOMAIN)) == 2
        await hass.services.async_call(
            dynalite.DOMAIN,
            "request_channel_level",
            {"host": "1.2.3.4", "area": 2, "channel": 3},
        )
        await hass.async_block_till_done()
        mock_req_chan_lvl.assert_called_once_with(2, 3)
        mock_req_chan_lvl.reset_mock()
        with pytest.raises(MultipleInvalid):
            await hass.services.async_call(
                dynalite.DOMAIN,
                "request_channel_level",
                {"area": 3},
            )
        await hass.async_block_till_done()
        mock_req_chan_lvl.assert_not_called()
        await hass.services.async_call(
            dynalite.DOMAIN,
            "request_channel_level",
            {"area": 4, "channel": 5},
        )
        await hass.async_block_till_done()
        assert mock_req_chan_lvl.mock_calls == [call(4, 5), call(4, 5)]


async def test_unload_entry(hass: HomeAssistant) -> None:
    """Test being able to unload an entry."""
    host = "1.2.3.4"
    entry = MockConfigEntry(domain=dynalite.DOMAIN, data={CONF_HOST: host})
    entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.dynalite.bridge.DynaliteDevices.async_setup",
        return_value=True,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    assert len(hass.config_entries.async_entries(dynalite.DOMAIN)) == 1
    with patch.object(
        hass.config_entries, "async_forward_entry_unload", return_value=True
    ) as mock_unload:
        assert await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()
        assert mock_unload.call_count == len(dynalite.PLATFORMS)
        expected_calls = [call(entry, platform) for platform in dynalite.PLATFORMS]
        for cur_call in mock_unload.mock_calls:
            assert cur_call in expected_calls
