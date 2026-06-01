"""Tests for the LG TV RS-232 config flow."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

from lg_rs232_tv import TVNotRespondingError
import pytest

from homeassistant.components.lg_tv_rs232.const import CONF_SET_ID, DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_DEVICE
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import MOCK_DEVICE, MOCK_SET_ID

from tests.common import MockConfigEntry


@pytest.fixture
def mock_async_setup_entry(mock_lgtv: MagicMock) -> Generator[AsyncMock]:
    """Prevent config-entry creation tests from setting up the integration."""

    with patch(
        "homeassistant.components.lg_tv_rs232.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        yield mock_setup_entry


async def test_user_form_creates_entry(
    hass: HomeAssistant,
    mock_lgtv: MagicMock,
    mock_async_setup_entry: AsyncMock,
) -> None:
    """Test successful config flow creates an entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    with patch(
        "homeassistant.components.lg_tv_rs232.config_flow.LGTV",
        return_value=mock_lgtv,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_DEVICE: MOCK_DEVICE, CONF_SET_ID: MOCK_SET_ID},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "LG TV"
    assert result["data"] == {CONF_DEVICE: MOCK_DEVICE, CONF_SET_ID: MOCK_SET_ID}
    mock_async_setup_entry.assert_awaited_once()
    mock_lgtv.connect.assert_awaited_once()
    mock_lgtv.disconnect.assert_awaited_once()


async def test_user_form_float_set_id(
    hass: HomeAssistant,
    mock_lgtv: MagicMock,
    mock_async_setup_entry: AsyncMock,
) -> None:
    """Test that a float set_id from NumberSelector is converted to int."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    with patch(
        "homeassistant.components.lg_tv_rs232.config_flow.LGTV",
        return_value=mock_lgtv,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_DEVICE: MOCK_DEVICE, CONF_SET_ID: 1.0},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_SET_ID] == MOCK_SET_ID
    assert isinstance(result["data"][CONF_SET_ID], int)


async def test_user_form_no_tv_shows_troubleshooting(
    hass: HomeAssistant,
    mock_lgtv: MagicMock,
    mock_async_setup_entry: AsyncMock,
) -> None:
    """Test a working port with no LG TV routes to the troubleshooting step."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    mock_lgtv.connect.side_effect = TVNotRespondingError("No response from LG TV")

    with patch(
        "homeassistant.components.lg_tv_rs232.config_flow.LGTV",
        return_value=mock_lgtv,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_DEVICE: MOCK_DEVICE, CONF_SET_ID: MOCK_SET_ID},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "troubleshoot"

    # Continuing from troubleshooting returns to the user step to retry.
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    mock_lgtv.connect.side_effect = None

    with patch(
        "homeassistant.components.lg_tv_rs232.config_flow.LGTV",
        return_value=mock_lgtv,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_DEVICE: MOCK_DEVICE, CONF_SET_ID: MOCK_SET_ID},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.parametrize(
    ("exception", "error"),
    [
        (ValueError("Invalid port"), "cannot_connect"),
        (OSError("No such device"), "cannot_connect"),
        (ConnectionRefusedError("Connection refused"), "cannot_connect"),
        (RuntimeError("boom"), "unknown"),
    ],
)
async def test_user_form_bad_port_shows_error(
    hass: HomeAssistant,
    exception: Exception,
    error: str,
    mock_lgtv: MagicMock,
    mock_async_setup_entry: AsyncMock,
) -> None:
    """Test a bad serial port keeps the user on the form with an error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    mock_lgtv.connect.side_effect = exception

    with patch(
        "homeassistant.components.lg_tv_rs232.config_flow.LGTV",
        return_value=mock_lgtv,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_DEVICE: MOCK_DEVICE, CONF_SET_ID: MOCK_SET_ID},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": error}

    mock_lgtv.connect.side_effect = None

    with patch(
        "homeassistant.components.lg_tv_rs232.config_flow.LGTV",
        return_value=mock_lgtv,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_DEVICE: MOCK_DEVICE, CONF_SET_ID: MOCK_SET_ID},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_user_duplicate_aborts(hass: HomeAssistant) -> None:
    """Test we abort if the same port and set ID are already configured."""
    entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_DEVICE: MOCK_DEVICE, CONF_SET_ID: MOCK_SET_ID}
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_DEVICE: MOCK_DEVICE, CONF_SET_ID: MOCK_SET_ID},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
