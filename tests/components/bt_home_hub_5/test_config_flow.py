"""Tests for the BT Home Hub 5 config flow."""

from unittest.mock import patch

import pytest
from pytest_homeassistant.common import MockConfigEntry
import requests

from homeassistant.components.bt_home_hub_5.const import DOMAIN
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_USER
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

MOCK_HOST = "192.168.1.254"
DEVICE_LIST = {"00:11:22:33:44:55": "Phone"}


async def test_user_flow_success(hass: HomeAssistant) -> None:
    """Test successful user step configuration."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    with (
        patch(
            "homeassistant.components.bt_home_hub_5.config_flow.get_devicelist",
            return_value=DEVICE_LIST,
        ),
        patch(
            "homeassistant.components.bt_home_hub_5.coordinator.get_devicelist",
            return_value=DEVICE_LIST,
        ),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: MOCK_HOST},
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == f"BT Home Hub 5 ({MOCK_HOST})"
    assert result2["data"] == {CONF_HOST: MOCK_HOST}


async def test_user_flow_cannot_connect(hass: HomeAssistant) -> None:
    """Test user step failure due to connection error and recover."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    with patch(
        "homeassistant.components.bt_home_hub_5.config_flow.get_devicelist",
        side_effect=requests.exceptions.ConnectionError,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: MOCK_HOST},
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}

    with (
        patch(
            "homeassistant.components.bt_home_hub_5.config_flow.get_devicelist",
            return_value=DEVICE_LIST,
        ),
        patch(
            "homeassistant.components.bt_home_hub_5.coordinator.get_devicelist",
            return_value=DEVICE_LIST,
        ),
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {CONF_HOST: MOCK_HOST},
        )
        await hass.async_block_till_done()

    assert result3["type"] is FlowResultType.CREATE_ENTRY


async def test_user_flow_none_data(hass: HomeAssistant) -> None:
    """Test user step failure when router returns None and recover."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    with patch(
        "homeassistant.components.bt_home_hub_5.config_flow.get_devicelist",
        return_value=None,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: MOCK_HOST},
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}

    with (
        patch(
            "homeassistant.components.bt_home_hub_5.config_flow.get_devicelist",
            return_value=DEVICE_LIST,
        ),
        patch(
            "homeassistant.components.bt_home_hub_5.coordinator.get_devicelist",
            return_value=DEVICE_LIST,
        ),
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {CONF_HOST: MOCK_HOST},
        )
        await hass.async_block_till_done()

    assert result3["type"] is FlowResultType.CREATE_ENTRY


async def test_user_flow_index_error(hass: HomeAssistant) -> None:
    """Test user step failure due to parsing IndexError and recover."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    with patch(
        "homeassistant.components.bt_home_hub_5.config_flow.get_devicelist",
        side_effect=IndexError("Payload parsing error"),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: MOCK_HOST},
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "unknown"}

    with (
        patch(
            "homeassistant.components.bt_home_hub_5.config_flow.get_devicelist",
            return_value=DEVICE_LIST,
        ),
        patch(
            "homeassistant.components.bt_home_hub_5.coordinator.get_devicelist",
            return_value=DEVICE_LIST,
        ),
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {CONF_HOST: MOCK_HOST},
        )
        await hass.async_block_till_done()

    assert result3["type"] is FlowResultType.CREATE_ENTRY


async def test_user_flow_unknown_exception(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test user step failure due to generic unexpected exception and recover."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    with patch(
        "homeassistant.components.bt_home_hub_5.config_flow.get_devicelist",
        side_effect=RuntimeError("Unexpected error"),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: MOCK_HOST},
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "unknown"}
    assert "Unexpected exception" in caplog.text

    with (
        patch(
            "homeassistant.components.bt_home_hub_5.config_flow.get_devicelist",
            return_value=DEVICE_LIST,
        ),
        patch(
            "homeassistant.components.bt_home_hub_5.coordinator.get_devicelist",
            return_value=DEVICE_LIST,
        ),
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {CONF_HOST: MOCK_HOST},
        )
        await hass.async_block_till_done()

    assert result3["type"] is FlowResultType.CREATE_ENTRY


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
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: MOCK_HOST},
    )

    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "already_configured"


async def test_import_flow_success(hass: HomeAssistant) -> None:
    """Test import flow from legacy YAML configuration succeeds."""
    with (
        patch(
            "homeassistant.components.bt_home_hub_5.config_flow.get_devicelist",
            return_value=DEVICE_LIST,
        ),
        patch(
            "homeassistant.components.bt_home_hub_5.coordinator.get_devicelist",
            return_value=DEVICE_LIST,
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data={CONF_HOST: MOCK_HOST},
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == f"BT Home Hub 5 ({MOCK_HOST})"
    assert result["data"] == {CONF_HOST: MOCK_HOST}


async def test_import_flow_cannot_connect(hass: HomeAssistant) -> None:
    """Test import flow aborts if router cannot be connected."""
    with patch(
        "homeassistant.components.bt_home_hub_5.config_flow.get_devicelist",
        side_effect=requests.exceptions.ConnectionError,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data={CONF_HOST: MOCK_HOST},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


async def test_import_flow_unknown_error(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test import flow aborts on generic exception."""
    with patch(
        "homeassistant.components.bt_home_hub_5.config_flow.get_devicelist",
        side_effect=RuntimeError("Fatal error"),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data={CONF_HOST: MOCK_HOST},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unknown"
    assert "Unexpected exception" in caplog.text
