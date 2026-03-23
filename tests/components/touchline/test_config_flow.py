"""Test the Touchline config flow."""

from __future__ import annotations

from unittest.mock import AsyncMock

from homeassistant import config_entries
from homeassistant.components.touchline.const import DOMAIN
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

TEST_HOST = "1.2.3.4"
TEST_DATA = {CONF_HOST: TEST_HOST}
TEST_UNIQUE_ID = "controller-1"


async def test_form_success(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test successful user flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=TEST_DATA,
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == TEST_HOST
    assert result["data"] == TEST_DATA
    assert result["result"].unique_id == TEST_UNIQUE_ID
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_cannot_connect(hass: HomeAssistant, mock_pytouchline) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    # The config flow runs validation in a thread executor.
    # If `get_number_of_devices` fails, validation fails too.
    mock_pytouchline.get_number_of_devices.side_effect = ConnectionError

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=TEST_DATA,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    # "Fix" the problem, and try again.
    mock_pytouchline.get_number_of_devices.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=TEST_DATA,
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == TEST_HOST
    assert result["data"] == TEST_DATA
    assert result["result"].unique_id == TEST_UNIQUE_ID


async def test_already_configured_by_host(hass: HomeAssistant) -> None:
    """Test abort when host is already configured."""
    MockConfigEntry(domain=DOMAIN, data=TEST_DATA).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=TEST_DATA,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_already_configured_by_unique_id(hass: HomeAssistant) -> None:
    """Test abort when unique id is already configured."""
    MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "5.6.7.8"},
        unique_id=TEST_UNIQUE_ID,
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=TEST_DATA,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_import_success(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test YAML import creates an entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_IMPORT},
        data=TEST_DATA,
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == TEST_HOST
    assert result["data"] == TEST_DATA
    assert result["result"].unique_id == TEST_UNIQUE_ID
    assert len(mock_setup_entry.mock_calls) == 1


async def test_import_cannot_connect(hass: HomeAssistant, mock_pytouchline) -> None:
    """Test YAML import aborts when it cannot connect."""
    mock_pytouchline.get_number_of_devices.side_effect = ConnectionError

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_IMPORT},
        data=TEST_DATA,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


async def test_import_already_configured(hass: HomeAssistant) -> None:
    """Test YAML import aborts when already configured."""
    MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "5.6.7.8"},
        unique_id=TEST_UNIQUE_ID,
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_IMPORT},
        data=TEST_DATA,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
