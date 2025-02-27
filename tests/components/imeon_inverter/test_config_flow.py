"""Test the Imeon Inverter config flow."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock

import pytest

from homeassistant import config_entries
from homeassistant.components.imeon_inverter.const import DOMAIN
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import TEST_ERROR, TEST_SERIAL, TEST_USER_INPUT

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("mock_async_setup_entry")
async def test_form(
    hass: HomeAssistant,
    mock_async_setup_entry: Generator[AsyncMock],
) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"], TEST_USER_INPUT
    )
    await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == TEST_USER_INPUT[CONF_ADDRESS]
    assert result2["data"] == TEST_USER_INPUT
    assert mock_async_setup_entry.call_count == 1


async def test_form_invalid_auth(
    hass: HomeAssistant, mock_imeon_inverter: Generator[MagicMock]
) -> None:
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    mock_imeon_inverter.login.return_value = False

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"], TEST_USER_INPUT
    )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "invalid_auth"}

    mock_imeon_inverter.login.return_value = True

    result3 = await hass.config_entries.flow.async_configure(
        result["flow_id"], TEST_USER_INPUT
    )

    assert result3["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.parametrize(("error", "expected"), TEST_ERROR)
async def test_form_exception(
    hass: HomeAssistant,
    mock_imeon_inverter: Generator[MagicMock],
    error: Exception,
    expected: str,
) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    mock_imeon_inverter.login.side_effect = error

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"], TEST_USER_INPUT
    )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": expected}

    mock_imeon_inverter.login.side_effect = None

    result3 = await hass.config_entries.flow.async_configure(
        result["flow_id"], TEST_USER_INPUT
    )

    assert result3["type"] is FlowResultType.CREATE_ENTRY


async def test_manual_setup_already_exists(
    hass: HomeAssistant,
    mock_async_setup_entry: Generator[AsyncMock],
    mock_imeon_inverter: Generator[MagicMock],
) -> None:
    """Test that a flow with an existing host aborts."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=TEST_SERIAL,
        data=TEST_USER_INPUT,
    )

    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    mock_imeon_inverter.get_serial.return_value = TEST_SERIAL

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"], TEST_USER_INPUT
    )

    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "already_configured"


async def test_get_serial_timeout(
    hass: HomeAssistant, mock_imeon_inverter: Generator[MagicMock]
) -> None:
    """Test we handle timeout exception for getting serial."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    mock_imeon_inverter.get_serial.side_effect = TimeoutError

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"], TEST_USER_INPUT
    )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}

    mock_imeon_inverter.get_serial.side_effect = None

    result3 = await hass.config_entries.flow.async_configure(
        result["flow_id"], TEST_USER_INPUT
    )

    assert result3["type"] is FlowResultType.CREATE_ENTRY
