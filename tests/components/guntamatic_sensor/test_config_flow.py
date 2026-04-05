"""Test the guntamatic config flow."""

from unittest.mock import AsyncMock, patch

import requests

from homeassistant import config_entries
from homeassistant.components.guntamatic_sensor.const import DOMAIN
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo

from tests.common import MockConfigEntry


async def test_form(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.guntamatic_sensor.config_flow.Heater.get_data",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "1.1.1.1",
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Guntamatic Heater"
    assert result["data"] == {
        CONF_HOST: "1.1.1.1",
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_cannot_connect(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.guntamatic_sensor.config_flow.Heater.get_data",
        side_effect=requests.exceptions.ConnectionError,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "1.1.1.1",
            },
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    # Make sure the config flow tests finish with either an
    # FlowResultType.CREATE_ENTRY or FlowResultType.ABORT so
    # we can show the config flow is able to recover from an error.

    with patch(
        "homeassistant.components.guntamatic_sensor.config_flow.Heater.get_data",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "1.1.1.1",
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Guntamatic Heater"
    assert result["data"] == {
        CONF_HOST: "1.1.1.1",
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_empty_data(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test we handle empty data from heater."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    with patch(
        "homeassistant.components.guntamatic_sensor.config_flow.Heater.get_data",
        return_value={},
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: "1.1.1.1"},
        )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_form_unknown_error(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test we handle unknown errors."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    with patch(
        "homeassistant.components.guntamatic_sensor.config_flow.Heater.get_data",
        side_effect=Exception("Unknown error"),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: "1.1.1.1"},
        )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "unknown"}


async def test_form_already_configured(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test we abort if already configured."""
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_HOST: "1.1.1.1"})
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    with patch(
        "homeassistant.components.guntamatic_sensor.config_flow.Heater.get_data",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: "1.1.1.1"},
        )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_dhcp_discovery(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test DHCP discovery."""
    with patch(
        "homeassistant.components.guntamatic_sensor.config_flow.Heater.get_data",
        return_value={"Boiler temperature": ["14.09", "°C"]},
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_DHCP},
            data=DhcpServiceInfo(
                ip="1.1.1.1",
                hostname="kessel0001",
                macaddress="0024bd123456",
            ),
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {CONF_HOST: "1.1.1.1"}
