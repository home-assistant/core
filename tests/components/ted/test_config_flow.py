"""Tests for the TED config flow."""
from unittest.mock import AsyncMock, PropertyMock, patch

import httpx
import tedpy

from homeassistant import config_entries, data_entry_flow
from homeassistant.components.ted import DOMAIN
from homeassistant.components.ted.const import (
    CONF_MTU_ENERGY_DAILY,
    CONF_MTU_ENERGY_MTD,
    CONF_MTU_ENERGY_NOW,
    CONF_MTU_POWER_VOLTAGE,
    CONF_SPYDER_ENERGY_DAILY,
    CONF_SPYDER_ENERGY_MTD,
    CONF_SPYDER_ENERGY_NOW,
)
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

CONFIG = {CONF_HOST: "127.0.0.1"}
CONFIG_FINAL = {CONF_HOST: "127.0.0.1", CONF_NAME: "TED 5000"}


async def test_form(hass: HomeAssistant) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["errors"] == {}

    with patch("tedpy.TED5000.check", return_value=True), patch(
        "tedpy.TED5000.update", return_value=True
    ), patch(
        "tedpy.TED5000.gateway_id", new_callable=PropertyMock, return_value="test"
    ), patch(
        "homeassistant.components.ted.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            CONFIG,
        )

        await hass.async_block_till_done()

    assert result2["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result2["data"] == CONFIG_FINAL
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_host_already_exists(hass: HomeAssistant) -> None:
    """Test host already exists."""

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "host": "1.1.1.1",
            "name": "TED",
        },
        title="TED",
    )
    config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["errors"] == {}

    with patch("tedpy.TED5000.check", return_value=True), patch(
        "tedpy.TED5000.update", return_value=True
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"host": "1.1.1.1"},
        )
        await hass.async_block_till_done()

    assert result2["type"] == data_entry_flow.FlowResultType.ABORT
    assert result2["reason"] == "already_configured"


async def test_form_cannot_connect(hass: HomeAssistant) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch("tedpy.createTED", side_effect=httpx.HTTPError("any")):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            CONFIG,
        )

    assert result2["type"] == data_entry_flow.FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_form_unknown_error(hass: HomeAssistant) -> None:
    """Test we handle unknown error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch("tedpy.createTED", side_effect=ValueError):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"host": "1.1.1.1"},
        )

    assert result2["type"] == data_entry_flow.FlowResultType.FORM
    assert result2["errors"] == {"base": "unknown"}


async def test_options_flow(hass):
    """Test config flow options."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "host": "1.1.1.1",
            "name": "TED",
        },
        title="TED",
    )
    config_entry.add_to_hass(hass)

    ted_mock = AsyncMock(tedpy.TED5000)
    ted_mock.spyders = [
        tedpy.TedSpyder(
            position=0,
            secondary=0,
            mtu_parent=0,
            ctgroups=[
                tedpy.TedCtGroup(
                    position=0,
                    spyder_position=0,
                    description="group",
                    _ted=ted_mock,
                    member_cts=[
                        tedpy.TedCt(position=0, description="ct", type=0, multiplier=1)
                    ],
                )
            ],
        )
    ]
    ted_mock.mtus = [
        tedpy.TedMtu(
            id=0,
            position=0,
            description="mtu",
            type=tedpy.MtuType.NET,
            power_cal_factor=1,
            voltage_cal_factor=1,
            _ted=ted_mock,
        )
    ]
    with patch("tedpy.createTED", return_value=ted_mock):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_SPYDER_ENERGY_NOW: True,
            CONF_SPYDER_ENERGY_DAILY: True,
            CONF_SPYDER_ENERGY_MTD: True,
            CONF_MTU_POWER_VOLTAGE: False,
            CONF_MTU_ENERGY_NOW: False,
            CONF_MTU_ENERGY_DAILY: False,
            CONF_MTU_ENERGY_MTD: False,
        },
    )
    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert config_entry.options[CONF_SPYDER_ENERGY_NOW]
    assert config_entry.options[CONF_SPYDER_ENERGY_DAILY]
    assert config_entry.options[CONF_SPYDER_ENERGY_MTD]
    assert not config_entry.options[CONF_MTU_POWER_VOLTAGE]
    assert not config_entry.options[CONF_MTU_ENERGY_NOW]
    assert not config_entry.options[CONF_MTU_ENERGY_DAILY]
    assert not config_entry.options[CONF_MTU_ENERGY_MTD]
