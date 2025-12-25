"""Test the Rejseplanen subentry config flows."""

from typing import Any

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
async def test_stop_subentry_variants(
    hass: HomeAssistant,
    user_input: dict[str, str],
    expected_data: dict[str, Any],
) -> None:
    """Test adding a stop subentry with various combinations."""
    # Set up main config entry
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
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] is None

    # Submit stop configuration
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], user_input=user_input
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY

    # Verify the data matches expected values
    result_data = result["data"]
    assert result_data[CONF_STOP_ID] == expected_data[CONF_STOP_ID]
    assert result_data[CONF_NAME] == expected_data[CONF_NAME]
    assert result_data[CONF_DIRECTION] == expected_data[CONF_DIRECTION]
    assert result_data[CONF_DEPARTURE_TYPE] == expected_data[CONF_DEPARTURE_TYPE]


async def test_stop_subentry_form_display(hass: HomeAssistant) -> None:
    """Test that the stop subentry form is displayed correctly."""
    # Set up main config entry
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

    # Start the subentry flow
    result = await hass.config_entries.subentries.async_init(
        (config_entry.entry_id, "stop"), context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] is None
