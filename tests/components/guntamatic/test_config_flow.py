"""Test the guntamatic config flow."""

from unittest.mock import AsyncMock, patch

from guntamatic.heater import NoSerialException
import pytest
import requests

from homeassistant import config_entries
from homeassistant.components.guntamatic.const import DOMAIN
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo

from .conftest import MOCK_DATA, MOCK_PARSE_DATA

from tests.common import MockConfigEntry


async def test_form(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    with patch(
        "guntamatic.heater.Heater.get_data",
        return_value=MOCK_DATA,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: "1.1.1.1"},
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Guntamatic Heater"
    assert result["data"] == {CONF_HOST: "1.1.1.1"}
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    ("side_effect", "expected_error"),
    [
        (requests.exceptions.ConnectionError, "cannot_connect"),
        (NoSerialException, "bad_data"),
        (Exception("Unknown error"), "unknown"),
    ],
)
async def test_form_errors(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    side_effect: Exception,
    expected_error: str,
) -> None:
    """Test we handle errors correctly."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    with patch(
        "guntamatic.heater.Heater.parse_data",
        side_effect=side_effect,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: "1.1.1.1"},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": expected_error}

    # Recover from error
    with patch(
        "guntamatic.heater.Heater.parse_data",
        return_value=MOCK_PARSE_DATA,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: "1.1.1.1"},
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_form_already_configured(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test we abort if already configured."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "1.1.1.1"},
        unique_id=MOCK_DATA["Serial"][0],
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    with patch(
        "guntamatic.heater.Heater.parse_data",
        return_value=MOCK_PARSE_DATA,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: "1.1.1.1"},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_dhcp_discovery(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test DHCP discovery shows confirmation form."""
    with patch(
        "guntamatic.heater.Heater.parse_data",
        return_value=MOCK_PARSE_DATA,
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

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "discovery_confirm"


@pytest.mark.parametrize(
    ("side_effect", "expected_error"),
    [
        (requests.exceptions.ConnectionError, "cannot_connect"),
        (NoSerialException, "bad_data"),
    ],
)
async def test_dhcp_discovery_errors(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    side_effect: Exception,
    expected_error: str,
) -> None:
    """Test DHCP discovery shows confirmation form."""
    with patch(
        "guntamatic.heater.Heater.parse_data",
        side_effect=side_effect,
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

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == expected_error


async def test_dhcp_discovery_confirm(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test DHCP discovery confirmation creates entry."""

    with patch(
        "guntamatic.heater.Heater.parse_data",
        return_value=MOCK_PARSE_DATA,
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
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: "1.1.1.1"},
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {CONF_HOST: "1.1.1.1"}
