"""Test the AirTouch 3 Air Conditioner config flow."""

from unittest.mock import AsyncMock, patch

import pytest

from homeassistant import config_entries
from homeassistant.components.airtouch3.const import DOMAIN
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.update_coordinator import UpdateFailed

from tests.common import MockConfigEntry


async def test_form(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.airtouch3.config_flow.async_fetch_airtouch_data",
        return_value=None,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "1.1.1.1",
            },
        )
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "AirTouch 3 Air Conditioner"
    assert result["data"] == {
        CONF_HOST: "1.1.1.1",
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_cannot_connect(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.airtouch3.config_flow.async_fetch_airtouch_data",
        side_effect=UpdateFailed("failed"),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "1.1.1.1",
            },
        )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    # Make sure the config flow tests finish with either an
    # FlowResultType.CREATE_ENTRY or FlowResultType.ABORT so
    # we can show the config flow is able to recover from an error.

    with patch(
        "homeassistant.components.airtouch3.config_flow.async_fetch_airtouch_data",
        return_value=None,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "1.1.1.1",
            },
        )
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "AirTouch 3 Air Conditioner"
    assert result["data"] == {
        CONF_HOST: "1.1.1.1",
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_unknown_error(hass: HomeAssistant) -> None:
    """Test we handle unknown errors."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.airtouch3.config_flow.async_fetch_airtouch_data",
        side_effect=RuntimeError("boom"),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "1.1.1.1",
            },
        )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "unknown"}


async def test_form_already_configured(hass: HomeAssistant) -> None:
    """Test we abort if the host is already configured."""
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_HOST: "1.1.1.1"})
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.airtouch3.config_flow.async_fetch_airtouch_data",
        return_value=None,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "1.1.1.1",
            },
        )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.usefixtures("mock_setup_entry")
async def test_reconfigure_updates_host(hass: HomeAssistant) -> None:
    """Test reconfiguring the host."""
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_HOST: "1.1.1.1"})
    entry.add_to_hass(hass)

    result = await entry.start_reconfigure_flow(hass)

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    with patch(
        "homeassistant.components.airtouch3.config_flow.async_fetch_airtouch_data",
        return_value=None,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: " 2.2.2.2 ",
            },
        )
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data == {
        CONF_HOST: "2.2.2.2",
    }


@pytest.mark.parametrize(
    ("side_effect", "expected_error"),
    [
        pytest.param(UpdateFailed("failed"), "cannot_connect", id="cannot-connect"),
        pytest.param(RuntimeError("boom"), "unknown", id="unknown"),
    ],
)
@pytest.mark.usefixtures("mock_setup_entry")
async def test_reconfigure_errors(
    hass: HomeAssistant,
    side_effect: Exception,
    expected_error: str,
) -> None:
    """Test reconfigure error handling."""
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_HOST: "1.1.1.1"})
    entry.add_to_hass(hass)

    result = await entry.start_reconfigure_flow(hass)

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    with patch(
        "homeassistant.components.airtouch3.config_flow.async_fetch_airtouch_data",
        side_effect=side_effect,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "2.2.2.2",
            },
        )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "reconfigure"
    assert result["errors"] == {"base": expected_error}

    with patch(
        "homeassistant.components.airtouch3.config_flow.async_fetch_airtouch_data",
        return_value=None,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "2.2.2.2",
            },
        )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
