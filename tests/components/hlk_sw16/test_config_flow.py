"""Test the Hi-Link HLK-SW16 config flow."""

from unittest.mock import patch

from homeassistant import config_entries
from homeassistant.components.hlk_sw16.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import create_mock_hlk_sw16_connection


async def test_form(hass: HomeAssistant) -> None:
    """Test we get the form."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    conf = {
        "host": "127.0.0.1",
        "port": 8080,
    }

    mock_hlk_sw16_connection = await create_mock_hlk_sw16_connection(False)

    with (
        patch(
            "homeassistant.components.hlk_sw16.config_flow.create_hlk_sw16_connection",
            return_value=mock_hlk_sw16_connection,
        ),
        patch(
            "homeassistant.components.hlk_sw16.async_setup", return_value=True
        ) as mock_setup,
        patch(
            "homeassistant.components.hlk_sw16.async_setup_entry",
            return_value=None,
        ) as mock_setup_entry,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            conf,
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "127.0.0.1:8080"
    assert result2["data"] == {
        "host": "127.0.0.1",
        "port": 8080,
    }
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1

    mock_hlk_sw16_connection = await create_mock_hlk_sw16_connection(False)

    with patch(
        "homeassistant.components.hlk_sw16.config_flow.create_hlk_sw16_connection",
        return_value=mock_hlk_sw16_connection,
    ):
        result3 = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
    assert result3["type"] is FlowResultType.FORM
    assert result3["errors"] == {}

    result4 = await hass.config_entries.flow.async_configure(
        result3["flow_id"],
        conf,
    )

    assert result4["type"] is FlowResultType.ABORT
    assert result4["reason"] == "already_configured"


async def test_import(hass: HomeAssistant) -> None:
    """Test we import a device."""
    conf = {
        "host": "127.0.0.1",
        "port": 8080,
    }

    mock_hlk_sw16_connection = await create_mock_hlk_sw16_connection(False)

    with (
        patch(
            "homeassistant.components.hlk_sw16.config_flow.connect_client",
            return_value=mock_hlk_sw16_connection,
        ),
        patch(
            "homeassistant.components.hlk_sw16.async_setup", return_value=True
        ) as mock_setup,
        patch(
            "homeassistant.components.hlk_sw16.async_setup_entry",
            return_value=None,
        ) as mock_setup_entry,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_IMPORT}, data=conf
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "127.0.0.1:8080"
    assert result["data"] == {
        "host": "127.0.0.1",
        "port": 8080,
    }
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_import_cannot_connect(hass: HomeAssistant) -> None:
    """Test the import aborts when the device cannot be reached."""
    with patch(
        "homeassistant.components.hlk_sw16.config_flow.connect_client",
        side_effect=TimeoutError,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={"host": "127.0.0.1", "port": 8080},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


async def test_form_invalid_data(hass: HomeAssistant) -> None:
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    mock_hlk_sw16_connection = await create_mock_hlk_sw16_connection(True)

    conf = {
        "host": "127.0.0.1",
        "port": 8080,
    }

    with patch(
        "homeassistant.components.hlk_sw16.config_flow.connect_client",
        return_value=mock_hlk_sw16_connection,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            conf,
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}

    mock_hlk_sw16_connection = await create_mock_hlk_sw16_connection(False)

    with (
        patch(
            "homeassistant.components.hlk_sw16.config_flow.connect_client",
            return_value=mock_hlk_sw16_connection,
        ),
        patch("homeassistant.components.hlk_sw16.async_setup", return_value=True),
        patch(
            "homeassistant.components.hlk_sw16.async_setup_entry",
            return_value=None,
        ),
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            conf,
        )
        await hass.async_block_till_done()

    assert result3["type"] is FlowResultType.CREATE_ENTRY


async def test_form_cannot_connect(hass: HomeAssistant) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    conf = {
        "host": "127.0.0.1",
        "port": 8080,
    }

    with patch(
        "homeassistant.components.hlk_sw16.config_flow.connect_client",
        side_effect=TimeoutError,
        return_value=None,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            conf,
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}

    mock_hlk_sw16_connection = await create_mock_hlk_sw16_connection(False)

    with (
        patch(
            "homeassistant.components.hlk_sw16.config_flow.connect_client",
            return_value=mock_hlk_sw16_connection,
        ),
        patch("homeassistant.components.hlk_sw16.async_setup", return_value=True),
        patch(
            "homeassistant.components.hlk_sw16.async_setup_entry",
            return_value=None,
        ),
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            conf,
        )
        await hass.async_block_till_done()

    assert result3["type"] is FlowResultType.CREATE_ENTRY
