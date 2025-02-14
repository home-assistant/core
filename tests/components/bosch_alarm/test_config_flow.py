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
from homeassistant.const import (
    CONF_CODE,
    CONF_HOST,
    CONF_MODEL,
    CONF_PASSWORD,
    CONF_PORT,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


@pytest.mark.parametrize(
    ("model", "config"),
    [
        ("Solution 3000", {CONF_USER_CODE: "1234"}),
        ("AMAX 3000", {CONF_INSTALLER_CODE: "1234", CONF_PASSWORD: "1234567890"}),
        ("B5512 (US1B)", {CONF_PASSWORD: "1234567890"}),
    ],
)
async def test_form_user(hass: HomeAssistant, model: str, config: dict) -> None:
    """Test the config flow for bosch_alarm."""

    async def connect(self, load_selector):
        self.model = model

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] is None
    with (
        patch("bosch_alarm_mode2.panel.Panel.connect", connect),
        patch(
            "homeassistant.components.bosch_alarm.async_setup_entry",
            return_value=True,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: "1.1.1.1", CONF_PORT: 7700},
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "auth"
        assert result["errors"] is None
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            config,
        )
        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["title"] == f"Bosch {model}"
        assert result["data"] == {
            CONF_HOST: "1.1.1.1",
            CONF_PORT: 7700,
            CONF_MODEL: model,
            **config,
        }


@pytest.mark.parametrize(
    ("exception", "message"),
    [
        (PermissionError(), "invalid_auth"),
        (asyncio.exceptions.TimeoutError(), "cannot_connect"),
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
    assert result["errors"] is None
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


async def test_entry_already_configured(hass: HomeAssistant) -> None:
    """Test if configuring an entity twice results in an error."""

    entry = MockConfigEntry(
        domain="bosch_alarm", unique_id="unique_id", data={"host": "0.0.0.0"}
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch("bosch_alarm_mode2.panel.Panel.connect"):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"host": "0.0.0.0"},
        )

        assert result2["type"] is FlowResultType.ABORT
        assert result2["reason"] == "already_configured"


async def test_options_flow(hass: HomeAssistant) -> None:
    """Test the options flow for bosch_alarm."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "1.1.1.1",
            CONF_PORT: 7700,
            CONF_INSTALLER_CODE: "1234",
            CONF_PASSWORD: "1234567890",
            CONF_MODEL: "AMAX 3000",
        },
        version=1,
        minor_version=2,
    )
    config_entry.add_to_hass(hass)

    with (
        patch("bosch_alarm_mode2.panel.Panel.connect", None),
        patch(
            "homeassistant.components.bosch_alarm.async_setup_entry",
            return_value=True,
        ),
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)

    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_CODE: "1234"},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"] is True

    assert config_entry.options == {CONF_CODE: "1234"}
