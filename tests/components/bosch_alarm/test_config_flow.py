"""Tests for the bosch_alarm config flow."""

import asyncio
from unittest.mock import patch

import pytest

from homeassistant import config_entries
from homeassistant.components.bosch_alarm.const import (
    CONF_INSTALLER_CODE,
    CONF_USER_CODE,
    DOMAIN,
)
from homeassistant.const import CONF_HOST, CONF_MODEL, CONF_PASSWORD, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("setup_bosch_alarm")
@pytest.mark.parametrize(
    ("setup_bosch_alarm", "config"),
    [
        ("Solution 3000", {CONF_USER_CODE: "1234"}),
        ("AMAX 3000", {CONF_INSTALLER_CODE: "1234", CONF_PASSWORD: "1234567890"}),
        ("B5512 (US1B)", {CONF_PASSWORD: "1234567890"}),
    ],
    indirect=["setup_bosch_alarm"],
)
async def test_form_user(
    hass: HomeAssistant, setup_bosch_alarm: str, config: dict
) -> None:
    """Test the config flow for bosch_alarm."""

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
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        config,
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == f"Bosch {setup_bosch_alarm}"
    assert result["data"] == {
        CONF_HOST: "1.1.1.1",
        CONF_PORT: 7700,
        CONF_MODEL: setup_bosch_alarm,
        **config,
    }


@pytest.mark.usefixtures("setup_bosch_alarm")
@pytest.mark.parametrize(
    ("setup_bosch_alarm", "exception", "message"),
    [
        ("Solution 3000", asyncio.exceptions.TimeoutError(), "cannot_connect"),
    ],
)
async def test_form_exceptions(
    hass: HomeAssistant, exception: Exception, message: str
) -> None:
    """Test we handle exceptions correctly."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}
    with (
        patch("bosch_alarm_mode2.panel.Panel.connect", side_effect=exception),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: "1.1.1.1", CONF_PORT: 7700},
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"
        assert result["errors"] == {"base": message}


@pytest.mark.usefixtures("setup_bosch_alarm")
@pytest.mark.parametrize(
    ("setup_bosch_alarm", "exception", "message"),
    [
        ("Solution 3000", PermissionError(), "invalid_auth"),
        ("Solution 3000", asyncio.exceptions.TimeoutError(), "cannot_connect"),
    ],
    indirect=["setup_bosch_alarm"],
)
async def test_form_exceptions_user(
    hass: HomeAssistant, exception: Exception, message: str
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

    with (
        patch("bosch_alarm_mode2.panel.Panel.connect", side_effect=exception),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_USER_CODE: "1234"},
        )


@pytest.mark.parametrize("setup_bosch_alarm", ["Solution 3000"], indirect=True)
@pytest.mark.usefixtures("setup_bosch_alarm")
async def test_entry_already_configured(hass: HomeAssistant) -> None:
    """Test if configuring an entity twice results in an error."""

    async def connect(self, load_selector):
        self.model = "Solution 3000"

    entry = MockConfigEntry(
        domain="bosch_alarm", unique_id="unique_id", data={CONF_HOST: "0.0.0.0"}
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    # with patch("bosch_alarm_mode2.panel.Panel.connect", connect):
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "0.0.0.0"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "auth"
    assert result["errors"] == {}
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_USER_CODE: "1234"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
