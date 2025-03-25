"""Tests for the bosch_alarm config flow."""

import asyncio
from unittest.mock import AsyncMock

import pytest

from homeassistant import config_entries
from homeassistant.components.bosch_alarm.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_HOST, CONF_MODEL, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import MockBoschAlarmConfig

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("bosch_alarm_test_data")
@pytest.mark.parametrize(
    ("bosch_alarm_test_data"),
    [
        "Solution 3000",
        "AMAX 3000",
        "B5512 (US1B)",
    ],
    indirect=["bosch_alarm_test_data"],
)
async def test_form_user(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    bosch_alarm_test_data: MockBoschAlarmConfig,
) -> None:
    """Test the config flow for bosch_alarm."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "1.1.1.1", CONF_PORT: 7700},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "auth"
    assert result["errors"] == {}
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        bosch_alarm_test_data.config,
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == f"Bosch {bosch_alarm_test_data.model}"
    assert result["data"] == {
        CONF_HOST: "1.1.1.1",
        CONF_PORT: 7700,
        CONF_MODEL: bosch_alarm_test_data.model,
        **bosch_alarm_test_data.config,
    }
    if bosch_alarm_test_data.serial:
        assert result["context"]["unique_id"] == str(bosch_alarm_test_data.serial)
    else:
        assert "unique_id" not in result["context"]

    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.usefixtures("bosch_alarm_test_data")
@pytest.mark.parametrize(
    ("bosch_alarm_test_data", "exception", "message"),
    [
        ("Solution 3000", asyncio.exceptions.TimeoutError(), "cannot_connect"),
        ("Solution 3000", Exception(), "unknown"),
        ("AMAX 3000", asyncio.exceptions.TimeoutError(), "cannot_connect"),
        ("AMAX 3000", Exception(), "unknown"),
        ("B5512 (US1B)", asyncio.exceptions.TimeoutError(), "cannot_connect"),
        ("B5512 (US1B)", Exception(), "unknown"),
    ],
    indirect=["bosch_alarm_test_data"],
)
async def test_form_exceptions(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    bosch_alarm_test_data: MockBoschAlarmConfig,
    exception: Exception,
    message: str,
) -> None:
    """Test we handle exceptions correctly."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}
    bosch_alarm_test_data.side_effect = exception
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "1.1.1.1", CONF_PORT: 7700},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": message}

    bosch_alarm_test_data.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "1.1.1.1", CONF_PORT: 7700},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "auth"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        bosch_alarm_test_data.config,
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY

    await hass.async_block_till_done()
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.usefixtures("bosch_alarm_test_data")
@pytest.mark.parametrize(
    ("bosch_alarm_test_data", "exception", "message"),
    [
        ("Solution 3000", PermissionError(), "invalid_auth"),
        ("Solution 3000", asyncio.exceptions.TimeoutError(), "cannot_connect"),
        ("Solution 3000", Exception(), "unknown"),
        ("AMAX 3000", PermissionError(), "invalid_auth"),
        ("AMAX 3000", asyncio.exceptions.TimeoutError(), "cannot_connect"),
        ("AMAX 3000", Exception(), "unknown"),
        ("B5512 (US1B)", PermissionError(), "invalid_auth"),
        ("B5512 (US1B)", asyncio.exceptions.TimeoutError(), "cannot_connect"),
        ("B5512 (US1B)", Exception(), "unknown"),
    ],
    indirect=["bosch_alarm_test_data"],
)
async def test_form_exceptions_user(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    bosch_alarm_test_data: MockBoschAlarmConfig,
    exception: Exception,
    message: str,
) -> None:
    """Test we handle exceptions correctly."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "1.1.1.1", CONF_PORT: 7700},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "auth"
    assert result["errors"] == {}
    bosch_alarm_test_data.side_effect = exception

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        bosch_alarm_test_data.config,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "auth"
    assert result["errors"] == {"base": message}

    bosch_alarm_test_data.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        bosch_alarm_test_data.config,
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY

    await hass.async_block_till_done()
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    "bosch_alarm_test_data",
    ["Solution 3000", "AMAX 3000"],
    indirect=True,
)
@pytest.mark.usefixtures("bosch_alarm_test_data")
async def test_entry_already_configured_host(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    bosch_alarm_test_data: MockBoschAlarmConfig,
) -> None:
    """Test if configuring an entity twice results in an error."""
    entry = MockConfigEntry(domain="bosch_alarm", data={CONF_HOST: "0.0.0.0"})
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "0.0.0.0"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "auth"
    assert result["errors"] == {}
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        bosch_alarm_test_data.config,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"

    await hass.async_block_till_done()
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    "bosch_alarm_test_data",
    [
        "B5512 (US1B)",
    ],
    indirect=True,
)
@pytest.mark.usefixtures("bosch_alarm_test_data")
async def test_entry_already_configured_serial(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    bosch_alarm_test_data: MockBoschAlarmConfig,
) -> None:
    """Test if configuring an entity twice results in an error."""
    entry = MockConfigEntry(
        domain="bosch_alarm",
        unique_id=str(bosch_alarm_test_data.serial),
        data={CONF_HOST: "0.0.0.0"},
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "0.0.0.0"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "auth"
    assert result["errors"] == {}
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        bosch_alarm_test_data.config,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"

    await hass.async_block_till_done()
    assert len(mock_setup_entry.mock_calls) == 0
