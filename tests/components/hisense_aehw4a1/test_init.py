"""Tests for the Hisense AEH-W4A1 init file."""
from unittest.mock import patch

from pyaehw4a1 import exceptions

from homeassistant import config_entries, data_entry_flow
from homeassistant.components import hisense_aehw4a1
from homeassistant.setup import async_setup_component


async def test_creating_entry_sets_up_climate_discovery(hass):
    """Test setting up Hisense AEH-W4A1 loads the climate component."""
    with patch(
        "homeassistant.components.hisense_aehw4a1.config_flow.AehW4a1.discovery",
        return_value=["1.2.3.4"],
    ), patch(
        "homeassistant.components.hisense_aehw4a1.climate.async_setup_entry",
        return_value=True,
    ) as mock_setup:
        result = await hass.config_entries.flow.async_init(
            hisense_aehw4a1.DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        # Confirmation form
        assert result["type"] == data_entry_flow.FlowResultType.FORM

        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY

        await hass.async_block_till_done()

    assert len(mock_setup.mock_calls) == 1


async def test_configuring_hisense_w4a1_create_entry(hass):
    """Test that specifying config will create an entry."""
    with patch(
        "homeassistant.components.hisense_aehw4a1.config_flow.AehW4a1.check",
        return_value=True,
    ), patch(
        "homeassistant.components.hisense_aehw4a1.async_setup_entry",
        return_value=True,
    ) as mock_setup:
        await async_setup_component(
            hass,
            hisense_aehw4a1.DOMAIN,
            {"hisense_aehw4a1": {"ip_address": ["1.2.3.4"]}},
        )
        await hass.async_block_till_done()

    assert len(mock_setup.mock_calls) == 1


async def test_configuring_hisense_w4a1_not_creates_entry_for_device_not_found(hass):
    """Test that specifying config will not create an entry."""
    with patch(
        "homeassistant.components.hisense_aehw4a1.config_flow.AehW4a1.check",
        side_effect=exceptions.ConnectionError,
    ), patch(
        "homeassistant.components.hisense_aehw4a1.async_setup_entry",
        return_value=True,
    ) as mock_setup:
        await async_setup_component(
            hass,
            hisense_aehw4a1.DOMAIN,
            {"hisense_aehw4a1": {"ip_address": ["1.2.3.4"]}},
        )
        await hass.async_block_till_done()

    assert len(mock_setup.mock_calls) == 0


async def test_configuring_hisense_w4a1_not_creates_entry_for_empty_import(hass):
    """Test that specifying config will not create an entry."""
    with patch(
        "homeassistant.components.hisense_aehw4a1.async_setup_entry",
        return_value=True,
    ) as mock_setup:
        await async_setup_component(hass, hisense_aehw4a1.DOMAIN, {})
        await hass.async_block_till_done()

    assert len(mock_setup.mock_calls) == 0
