"""Test the Rejseplanen config flow."""

from unittest.mock import AsyncMock

from py_rejseplan.enums import TransportClass
import pytest

from homeassistant.components.rejseplanen.const import (
    CONF_API_KEY,
    CONF_DEPARTURE_TYPE,
    CONF_DIRECTION,
    CONF_NAME,
    CONF_STOP_ID,
    DEFAULT_STOP_NAME,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


async def test_form_success(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test the form step of the config flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert "type" in result and result["type"] == FlowResultType.FORM

    _step_id = result.get("step_id")
    assert _step_id
    assert _step_id == "user"
    assert result.get("errors") is None


@pytest.mark.parametrize(
    ("user_input", "expected_data"),
    [
        # All fields empty except required stop_id
        (
            {
                CONF_STOP_ID: "123456",
            },
            {
                CONF_STOP_ID: 123456,
                CONF_DIRECTION: [],
                CONF_DEPARTURE_TYPE: [],
                CONF_NAME: DEFAULT_STOP_NAME,
            },
        ),
        # Only direction provided
        (
            {
                CONF_STOP_ID: "123456",
                CONF_DIRECTION: ["north"],
            },
            {
                CONF_STOP_ID: 123456,
                CONF_DIRECTION: ["north"],
                CONF_DEPARTURE_TYPE: [],
                CONF_NAME: DEFAULT_STOP_NAME,
            },
        ),
        # Only departure type provided
        (
            {
                CONF_STOP_ID: "123456",
                CONF_DEPARTURE_TYPE: ["ic", "icl"],
            },
            {
                CONF_STOP_ID: 123456,
                CONF_DEPARTURE_TYPE: [TransportClass.IC, TransportClass.ICL],
                CONF_DIRECTION: [],
                CONF_NAME: DEFAULT_STOP_NAME,
            },
        ),
        # Direction and departure type provided
        (
            {
                CONF_STOP_ID: "123456",
                CONF_DIRECTION: ["north"],
                CONF_DEPARTURE_TYPE: ["s_tog"],
            },
            {
                CONF_STOP_ID: 123456,
                CONF_DIRECTION: ["north"],
                CONF_DEPARTURE_TYPE: [TransportClass.S_TOG],
                CONF_NAME: DEFAULT_STOP_NAME,
            },
        ),
        # All fields provided, including name
        (
            {
                CONF_STOP_ID: "123456",
                CONF_DIRECTION: ["north"],
                CONF_DEPARTURE_TYPE: ["s_tog"],
                CONF_NAME: "customname",
            },
            {
                CONF_STOP_ID: 123456,
                CONF_DIRECTION: ["north"],
                CONF_DEPARTURE_TYPE: [TransportClass.S_TOG],
                CONF_NAME: "customname",
            },
        ),
    ],
)
@pytest.mark.usefixtures("mock_rejseplan")
async def test_add_stop_variants(
    hass: HomeAssistant, user_input, expected_data
) -> None:
    """Test adding a stop subentry with various combinations."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        title="Rejseplanen",
        data={
            CONF_NAME: "Rejseplanen",
            CONF_API_KEY: "token",
        },
    )
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    # Start the subentry flow for adding a stop
    result = await hass.config_entries.subentries.async_init(
        (config_entry.entry_id, "stop"), context={"source": SOURCE_USER}
    )
    assert result.get("type") is FlowResultType.FORM
    assert result.get("errors") is None

    result = await hass.config_entries.subentries.async_configure(
        result.get("flow_id"), user_input=user_input
    )
    assert result.get("type") is FlowResultType.CREATE_ENTRY
    assert (result_data := result.get("data")) is not None, "Subentry data is None"
    assert result_data.get(CONF_STOP_ID) == expected_data[CONF_STOP_ID], (
        "Stop ID mismatch"
    )
    assert result_data.get(CONF_NAME) == expected_data[CONF_NAME], "Name mismatch"
    assert result_data.get(CONF_DIRECTION) == expected_data[CONF_DIRECTION], (
        "Direction mismatch"
    )
    assert result_data.get(CONF_DEPARTURE_TYPE) == expected_data[CONF_DEPARTURE_TYPE], (
        "Departure type mismatch"
    )
