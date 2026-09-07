"""Tests for the Bitcoin config flow."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from homeassistant.components.bitcoin.const import DOMAIN
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_USER
from homeassistant.const import CONF_CURRENCY, CONF_DISPLAY_OPTIONS
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

YAML_CONFIG = {
    "platform": DOMAIN,
    CONF_DISPLAY_OPTIONS: ["exchangerate"],
    CONF_CURRENCY: "EUR",
}


@pytest.mark.usefixtures("mock_exchangerates", "mock_setup_entry")
async def test_user_flow(hass: HomeAssistant) -> None:
    """Test the happy path of the user flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_CURRENCY: "EUR"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Bitcoin"
    assert result["data"] == {CONF_CURRENCY: "EUR"}


async def test_user_flow_cannot_connect(
    hass: HomeAssistant, mock_exchangerates: MagicMock
) -> None:
    """Test the user flow aborts when blockchain.com cannot be reached."""
    mock_exchangerates.side_effect = OSError("boom")

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


@pytest.mark.usefixtures("mock_exchangerates", "mock_setup_entry")
async def test_user_flow_single_instance(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test only one Bitcoin config entry can be created."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"


@pytest.mark.usefixtures("mock_exchangerates", "mock_statistics")
async def test_reconfigure_flow(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test changing the currency of an existing entry."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    result = await mock_config_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_CURRENCY: "EUR"}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_config_entry.data == {CONF_CURRENCY: "EUR"}


@pytest.mark.usefixtures("mock_statistics")
async def test_reconfigure_flow_cannot_connect(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_exchangerates: MagicMock,
) -> None:
    """Test the reconfigure flow aborts when blockchain.com cannot be reached."""
    mock_config_entry.add_to_hass(hass)
    mock_exchangerates.side_effect = OSError("boom")

    result = await mock_config_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


@pytest.mark.usefixtures("mock_exchangerates")
async def test_import_flow(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test importing a YAML configuration."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_IMPORT}, data=YAML_CONFIG
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Bitcoin"
    assert result["data"] == {CONF_CURRENCY: "EUR"}
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.usefixtures("mock_exchangerates", "mock_setup_entry")
async def test_import_flow_lowercase_currency(hass: HomeAssistant) -> None:
    """Test a lowercase YAML currency is still imported."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={**YAML_CONFIG, CONF_CURRENCY: "eur"},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {CONF_CURRENCY: "EUR"}


@pytest.mark.usefixtures("mock_setup_entry")
async def test_import_flow_cannot_connect(
    hass: HomeAssistant, mock_exchangerates: MagicMock
) -> None:
    """Test the import aborts when blockchain.com cannot be reached."""
    mock_exchangerates.side_effect = OSError("boom")

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_IMPORT}, data=YAML_CONFIG
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


@pytest.mark.usefixtures("mock_exchangerates", "mock_setup_entry")
async def test_import_flow_unknown_currency(hass: HomeAssistant) -> None:
    """Test the import aborts when the YAML currency is not quoted."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={**YAML_CONFIG, CONF_CURRENCY: "XYZ"},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unknown_currency"
