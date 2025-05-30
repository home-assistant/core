"""Tests for the deako component config flow."""

from unittest.mock import MagicMock

from pydeako.discover import DevicesNotFoundException

from homeassistant.components.deako.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


async def test_found(
    hass: HomeAssistant,
    pydeako_discoverer_mock: MagicMock,
    mock_deako_setup: MagicMock,
) -> None:
    """Test finding a Deako device."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    # Confirmation form
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    pydeako_discoverer_mock.return_value.get_address.assert_called_once()

    mock_deako_setup.assert_called_once()


async def test_not_found(
    hass: HomeAssistant,
    pydeako_discoverer_mock: MagicMock,
    mock_deako_setup: MagicMock,
) -> None:
    """Test not finding any Deako devices."""
    pydeako_discoverer_mock.return_value.get_address.side_effect = (
        DevicesNotFoundException()
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    # Confirmation form
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_devices_found"
    pydeako_discoverer_mock.return_value.get_address.assert_called_once()

    mock_deako_setup.assert_not_called()


async def test_already_configured(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_deako_setup: MagicMock,
) -> None:
    """Test flow aborts when already configured."""

    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"

    mock_deako_setup.assert_not_called()
