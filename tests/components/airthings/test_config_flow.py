"""Test the Airthings config flow."""

from unittest.mock import patch

import airthings

from homeassistant import config_entries
from homeassistant.components.airthings.const import CONF_SECRET, DOMAIN
from homeassistant.const import CONF_ID
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo

from tests.common import MockConfigEntry

TEST_DATA = {
    CONF_ID: "client_id",
    CONF_SECRET: "secret",
}

DHCP_SERVICE_INFO_VIEW_SERIES = DhcpServiceInfo(
    hostname="airthings-view",
    ip="192.168.1.100",
    macaddress="00:00:00:00:00:00",
)

DHCP_SERVICE_INFO_HUBS = [
    DhcpServiceInfo(
        hostname="airthings-hub",
        ip="192.168.1.101",
        macaddress="D0:14:11:90:00:00",
    ),
    DhcpServiceInfo(
        hostname="airthings-hub",
        ip="192.168.1.102",
        macaddress="70:B3:D5:2A:00:00",
    ),
]


async def test_form(hass: HomeAssistant) -> None:
    """Test we get the form."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] is None

    with (
        patch(
            "airthings.get_token",
            return_value="test_token",
        ),
        patch(
            "homeassistant.components.airthings.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            TEST_DATA,
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Airthings"
    assert result2["data"] == TEST_DATA
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_invalid_auth(hass: HomeAssistant) -> None:
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "airthings.get_token",
        side_effect=airthings.AirthingsAuthError,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            TEST_DATA,
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "invalid_auth"}


async def test_form_cannot_connect(hass: HomeAssistant) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "airthings.get_token",
        side_effect=airthings.AirthingsConnectionError,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            TEST_DATA,
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_form_unknown_error(hass: HomeAssistant) -> None:
    """Test we handle unknown error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "airthings.get_token",
        side_effect=Exception,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            TEST_DATA,
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "unknown"}


async def test_flow_entry_already_exists(hass: HomeAssistant) -> None:
    """Test user input for config_entry that already exists."""

    first_entry = MockConfigEntry(
        domain="airthings",
        data=TEST_DATA,
        unique_id=TEST_DATA[CONF_ID],
    )
    first_entry.add_to_hass(hass)

    with patch("airthings.get_token", return_value="token"):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}, data=TEST_DATA
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_dhcp_flow_view_series(hass: HomeAssistant) -> None:
    """Test that DHCP discovery works for Airthings View series."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        data=DHCP_SERVICE_INFO_VIEW_SERIES,
        context={"source": config_entries.SOURCE_DHCP},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    with (
        patch(
            "homeassistant.components.airthings.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
        patch(
            "airthings.get_token",
            return_value="test_token",
        ),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            TEST_DATA,
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Airthings"
    assert result2["data"] == TEST_DATA
    assert len(mock_setup_entry.mock_calls) == 1


async def test_dhcp_flow_hub(hass: HomeAssistant) -> None:
    """Test that DHCP discovery works for Airthings Hub."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        data=DHCP_SERVICE_INFO_HUBS[0],
        context={"source": config_entries.SOURCE_DHCP},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    with (
        patch(
            "homeassistant.components.airthings.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
        patch(
            "airthings.get_token",
            return_value="test_token",
        ),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            TEST_DATA,
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Airthings"
    assert result2["data"] == TEST_DATA
    assert len(mock_setup_entry.mock_calls) == 1


async def test_dhcp_flow_hub_already_configured(hass: HomeAssistant) -> None:
    """Test that DHCP discovery fails when already configured."""

    first_entry = MockConfigEntry(
        domain="airthings",
        data=TEST_DATA,
        unique_id=TEST_DATA[CONF_ID],
    )
    first_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        data=DHCP_SERVICE_INFO_HUBS[1],
        context={"source": config_entries.SOURCE_DHCP},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
