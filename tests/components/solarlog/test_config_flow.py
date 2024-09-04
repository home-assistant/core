"""Test the solarlog config flow."""

from unittest.mock import AsyncMock, patch

import pytest
from solarlog_cli.solarlog_exceptions import SolarLogConnectionError, SolarLogError

from homeassistant.components.solarlog import config_flow
from homeassistant.components.solarlog.const import DOMAIN
from homeassistant.config_entries import SOURCE_RECONFIGURE, SOURCE_USER
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .const import HOST, NAME

from tests.common import MockConfigEntry


async def test_form(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test we get the form."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    with (
        patch(
            "homeassistant.components.solarlog.config_flow.SolarLogConfigFlow._test_connection",
            return_value=True,
        ),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: HOST, CONF_NAME: NAME, "extended_data": False},
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "solarlog_test_1_2_3"
    assert result2["data"][CONF_HOST] == "http://1.1.1.1"
    assert result2["data"]["extended_data"] is False
    assert len(mock_setup_entry.mock_calls) == 1


def init_config_flow(hass: HomeAssistant) -> config_flow.SolarLogConfigFlow:
    """Init a configuration flow."""
    flow = config_flow.SolarLogConfigFlow()
    flow.hass = hass
    return flow


@pytest.mark.usefixtures("test_connect")
async def test_user(
    hass: HomeAssistant,
    mock_solarlog_connector: AsyncMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test user config."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    # tests with all provided
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: HOST, CONF_NAME: NAME, "extended_data": True}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "solarlog_test_1_2_3"
    assert result["data"][CONF_HOST] == HOST
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    ("exception", "error"),
    [
        (SolarLogConnectionError, {CONF_HOST: "cannot_connect"}),
        (SolarLogError, {CONF_HOST: "unknown"}),
    ],
)
async def test_form_exceptions(
    hass: HomeAssistant,
    exception: Exception,
    error: dict[str, str],
    mock_solarlog_connector: AsyncMock,
) -> None:
    """Test we can handle Form exceptions."""
    flow = init_config_flow(hass)

    result = await flow.async_step_user()
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    mock_solarlog_connector.test_connection.side_effect = exception

    # tests with connection error
    result = await flow.async_step_user(
        {CONF_NAME: NAME, CONF_HOST: HOST, "extended_data": False}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == error

    mock_solarlog_connector.test_connection.side_effect = None

    # tests with all provided
    result = await flow.async_step_user(
        {CONF_NAME: NAME, CONF_HOST: HOST, "extended_data": False}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "solarlog_test_1_2_3"
    assert result["data"][CONF_HOST] == HOST
    assert result["data"]["extended_data"] is False


async def test_abort_if_already_setup(hass: HomeAssistant, test_connect: None) -> None:
    """Test we abort if the device is already setup."""

    MockConfigEntry(domain=DOMAIN, data={CONF_NAME: NAME, CONF_HOST: HOST}).add_to_hass(
        hass
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: HOST, CONF_NAME: "solarlog_test_7_8_9", "extended_data": False},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_reconfigure_flow(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test config flow options."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="solarlog_test_1_2_3",
        data={
            CONF_HOST: HOST,
            "extended_data": False,
        },
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": SOURCE_RECONFIGURE,
            "entry_id": entry.entry_id,
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"extended_data": True}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert len(mock_setup_entry.mock_calls) == 1
