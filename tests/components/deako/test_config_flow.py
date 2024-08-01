"""Tests for the deako component config flow."""

from unittest.mock import patch

from pydeako.discover import DevicesNotFoundException
import pytest

from homeassistant import config_entries
from homeassistant.components.deako.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


@pytest.mark.asyncio
async def test_found(
    hass: HomeAssistant,
) -> None:
    """Test finding a Deako device."""

    with patch(
        "homeassistant.components.deako.config_flow.DeakoDiscoverer", autospec=True
    ) as mock_discoverer:
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        # Confirmation form
        assert result["type"] is FlowResultType.FORM

        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        await hass.async_block_till_done()

        assert result["type"] is FlowResultType.CREATE_ENTRY
        mock_discoverer.return_value.get_address.assert_called_once()


@pytest.mark.asyncio
async def test_not_found(
    hass: HomeAssistant,
) -> None:
    """Test not finding any Deako devices."""

    with patch(
        "homeassistant.components.deako.config_flow.DeakoDiscoverer", autospec=True
    ) as mock_discoverer:
        mock_discoverer.return_value.get_address.side_effect = (
            DevicesNotFoundException()
        )

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        # Confirmation form
        assert result["type"] is FlowResultType.FORM

        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        await hass.async_block_till_done()

        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "no_devices_found"
        mock_discoverer.return_value.get_address.assert_called_once()


@pytest.mark.asyncio
async def test_single_instance_allowed(hass: HomeAssistant) -> None:
    """Test single instance allowed."""
    config_entry = MockConfigEntry(domain=DOMAIN)
    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.deako.config_flow.DeakoDiscoverer", autospec=True
    ) as mock_discoverer:
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        await hass.async_block_till_done()

        assert result.get("type") is FlowResultType.ABORT
        assert result.get("reason") == "single_instance_allowed"
        mock_discoverer.return_value.get_address.assert_not_called()
