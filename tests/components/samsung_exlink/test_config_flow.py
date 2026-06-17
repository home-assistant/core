"""Tests for the Samsung ExLink config flow."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from samsung_exlink import SamsungTVError

from homeassistant.components.samsung_exlink.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_DEVICE, CONF_MODEL
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import MOCK_DEVICE, MOCK_MODEL

from tests.common import MockConfigEntry


@pytest.fixture
def mock_async_setup_entry(mock_samsung_tv: MagicMock) -> Generator[AsyncMock]:
    """Prevent config-entry creation tests from setting up the integration."""

    with patch(
        "homeassistant.components.samsung_exlink.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        yield mock_setup_entry


async def test_user_form_creates_entry(
    hass: HomeAssistant,
    mock_samsung_tv: MagicMock,
    mock_async_setup_entry: AsyncMock,
) -> None:
    """Test successful config flow creates an entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    with patch(
        "homeassistant.components.samsung_exlink.config_flow.SamsungTV",
        return_value=mock_samsung_tv,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_DEVICE: MOCK_DEVICE, CONF_MODEL: MOCK_MODEL},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Samsung TV"
    assert result["data"] == {CONF_DEVICE: MOCK_DEVICE, CONF_MODEL: MOCK_MODEL}
    mock_async_setup_entry.assert_awaited_once()
    mock_samsung_tv.connect.assert_awaited_once()
    mock_samsung_tv.query_power.assert_awaited_once()
    mock_samsung_tv.disconnect.assert_awaited_once()


async def test_user_form_without_model(
    hass: HomeAssistant,
    mock_samsung_tv: MagicMock,
    mock_async_setup_entry: AsyncMock,
) -> None:
    """Test the model field is optional."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    with patch(
        "homeassistant.components.samsung_exlink.config_flow.SamsungTV",
        return_value=mock_samsung_tv,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_DEVICE: MOCK_DEVICE},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {CONF_DEVICE: MOCK_DEVICE}


@pytest.mark.parametrize(
    "exception",
    [TimeoutError, SamsungTVError("garbled response")],
)
async def test_user_form_no_tv_shows_troubleshooting(
    hass: HomeAssistant,
    mock_samsung_tv: MagicMock,
    mock_async_setup_entry: AsyncMock,
    exception: Exception,
) -> None:
    """Test a working port with no responding TV routes to troubleshooting."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    mock_samsung_tv.query_power.side_effect = exception

    with patch(
        "homeassistant.components.samsung_exlink.config_flow.SamsungTV",
        return_value=mock_samsung_tv,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_DEVICE: MOCK_DEVICE, CONF_MODEL: MOCK_MODEL},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "troubleshoot"

    # Continuing from troubleshooting returns to the user step to retry.
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    mock_samsung_tv.query_power.side_effect = None

    with patch(
        "homeassistant.components.samsung_exlink.config_flow.SamsungTV",
        return_value=mock_samsung_tv,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_DEVICE: MOCK_DEVICE, CONF_MODEL: MOCK_MODEL},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_user_form_query_unexpected_error(
    hass: HomeAssistant,
    mock_samsung_tv: MagicMock,
    mock_async_setup_entry: AsyncMock,
) -> None:
    """Test an unexpected error while querying the TV shows the unknown error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    mock_samsung_tv.query_power.side_effect = RuntimeError("boom")

    with patch(
        "homeassistant.components.samsung_exlink.config_flow.SamsungTV",
        return_value=mock_samsung_tv,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_DEVICE: MOCK_DEVICE, CONF_MODEL: MOCK_MODEL},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "unknown"}
    mock_samsung_tv.disconnect.assert_awaited_once()


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
    mock_samsung_tv: MagicMock,
    mock_async_setup_entry: AsyncMock,
) -> None:
    """Test a bad serial port keeps the user on the form with an error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    mock_samsung_tv.connect.side_effect = exception

    with patch(
        "homeassistant.components.samsung_exlink.config_flow.SamsungTV",
        return_value=mock_samsung_tv,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_DEVICE: MOCK_DEVICE, CONF_MODEL: MOCK_MODEL},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": error}

    mock_samsung_tv.connect.side_effect = None

    with patch(
        "homeassistant.components.samsung_exlink.config_flow.SamsungTV",
        return_value=mock_samsung_tv,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_DEVICE: MOCK_DEVICE, CONF_MODEL: MOCK_MODEL},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_user_duplicate_aborts(hass: HomeAssistant) -> None:
    """Test we abort if the same port is already configured."""
    entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_DEVICE: MOCK_DEVICE, CONF_MODEL: MOCK_MODEL}
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_DEVICE: MOCK_DEVICE, CONF_MODEL: MOCK_MODEL},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
