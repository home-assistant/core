"""Test the 2N Telekomunikace config flow."""
from datetime import datetime
from unittest.mock import AsyncMock, patch

from py2n import Py2NDeviceData, Py2NDeviceSwitch

from homeassistant import config_entries
from homeassistant.components.telekomunikace_2n.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

MOCK_DEVICE_DATA = Py2NDeviceData(
    name="Test name",
    model="Test model",
    serial="00-0000-0000",
    host="1.1.1.1",
    mac="00-00-00-00-00-00",
    firmware="1.0.0.0.0",
    hardware="0v0",
    uptime=datetime.now,
    switches=[Py2NDeviceSwitch(id=1, active=False, locked=False)],
)


async def test_form(hass: HomeAssistant) -> None:
    """Test we get the form."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] is None

    with patch(
        "py2n.Py2NDevice.create",
        new=AsyncMock(return_value=AsyncMock(data=MOCK_DEVICE_DATA)),
    ), patch(
        "homeassistant.components.telekomunikace_2n.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: "1.1.1.1", CONF_USERNAME: "foo", CONF_PASSWORD: "bar"},
        )
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Test name"
    assert result2["data"] == {
        CONF_HOST: "1.1.1.1",
        CONF_USERNAME: "foo",
        CONF_PASSWORD: "bar",
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_invalid_host(hass: HomeAssistant) -> None:
    """Test we get error if host is invalid."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] is None

    with patch(
        "py2n.Py2NDevice.create",
        new=AsyncMock(return_value=AsyncMock(data=MOCK_DEVICE_DATA)),
    ), patch(
        "homeassistant.components.telekomunikace_2n.async_setup_entry",
        return_value=True,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: "1.1.1", CONF_USERNAME: "foo", CONF_PASSWORD: "bar"},
        )
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"host": "invalid_host"}
