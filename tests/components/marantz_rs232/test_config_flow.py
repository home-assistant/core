"""Tests for the Marantz RS-232 config flow."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.marantz_rs232.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_DEVICE, CONF_MODEL
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import MOCK_DEVICE

from tests.common import MockConfigEntry


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Prevent config-entry creation tests from setting up the integration."""
    with patch(
        "homeassistant.components.marantz_rs232.async_setup_entry",
        return_value=True,
    ) as mock_setup:
        yield mock_setup


@pytest.mark.parametrize(
    ("model_key", "title", "receiver_class", "receiver_fixture"),
    [
        ("modern", "Modern", "MarantzV2015Receiver", "mock_v2015_receiver"),
        ("sr7002", "SR7002", "MarantzV2007Receiver", "mock_v2007_receiver"),
        ("sr9300", "SR9300", "MarantzV2003Receiver", "mock_v2003_receiver"),
    ],
)
async def test_user_form_creates_entry(
    hass: HomeAssistant,
    request: pytest.FixtureRequest,
    mock_setup_entry: AsyncMock,
    model_key: str,
    title: str,
    receiver_class: str,
    receiver_fixture: str,
) -> None:
    """Test a successful config flow creates an entry for each protocol."""
    receiver = request.getfixturevalue(receiver_fixture)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM

    with patch(
        f"homeassistant.components.marantz_rs232.config_flow.{receiver_class}",
        return_value=receiver,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_DEVICE: MOCK_DEVICE, CONF_MODEL: model_key},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == title
    assert result["data"] == {CONF_DEVICE: MOCK_DEVICE, CONF_MODEL: model_key}
    mock_setup_entry.assert_awaited_once()
    receiver.connect.assert_awaited_once()
    receiver.disconnect.assert_awaited_once()


@pytest.mark.parametrize(
    ("exception", "error"),
    [
        (ValueError("Invalid port"), "cannot_connect"),
        (ConnectionError("No response"), "cannot_connect"),
        (OSError("No such device"), "cannot_connect"),
        (RuntimeError("boom"), "unknown"),
    ],
)
async def test_user_form_error_recovers(
    hass: HomeAssistant,
    mock_v2015_receiver: AsyncMock,
    exception: Exception,
    error: str,
) -> None:
    """Test the user step reports errors and recovers on retry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    mock_v2015_receiver.connect.side_effect = exception

    with patch(
        "homeassistant.components.marantz_rs232.config_flow.MarantzV2015Receiver",
        return_value=mock_v2015_receiver,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_DEVICE: MOCK_DEVICE, CONF_MODEL: "modern"},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": error}

    mock_v2015_receiver.connect.side_effect = None

    with (
        patch(
            "homeassistant.components.marantz_rs232.config_flow.MarantzV2015Receiver",
            return_value=mock_v2015_receiver,
        ),
        patch(
            "homeassistant.components.marantz_rs232.async_setup_entry",
            return_value=True,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_DEVICE: MOCK_DEVICE, CONF_MODEL: "modern"},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_user_duplicate_port_aborts(hass: HomeAssistant) -> None:
    """Test we abort if the same port is already configured."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_DEVICE: MOCK_DEVICE, CONF_MODEL: "modern"},
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_DEVICE: MOCK_DEVICE, CONF_MODEL: "modern"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
