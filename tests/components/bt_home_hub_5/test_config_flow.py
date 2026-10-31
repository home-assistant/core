"""Tests for the BT Home Hub 5 config flow."""

from unittest.mock import patch

from pytest_homeassistant.common import MockConfigEntry
import requests

from homeassistant.components.bt_home_hub_5.const import DOMAIN
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_USER
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

MOCK_HOST = "192.168.1.254"
MOCK_DEVICES = {"00:11:22:33:44:55": "Test-Device"}


async def test_user_flow_success(hass: HomeAssistant) -> None:
    """Test successful user configuration."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    with (
        patch(
            "homeassistant.components.bt_home_hub_5.config_flow.get_devicelist",
            return_value=MOCK_DEVICES,
        ),
        patch(
            "homeassistant.components.bt_home_hub_5.async_setup_entry",
            return_value=None,
        ) as mock_setup_entry,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: MOCK_HOST},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == f"BT Home Hub 5 ({MOCK_HOST})"
    assert result["data"] == {CONF_HOST: MOCK_HOST}
    assert len(mock_setup_entry.mock_calls) == 1


async def test_user_flow_cannot_connect_none(hass: HomeAssistant) -> None:
    """Test user flow error when router returns None (timeout/HTTP error)."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    with patch(
        "homeassistant.components.bt_home_hub_5.config_flow.get_devicelist",
        return_value=None,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: MOCK_HOST},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_user_flow_cannot_connect_exception(hass: HomeAssistant) -> None:
    """Test user flow error on connection exception."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    with patch(
        "homeassistant.components.bt_home_hub_5.config_flow.get_devicelist",
        side_effect=requests.exceptions.ConnectionError,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: MOCK_HOST},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_user_flow_already_configured(hass: HomeAssistant) -> None:
    """Test user flow aborts when host is already configured."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: MOCK_HOST},
        title=f"BT Home Hub 5 ({MOCK_HOST})",
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: MOCK_HOST},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_import_flow_success(hass: HomeAssistant) -> None:
    """Test successful YAML import."""
    with (
        patch(
            "homeassistant.components.bt_home_hub_5.config_flow.get_devicelist",
            return_value=MOCK_DEVICES,
        ),
        patch(
            "homeassistant.components.bt_home_hub_5.async_setup_entry",
            return_value=None,
        ) as mock_setup_entry,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data={CONF_HOST: MOCK_HOST},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == f"BT Home Hub 5 ({MOCK_HOST})"
    assert result["data"] == {CONF_HOST: MOCK_HOST}
    assert len(mock_setup_entry.mock_calls) == 1


async def test_import_flow_cannot_connect(hass: HomeAssistant) -> None:
    """Test YAML import aborts when host is unreachable."""
    with patch(
        "homeassistant.components.bt_home_hub_5.config_flow.get_devicelist",
        return_value=None,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data={CONF_HOST: MOCK_HOST},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


async def test_user_flow_unknown_exception(hass: HomeAssistant) -> None:
    """Test user flow error on unexpected exception."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    with patch(
        "homeassistant.components.bt_home_hub_5.config_flow.get_devicelist",
        side_effect=Exception,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: MOCK_HOST},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "unknown"}


async def test_import_flow_unknown_exception(hass: HomeAssistant) -> None:
    """Test YAML import aborts on unexpected exception."""
    with patch(
        "homeassistant.components.bt_home_hub_5.config_flow.get_devicelist",
        side_effect=Exception,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data={CONF_HOST: MOCK_HOST},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unknown"
