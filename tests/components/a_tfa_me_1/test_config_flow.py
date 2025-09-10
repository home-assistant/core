"""Test the TFA.me: test of config_flow.py."""

from unittest.mock import AsyncMock, patch

import pytest

from homeassistant import config_entries, data_entry_flow
from homeassistant.components.a_tfa_me_1.const import (
    CONF_INTERVAL,
    CONF_MULTIPLE_ENTITIES,
    DOMAIN,
)
from homeassistant.components.a_tfa_me_1.data import TFAmeException
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
        "homeassistant.components.a_tfa_me_1.config_flow.TFAmeData",
        return_value=mock_client,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data={
                CONF_IP_ADDRESS: "192.168.1.10",
                CONF_INTERVAL: 60,
                CONF_MULTIPLE_ENTITIES: False,
            },
        )

    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["title"].startswith("TFA.me Station")
    assert result["data"][CONF_IP_ADDRESS] == "192.168.1.10"


@pytest.mark.asyncio
async def test_create_entry_with_tfa_exception(hass: HomeAssistant) -> None:
    """Test flow handles TFAmeException correctly."""

    with patch(
        "homeassistant.components.a_tfa_me_1.config_flow.TFAmeData",
        side_effect=TFAmeException("host_empty"),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data={
                CONF_IP_ADDRESS: "192.168.0.10",
                CONF_INTERVAL: 60,
                CONF_MULTIPLE_ENTITIES: True,
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
            CONF_INTERVAL: 60,
            CONF_MULTIPLE_ENTITIES: False,
        },
    )

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["errors"][CONF_IP_ADDRESS] == "invalid_ip_host"


@pytest.mark.asyncio
async def test_invalid_interval(hass: HomeAssistant) -> None:
    """Test: Invalid interval (<10 seconds)."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
        data={
            CONF_IP_ADDRESS: "192.168.1.10",
            CONF_INTERVAL: 5,  # Invalid value
            CONF_MULTIPLE_ENTITIES: True,
        },
    )

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert "invalid_interval" in result["errors"].values()


@pytest.mark.asyncio
async def test_invalid_interval_not_int(hass: HomeAssistant) -> None:
    """Test: Invalid interval, not integer."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
        data={
            CONF_IP_ADDRESS: "192.168.1.10",
            CONF_INTERVAL: "XXX",  # Invalid value
            CONF_MULTIPLE_ENTITIES: True,
        },
    )

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert "invalid_interval" in result["errors"].values()


@pytest.mark.asyncio
async def test_invalid_multiple_entities(hass: HomeAssistant) -> None:
    """Test: Invalid entity class, not bool."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
        data={
            CONF_IP_ADDRESS: "192.168.1.10",
            CONF_INTERVAL: 120,
            CONF_MULTIPLE_ENTITIES: 123,  # wrong value
        },
    )

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert "invalid_multiple_entities" in result["errors"].values()


@pytest.mark.asyncio
async def test_cannot_connect(hass: HomeAssistant) -> None:
    """Test: Connections fails."""
    with patch(
        "homeassistant.components.a_tfa_me_1.config_flow.TFAmeData.get_identifier",
        side_effect=Exception("connection error"),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data={
                CONF_IP_ADDRESS: "192.168.1.10",
                CONF_INTERVAL: 60,
                CONF_MULTIPLE_ENTITIES: True,
            },
        )

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["errors"]["base"] in ("cannot_connect", "unknown")


@pytest.mark.asyncio
async def test_cannot_connect_2(hass: HomeAssistant) -> None:
    """Test: Connections fails."""
    with patch(
        "homeassistant.components.a_tfa_me_1.config_flow.TFAmeData.get_identifier",
        side_effect=Exception("connection error"),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data={
                CONF_IP_ADDRESS: "192.168.1.10",
                CONF_INTERVAL: 60,
                CONF_MULTIPLE_ENTITIES: True,
            },
        )

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["errors"]["base"] in ("cannot_connect", "unknown")


@pytest.mark.asyncio
async def test_create_entry_success_with_id(hass: HomeAssistant) -> None:
    """Test: Successful generation of an entry."""

    with patch(
        "homeassistant.components.a_tfa_me_1.TFAmeDataCoordinator.resolve_mdns",
        return_value="127.0.0.1",
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data={
                CONF_IP_ADDRESS: "012-345-678",  # fast: "127.0.0.1",  # SLOW if not patched: "012-345-678",
                CONF_INTERVAL: 60,
                CONF_MULTIPLE_ENTITIES: False,
            },
        )

    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["title"] == ("TFA.me Station '012-345-678'")
    assert result["data"][CONF_IP_ADDRESS] == "012-345-678"
