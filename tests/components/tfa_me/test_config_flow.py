"""Test the TFA.me integration: test of config_flow.py."""

# For test run: "pytest ./tests/components/tfa_me/ --cov=homeassistant.components.tfa_me --cov-report term-missing -vv"

from unittest.mock import AsyncMock, patch

import pytest

from homeassistant import config_entries, data_entry_flow
from homeassistant.components.tfa_me.const import CONF_NAME_WITH_STATION_ID, DOMAIN
from homeassistant.components.tfa_me.data import TFAmeException
from homeassistant.const import CONF_IP_ADDRESS
from homeassistant.core import HomeAssistant


@pytest.mark.asyncio
async def test_show_form(hass: HomeAssistant) -> None:
    """Test: Flow starts with form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "user"


@pytest.mark.asyncio
async def test_create_entry_success_with_ip(hass: HomeAssistant) -> None:
    """Test: Successful generation of an entry."""

    mock_client = AsyncMock()
    mock_client.get_identifier.return_value = "unique-device-123"

    with patch(
        "homeassistant.components.tfa_me.config_flow.TFAmeData",
        return_value=mock_client,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data={
                CONF_IP_ADDRESS: "192.168.1.10",
                CONF_NAME_WITH_STATION_ID: False,
            },
        )

    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["title"].startswith("TFA.me Station")
    assert result["data"][CONF_IP_ADDRESS] == "192.168.1.10"


@pytest.mark.asyncio
async def test_create_entry_with_tfa_exception(hass: HomeAssistant) -> None:
    """Test flow handles TFAmeException correctly."""

    with patch(
        "homeassistant.components.tfa_me.config_flow.TFAmeData",
        side_effect=TFAmeException("host_empty"),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data={
                CONF_IP_ADDRESS: "192.168.0.10",
                CONF_NAME_WITH_STATION_ID: True,
            },
        )

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["errors"]["base"] == "host_empty"


@pytest.mark.asyncio
async def test_invalid_ip(hass: HomeAssistant) -> None:
    """Test: Invalid Hostname/IP."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
        data={
            CONF_IP_ADDRESS: "not-an-ip",
            CONF_NAME_WITH_STATION_ID: False,
        },
    )

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["errors"][CONF_IP_ADDRESS] == "invalid_ip_host"


@pytest.mark.asyncio
async def test_invalid_name_with_station_id(hass: HomeAssistant) -> None:
    """Test: Invalid entity class, not bool."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
        data={
            CONF_IP_ADDRESS: "192.168.1.10",
            CONF_NAME_WITH_STATION_ID: 123,  # wrong value
        },
    )

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert "invalid_name_with_station_id" in result["errors"].values()


@pytest.mark.asyncio
async def test_cannot_connect(hass: HomeAssistant) -> None:
    """Test: Connections fails."""
    with patch(
        "homeassistant.components.tfa_me.config_flow.TFAmeData.get_identifier",
        side_effect=Exception("connection error"),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data={
                CONF_IP_ADDRESS: "192.168.1.10",
                CONF_NAME_WITH_STATION_ID: True,
            },
        )

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["errors"]["base"] in ("cannot_connect", "unknown")


@pytest.mark.asyncio
async def test_cannot_connect_2(hass: HomeAssistant) -> None:
    """Test: Connections fails."""
    with patch(
        "homeassistant.components.tfa_me.config_flow.TFAmeData.get_identifier",
        side_effect=Exception("connection error"),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data={
                CONF_IP_ADDRESS: "192.168.1.10",
                CONF_NAME_WITH_STATION_ID: True,
            },
        )

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["errors"]["base"] in ("cannot_connect", "unknown")


@pytest.mark.asyncio
async def test_create_entry_success_with_id(hass: HomeAssistant) -> None:
    """Test: Successful generation of an entry."""

    with patch(
        "homeassistant.components.tfa_me.TFAmeDataCoordinator.resolve_mdns",
        return_value="127.0.0.1",
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data={
                CONF_IP_ADDRESS: "012-345-678",
                CONF_NAME_WITH_STATION_ID: False,
            },
        )

    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["title"] == ("TFA.me Station '012-345-678'")
    assert result["data"][CONF_IP_ADDRESS] == "012-345-678"
