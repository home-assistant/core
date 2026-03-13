"""Test the Solarwatt config flow."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from aiohttp.client_exceptions import ClientError
import pytest

from homeassistant.components.solarwatt.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import MOCK_USER_INPUT  # aus tests/components/solarwatt/__init__.py

from tests.common import MockConfigEntry


@pytest.fixture
def mock_setup_entry() -> AsyncMock:
    """Mock async_setup_entry for Solarwatt."""
    with patch(
        "homeassistant.components.solarwatt.async_setup_entry",
        return_value=True,
    ) as mock:
        yield mock


@pytest.mark.parametrize(
    "host",
    [
        "batteryflex.fritz.box",  # Hostname
        "192.168.178.5",  # IP
    ],
)
async def test_user_flow_success(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    host: str,
) -> None:
    """Test a successful user initiated config flow with hostname and IP."""
    mock_user_input = {
        CONF_HOST: host,
        CONF_PORT: MOCK_USER_INPUT[CONF_PORT],
    }

    # Start the flow
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    # validate_input stubben
    with patch(
        "homeassistant.components.solarwatt.config_flow.validate_input",
        return_value={"serial": "0004A20B000BF3A3", "title": host},
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=mock_user_input,
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == host
    assert result2["data"] == mock_user_input

    # Unique ID should be set from serial
    assert result2["result"].unique_id == "0004A20B000BF3A3"

    # async_setup_entry should have been called once
    assert mock_setup_entry.call_count == 1


@pytest.mark.parametrize(
    ("exception", "error"),
    [
        (ClientError, "cannot_connect"),
        (Exception, "unknown"),
    ],
)
async def test_user_flow_exceptions(
    hass: HomeAssistant,
    exception: Exception,
    error: str,
) -> None:
    """Test we handle errors during the user flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM

    with patch(
        "homeassistant.components.solarwatt.config_flow.validate_input",
        side_effect=exception,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=MOCK_USER_INPUT,
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": error}


async def test_user_flow_already_configured(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test starting a flow when an entry with same serial already exists."""
    # Existing entry with same serial
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_USER_INPUT,
        unique_id="0004A20B000BF3A3",
    )
    entry.add_to_hass(hass)

    # Start new flow
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    # validate_input returns same serial → should abort as already configured
    with patch(
        "homeassistant.components.solarwatt.config_flow.validate_input",
        return_value={
            "serial": "0004A20B000BF3A3",
            "title": MOCK_USER_INPUT[CONF_HOST],
        },
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=MOCK_USER_INPUT,
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "already_configured"
    # setup should not be called wieder
    assert mock_setup_entry.call_count == 0


async def test_reauth_flow(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test the reauth flow aborts with reauth_successful."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_USER_INPUT,
        unique_id="0004A20B000BF3A3",
    )
    entry.add_to_hass(hass)

    # Start reauth via helper, HA setzt source="reauth" selbst
    result = await entry.start_reauth_flow(hass)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
