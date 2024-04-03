"""Test the Vallox integration config flow."""

from unittest.mock import patch

from vallox_websocket_api import ValloxApiException, ValloxWebsocketException

from homeassistant.components.vallox.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


async def test_form_no_input(hass: HomeAssistant) -> None:
    """Test that the form is returned with no input."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] is None


async def test_form_create_entry(hass: HomeAssistant) -> None:
    """Test that an entry is created with valid input."""
    init = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert init["type"] is FlowResultType.FORM
    assert init["errors"] is None

    with (
        patch(
            "homeassistant.components.vallox.config_flow.Vallox.fetch_metric_data",
            return_value=None,
        ),
        patch(
            "homeassistant.components.vallox.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        result = await hass.config_entries.flow.async_configure(
            init["flow_id"],
            {"host": "1.2.3.4"},
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Vallox"
    assert result["data"] == {"host": "1.2.3.4", "name": "Vallox"}
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_invalid_ip(hass: HomeAssistant) -> None:
    """Test that invalid IP error is handled."""
    init = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        init["flow_id"],
        {"host": "test.host.com"},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"host": "invalid_host"}


async def test_form_vallox_api_exception_cannot_connect(hass: HomeAssistant) -> None:
    """Test that cannot connect error is handled."""
    init = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    with patch(
        "homeassistant.components.vallox.config_flow.Vallox.fetch_metric_data",
        side_effect=ValloxApiException,
    ):
        result = await hass.config_entries.flow.async_configure(
            init["flow_id"],
            {"host": "4.3.2.1"},
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"host": "cannot_connect"}


async def test_form_os_error_cannot_connect(hass: HomeAssistant) -> None:
    """Test that cannot connect error is handled."""
    init = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    with patch(
        "homeassistant.components.vallox.config_flow.Vallox.fetch_metric_data",
        side_effect=ValloxWebsocketException,
    ):
        result = await hass.config_entries.flow.async_configure(
            init["flow_id"],
            {"host": "5.6.7.8"},
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"host": "cannot_connect"}


async def test_form_unknown_exception(hass: HomeAssistant) -> None:
    """Test that unknown exceptions are handled."""
    init = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    with patch(
        "homeassistant.components.vallox.config_flow.Vallox.fetch_metric_data",
        side_effect=Exception,
    ):
        result = await hass.config_entries.flow.async_configure(
            init["flow_id"],
            {"host": "54.12.31.41"},
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"host": "unknown"}


async def test_form_already_configured(hass: HomeAssistant) -> None:
    """Test that already configured error is handled."""
    init = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "20.40.10.30",
            CONF_NAME: "Vallox 110 MV",
        },
    )
    mock_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_configure(
        init["flow_id"],
        {"host": "20.40.10.30"},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
