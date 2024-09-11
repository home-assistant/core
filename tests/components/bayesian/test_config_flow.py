"""Test the Config flow for the Bayesian integration."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from pytest_unordered import unordered

from homeassistant import config_entries
from homeassistant.components.bayesian import DOMAIN
from homeassistant.components.bayesian.config_flow import (
    ObservationTypes,
    OptionsFlowSteps,
)
from homeassistant.components.bayesian.const import (
    CONF_OBSERVATIONS,
    CONF_P_GIVEN_F,
    CONF_P_GIVEN_T,
    CONF_PRIOR,
    CONF_PROBABILITY_THRESHOLD,
    CONF_TO_STATE,
)
from homeassistant.const import (
    CONF_ABOVE,
    CONF_BELOW,
    CONF_DEVICE_CLASS,
    CONF_ENTITY_ID,
    CONF_NAME,
    CONF_PLATFORM,
    CONF_STATE,
    CONF_VALUE_TEMPLATE,
    STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.template import result_as_boolean

from tests.common import MockConfigEntry
from tests.typing import WebSocketGenerator


async def test_config_flow(hass: HomeAssistant) -> None:
    """Test the config flow with a full example."""
    with patch(
        "homeassistant.components.bayesian.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        result0 = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result0["step_id"] == "user"
        assert result0["type"] is FlowResultType.FORM

        result1 = await hass.config_entries.flow.async_configure(
            result0["flow_id"],
            {
                CONF_NAME: "Office occupied",
                CONF_PROBABILITY_THRESHOLD: 50,
                CONF_PRIOR: 15,
                CONF_DEVICE_CLASS: "occupancy",
            },
        )
        await hass.async_block_till_done()
        assert result1["step_id"] == "observation_selector"
        assert result1["type"] is FlowResultType.MENU

        result2 = await hass.config_entries.flow.async_configure(
            result1["flow_id"], {"next_step_id": "numeric_state"}
        )
        await hass.async_block_till_done()

        assert result2["step_id"] == "numeric_state"
        assert result2["type"] is FlowResultType.FORM
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {
                CONF_ENTITY_ID: "sensor.office_illuminance_lux",
                CONF_ABOVE: 40,
                CONF_P_GIVEN_T: 85,
                CONF_P_GIVEN_F: 45,
                CONF_NAME: "Office is bright",
                "add_another": True,
            },
        )

        await hass.async_block_till_done()
        assert result3["step_id"] == "observation_selector"
        assert result3["type"] is FlowResultType.MENU

        result4 = await hass.config_entries.flow.async_configure(
            result3["flow_id"], {"next_step_id": "state"}
        )
        await hass.async_block_till_done()

        assert result4["step_id"] == "state"
        assert result4["type"] is FlowResultType.FORM
        result5 = await hass.config_entries.flow.async_configure(
            result4["flow_id"],
            {
                CONF_ENTITY_ID: "sensor.work_laptop",
                CONF_TO_STATE: "on",
                CONF_P_GIVEN_T: 60,
                CONF_P_GIVEN_F: 20,
                CONF_NAME: "Work laptop on network",
                "add_another": True,
            },
        )
        await hass.async_block_till_done()
        assert result5["step_id"] == "observation_selector"
        assert result5["type"] is FlowResultType.MENU

        result6 = await hass.config_entries.flow.async_configure(
            result5["flow_id"], {"next_step_id": "template"}
        )
        await hass.async_block_till_done()

        assert result6["step_id"] == "template"
        assert result6["type"] is FlowResultType.FORM
        result7 = await hass.config_entries.flow.async_configure(
            result6["flow_id"],
            {
                CONF_VALUE_TEMPLATE: """
{% set current_time = now().time() %}
{% set start_time = strptime("07:00", "%H:%M").time() %}
{% set end_time = strptime("18:30", "%H:%M").time() %}
{% if start_time <= current_time <= end_time %}
True
{% else %}
False
{% endif %}
                """,
                CONF_P_GIVEN_T: 45,
                CONF_P_GIVEN_F: 5,
                CONF_NAME: "Daylight hours",
                "add_another": False,
            },
        )

        assert result7["version"] == 1
        assert result7["options"] == {
            CONF_NAME: "Office occupied",
            CONF_PROBABILITY_THRESHOLD: 0.5,
            CONF_PRIOR: 0.15,
            CONF_DEVICE_CLASS: "occupancy",
            CONF_OBSERVATIONS: [
                {
                    CONF_PLATFORM: "numeric_state",
                    CONF_ENTITY_ID: "sensor.office_illuminance_lux",
                    CONF_ABOVE: 40,
                    CONF_P_GIVEN_T: 0.85,
                    CONF_P_GIVEN_F: 0.45,
                    CONF_NAME: "Office is bright",
                },
                {
                    CONF_PLATFORM: "state",
                    CONF_ENTITY_ID: "sensor.work_laptop",
                    CONF_TO_STATE: "on",
                    CONF_P_GIVEN_T: 0.6,
                    CONF_P_GIVEN_F: 0.2,
                    CONF_NAME: "Work laptop on network",
                },
                {
                    CONF_PLATFORM: "template",
                    CONF_VALUE_TEMPLATE: '{% set current_time = now().time() %}\n{% set start_time = strptime("07:00", "%H:%M").time() %}\n{% set end_time = strptime("18:30", "%H:%M").time() %}\n{% if start_time <= current_time <= end_time %}\nTrue\n{% else %}\nFalse\n{% endif %}',
                    CONF_P_GIVEN_T: 0.45,
                    CONF_P_GIVEN_F: 0.05,
                    CONF_NAME: "Daylight hours",
                },
            ],
        }

    assert len(mock_setup_entry.mock_calls) == 1


async def test_single_state_observation(hass: HomeAssistant) -> None:
    """Test we get the form."""

    with patch(
        "homeassistant.components.bayesian.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        result0 = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result0["step_id"] == "user"
        assert result0["type"] is FlowResultType.FORM

        result1 = await hass.config_entries.flow.async_configure(
            result0["flow_id"],
            {
                CONF_NAME: "Anyone home",
                CONF_PROBABILITY_THRESHOLD: 50,
                CONF_PRIOR: 66,
                CONF_DEVICE_CLASS: "occupancy",
            },
        )
        await hass.async_block_till_done()
        assert result1["step_id"] == "observation_selector"
        assert result1["type"] is FlowResultType.MENU

        result2 = await hass.config_entries.flow.async_configure(
            result1["flow_id"], {"next_step_id": "state"}
        )
        await hass.async_block_till_done()

        assert result2["step_id"] == "state"
        assert result2["type"] is FlowResultType.FORM
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {
                CONF_ENTITY_ID: "sensor.kitchen_occupancy",
                CONF_TO_STATE: "on",
                CONF_P_GIVEN_T: 40,
                CONF_P_GIVEN_F: 0.5,
                CONF_NAME: "Kitchen Motion",
                "add_another": False,
            },
        )

        assert result3["version"] == 1
        assert result3["options"] == {
            CONF_NAME: "Anyone home",
            CONF_PROBABILITY_THRESHOLD: 0.5,
            CONF_PRIOR: 0.66,
            CONF_DEVICE_CLASS: "occupancy",
            CONF_OBSERVATIONS: [
                {
                    CONF_PLATFORM: CONF_STATE,
                    CONF_ENTITY_ID: "sensor.kitchen_occupancy",
                    CONF_TO_STATE: "on",
                    CONF_P_GIVEN_T: 0.4,
                    CONF_P_GIVEN_F: 0.005,
                    CONF_NAME: "Kitchen Motion",
                }
            ],
        }

    assert len(mock_setup_entry.mock_calls) == 1


async def test_single_numeric_state_observation(hass: HomeAssistant) -> None:
    """Test we get the form."""

    with patch(
        "homeassistant.components.bayesian.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        result0 = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result0["step_id"] == "user"
        assert result0["type"] is FlowResultType.FORM

        result1 = await hass.config_entries.flow.async_configure(
            result0["flow_id"],
            {
                CONF_NAME: "Nice day",
                CONF_PROBABILITY_THRESHOLD: 51,
                CONF_PRIOR: 20,
            },
        )
        await hass.async_block_till_done()
        assert result1["step_id"] == "observation_selector"
        assert result1["type"] is FlowResultType.MENU

        result2 = await hass.config_entries.flow.async_configure(
            result1["flow_id"], {"next_step_id": "numeric_state"}
        )
        await hass.async_block_till_done()

        assert result2["step_id"] == "numeric_state"
        assert result2["type"] is FlowResultType.FORM
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {
                CONF_ENTITY_ID: "sensor.outside_temperature",
                CONF_ABOVE: 20,
                CONF_BELOW: 35,
                CONF_P_GIVEN_T: 95,
                CONF_P_GIVEN_F: 8,
                CONF_NAME: "20 - 35 outside",
                "add_another": False,
            },
        )

        assert result3["version"] == 1
        assert result3["options"] == {
            CONF_NAME: "Nice day",
            CONF_PROBABILITY_THRESHOLD: 0.51,
            CONF_PRIOR: 0.2,
            CONF_OBSERVATIONS: [
                {
                    CONF_PLATFORM: "numeric_state",
                    CONF_ENTITY_ID: "sensor.outside_temperature",
                    CONF_ABOVE: 20,
                    CONF_BELOW: 35,
                    CONF_P_GIVEN_T: 0.95,
                    CONF_P_GIVEN_F: 0.08,
                    CONF_NAME: "20 - 35 outside",
                }
            ],
        }

    assert len(mock_setup_entry.mock_calls) == 1


async def test_single_template_observation(hass: HomeAssistant) -> None:
    """Test we get the form."""

    with patch(
        "homeassistant.components.bayesian.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        result0 = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result0["step_id"] == "user"
        assert result0["type"] is FlowResultType.FORM

        result1 = await hass.config_entries.flow.async_configure(
            result0["flow_id"],
            {
                CONF_NAME: "Paulus Home",
                CONF_PROBABILITY_THRESHOLD: 90,
                CONF_PRIOR: 50,
                CONF_DEVICE_CLASS: "occupancy",
            },
        )
        await hass.async_block_till_done()
        assert result1["step_id"] == "observation_selector"
        assert result1["type"] is FlowResultType.MENU

        result2 = await hass.config_entries.flow.async_configure(
            result1["flow_id"], {"next_step_id": "template"}
        )
        await hass.async_block_till_done()
        assert result2["step_id"] == "template"
        assert result2["type"] is FlowResultType.FORM
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {
                CONF_VALUE_TEMPLATE: "{{is_state('device_tracker.paulus','not_home') and ((as_timestamp(now()) - as_timestamp(states.device_tracker.paulus.last_changed)) > 300)}}",
                CONF_P_GIVEN_T: 5,
                CONF_P_GIVEN_F: 99,
                CONF_NAME: "Not seen in last 5 minutes",
                "add_another": False,
            },
        )

        assert result3["version"] == 1
        assert result3["options"] == {
            CONF_NAME: "Paulus Home",
            CONF_PROBABILITY_THRESHOLD: 0.9,
            CONF_PRIOR: 0.5,
            CONF_DEVICE_CLASS: "occupancy",
            CONF_OBSERVATIONS: [
                {
                    CONF_PLATFORM: "template",
                    CONF_VALUE_TEMPLATE: "{{is_state('device_tracker.paulus','not_home') and ((as_timestamp(now()) - as_timestamp(states.device_tracker.paulus.last_changed)) > 300)}}",
                    CONF_P_GIVEN_T: 0.05,
                    CONF_P_GIVEN_F: 0.99,
                    CONF_NAME: "Not seen in last 5 minutes",
                }
            ],
        }

    assert len(mock_setup_entry.mock_calls) == 1


async def test_basic_options(hass: HomeAssistant) -> None:
    """Test reconfiguring the basic options."""
    # Setup the config entry
    config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={
            CONF_NAME: "Office occupied",
            CONF_PROBABILITY_THRESHOLD: 0.5,
            CONF_PRIOR: 0.15,
            CONF_DEVICE_CLASS: "occupancy",
            CONF_OBSERVATIONS: [
                {
                    CONF_PLATFORM: "numeric_state",
                    CONF_ENTITY_ID: "sensor.office_illuminance_lux",
                    CONF_ABOVE: 40,
                    CONF_P_GIVEN_T: 0.85,
                    CONF_P_GIVEN_F: 0.45,
                    CONF_NAME: "Office is bright",
                }
            ],
        },
        title="Office occupied",
    )
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    hass.states.async_set("sensor.office_illuminance_lux", 50)

    result0 = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result0["type"] is FlowResultType.MENU
    assert result0["step_id"] == "init"

    result1 = await hass.config_entries.options.async_configure(
        result0["flow_id"], {"next_step_id": "base_options"}
    )
    await hass.async_block_till_done()
    assert result1["step_id"] == "base_options"
    assert result1["type"] is FlowResultType.FORM

    await hass.config_entries.options.async_configure(
        result1["flow_id"],
        {
            CONF_PROBABILITY_THRESHOLD: 49,
            CONF_PRIOR: 14,
            CONF_DEVICE_CLASS: "presence",
        },
    )
    await hass.async_block_till_done()
    assert hass.config_entries.async_get_entry(config_entry.entry_id).options == {
        CONF_NAME: "Office occupied",
        CONF_PROBABILITY_THRESHOLD: 0.49,
        CONF_PRIOR: 0.14,
        CONF_DEVICE_CLASS: "presence",
        CONF_OBSERVATIONS: [
            {
                CONF_PLATFORM: "numeric_state",
                CONF_ENTITY_ID: "sensor.office_illuminance_lux",
                CONF_ABOVE: 40,
                CONF_P_GIVEN_T: 0.85,
                CONF_P_GIVEN_F: 0.45,
                CONF_NAME: "Office is bright",
            }
        ],
    }


async def test_add_single_state_obvservation(hass: HomeAssistant) -> None:
    """Test adding a single observation through options flow.

    Since this relies on the same logic as a config flow, we do not need to test each type.
    """
    # Setup the config entry
    config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={
            CONF_NAME: "Office occupied",
            CONF_PROBABILITY_THRESHOLD: 0.5,
            CONF_PRIOR: 0.15,
            CONF_DEVICE_CLASS: "occupancy",
            CONF_OBSERVATIONS: [
                {
                    CONF_PLATFORM: "numeric_state",
                    CONF_ENTITY_ID: "sensor.office_illuminance_lux",
                    CONF_ABOVE: 40,
                    CONF_P_GIVEN_T: 0.85,
                    CONF_P_GIVEN_F: 0.45,
                    CONF_NAME: "Office is bright",
                }
            ],
        },
        title="Office occupied",
    )
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    hass.states.async_set("sensor.office_illuminance_lux", 50)

    result0 = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result0["type"] is FlowResultType.MENU
    assert result0["step_id"] == "init"

    result1 = await hass.config_entries.options.async_configure(
        result0["flow_id"], {"next_step_id": str(OptionsFlowSteps.ADD_OBSERVATION)}
    )
    await hass.async_block_till_done()
    assert result1["step_id"] == str(OptionsFlowSteps.ADD_OBSERVATION)
    assert result1["type"] is FlowResultType.MENU

    # First test adding a single state observation
    result2 = await hass.config_entries.options.async_configure(
        result1["flow_id"], {"next_step_id": CONF_STATE}
    )
    await hass.async_block_till_done()
    assert result2["step_id"] == CONF_STATE
    assert result2["type"] is FlowResultType.FORM

    await hass.config_entries.options.async_configure(
        result2["flow_id"],
        {
            CONF_ENTITY_ID: "sensor.work_laptop",
            CONF_TO_STATE: "on",
            CONF_P_GIVEN_T: 60,
            CONF_P_GIVEN_F: 20,
            CONF_NAME: "Work laptop on network",
            "add_another": False,
        },
    )
    await hass.async_block_till_done()
    assert hass.config_entries.async_get_entry(config_entry.entry_id).options == {
        CONF_NAME: "Office occupied",
        CONF_PROBABILITY_THRESHOLD: 0.5,
        CONF_PRIOR: 0.15,
        CONF_DEVICE_CLASS: "occupancy",
        CONF_OBSERVATIONS: [
            {
                CONF_PLATFORM: "numeric_state",
                CONF_ENTITY_ID: "sensor.office_illuminance_lux",
                CONF_ABOVE: 40,
                CONF_P_GIVEN_T: 0.85,
                CONF_P_GIVEN_F: 0.45,
                CONF_NAME: "Office is bright",
            },
            {
                CONF_PLATFORM: "state",
                CONF_ENTITY_ID: "sensor.work_laptop",
                CONF_TO_STATE: "on",
                CONF_P_GIVEN_T: 0.6,
                CONF_P_GIVEN_F: 0.2,
                CONF_NAME: "Work laptop on network",
            },
        ],
    }


async def test_editing_observations(hass: HomeAssistant) -> None:
    """Test editing observations through options flow, once of each of the 3 types."""
    # Setup the config entry
    config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={
            CONF_NAME: "Office occupied",
            CONF_PROBABILITY_THRESHOLD: 0.5,
            CONF_PRIOR: 0.15,
            CONF_DEVICE_CLASS: "occupancy",
            CONF_OBSERVATIONS: [
                {
                    CONF_PLATFORM: "numeric_state",
                    CONF_ENTITY_ID: "sensor.office_illuminance_lux",
                    CONF_ABOVE: 40,
                    CONF_P_GIVEN_T: 0.85,
                    CONF_P_GIVEN_F: 0.45,
                    CONF_NAME: "Office is bright",
                },
                {
                    CONF_PLATFORM: "state",
                    CONF_ENTITY_ID: "sensor.work_laptop",
                    CONF_TO_STATE: "on",
                    CONF_P_GIVEN_T: 0.6,
                    CONF_P_GIVEN_F: 0.2,
                    CONF_NAME: "Work laptop on network",
                },
                {
                    CONF_PLATFORM: "template",
                    CONF_VALUE_TEMPLATE: '{% set current_time = now().time() %}\n{% set start_time = strptime("07:00", "%H:%M").time() %}\n{% set end_time = strptime("18:30", "%H:%M").time() %}\n{% if start_time <= current_time <= end_time %}\nTrue\n{% else %}\nFalse\n{% endif %}',
                    CONF_P_GIVEN_T: 0.45,
                    CONF_P_GIVEN_F: 0.05,
                    CONF_NAME: "Daylight hours",
                },
            ],
        },
        title="Office occupied",
    )
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    hass.states.async_set("sensor.office_illuminance_lux", 50)

    result0 = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result0["type"] is FlowResultType.MENU
    assert result0["step_id"] == "init"

    result1 = await hass.config_entries.options.async_configure(
        result0["flow_id"],
        {"next_step_id": str(OptionsFlowSteps.SELECT_EDIT_OBSERVATION)},
    )
    await hass.async_block_till_done()
    assert result1["step_id"] == str(OptionsFlowSteps.SELECT_EDIT_OBSERVATION)
    assert result1["type"] is FlowResultType.FORM
    assert result1["data_schema"].schema["index"].container == {
        "0": "Office is bright (numeric_state)",
        "1": "Work laptop on network (state)",
        "2": "Daylight hours (template)",
    }

    # First test edit a state observation
    result2 = await hass.config_entries.options.async_configure(
        result1["flow_id"], {"index": "1"}
    )
    await hass.async_block_till_done()
    assert result2["step_id"] == str(OptionsFlowSteps.EDIT_OBSERVATION)
    assert result2["type"] is FlowResultType.FORM

    await hass.config_entries.options.async_configure(
        result2["flow_id"],
        {
            CONF_ENTITY_ID: "sensor.desktop",
            CONF_TO_STATE: "on",
            CONF_P_GIVEN_T: 70,
            CONF_P_GIVEN_F: 12,
            CONF_NAME: "Desktop on network",
        },
    )
    await hass.async_block_till_done()
    assert hass.config_entries.async_get_entry(config_entry.entry_id).options == {
        CONF_NAME: "Office occupied",
        CONF_PROBABILITY_THRESHOLD: 0.5,
        CONF_PRIOR: 0.15,
        CONF_DEVICE_CLASS: "occupancy",
        CONF_OBSERVATIONS: [
            {
                CONF_PLATFORM: "numeric_state",
                CONF_ENTITY_ID: "sensor.office_illuminance_lux",
                CONF_ABOVE: 40,
                CONF_P_GIVEN_T: 0.85,
                CONF_P_GIVEN_F: 0.45,
                CONF_NAME: "Office is bright",
            },
            {
                CONF_PLATFORM: "state",
                CONF_ENTITY_ID: "sensor.desktop",
                CONF_TO_STATE: "on",
                CONF_P_GIVEN_T: 0.7,
                CONF_P_GIVEN_F: 0.12,
                CONF_NAME: "Desktop on network",
            },
            {
                CONF_PLATFORM: "template",
                CONF_VALUE_TEMPLATE: '{% set current_time = now().time() %}\n{% set start_time = strptime("07:00", "%H:%M").time() %}\n{% set end_time = strptime("18:30", "%H:%M").time() %}\n{% if start_time <= current_time <= end_time %}\nTrue\n{% else %}\nFalse\n{% endif %}',
                CONF_P_GIVEN_T: 0.45,
                CONF_P_GIVEN_F: 0.05,
                CONF_NAME: "Daylight hours",
            },
        ],
    }

    # Next test edit a numeric_state observation
    result0 = await hass.config_entries.options.async_init(config_entry.entry_id)
    result1 = await hass.config_entries.options.async_configure(
        result0["flow_id"],
        {"next_step_id": str(OptionsFlowSteps.SELECT_EDIT_OBSERVATION)},
    )
    await hass.async_block_till_done()
    assert result1["data_schema"].schema["index"].container == {
        "0": "Office is bright (numeric_state)",
        "1": "Desktop on network (state)",
        "2": "Daylight hours (template)",
    }
    result2 = await hass.config_entries.options.async_configure(
        result1["flow_id"], {"index": "0"}
    )
    await hass.async_block_till_done()
    assert result2["step_id"] == str(OptionsFlowSteps.EDIT_OBSERVATION)
    assert result2["type"] is FlowResultType.FORM

    await hass.config_entries.options.async_configure(
        result2["flow_id"],
        {
            CONF_ENTITY_ID: "sensor.office_illuminance_lumens",
            CONF_ABOVE: 2000,
            CONF_P_GIVEN_T: 80,
            CONF_P_GIVEN_F: 40,
            CONF_NAME: "Office is bright",
        },
    )
    await hass.async_block_till_done()
    assert hass.config_entries.async_get_entry(config_entry.entry_id).options == {
        CONF_NAME: "Office occupied",
        CONF_PROBABILITY_THRESHOLD: 0.5,
        CONF_PRIOR: 0.15,
        CONF_DEVICE_CLASS: "occupancy",
        CONF_OBSERVATIONS: [
            {
                CONF_PLATFORM: "numeric_state",
                CONF_ENTITY_ID: "sensor.office_illuminance_lumens",
                CONF_ABOVE: 2000,
                CONF_P_GIVEN_T: 0.8,
                CONF_P_GIVEN_F: 0.4,
                CONF_NAME: "Office is bright",
            },
            {
                CONF_PLATFORM: "state",
                CONF_ENTITY_ID: "sensor.desktop",
                CONF_TO_STATE: "on",
                CONF_P_GIVEN_T: 0.7,
                CONF_P_GIVEN_F: 0.12,
                CONF_NAME: "Desktop on network",
            },
            {
                CONF_PLATFORM: "template",
                CONF_VALUE_TEMPLATE: '{% set current_time = now().time() %}\n{% set start_time = strptime("07:00", "%H:%M").time() %}\n{% set end_time = strptime("18:30", "%H:%M").time() %}\n{% if start_time <= current_time <= end_time %}\nTrue\n{% else %}\nFalse\n{% endif %}',
                CONF_P_GIVEN_T: 0.45,
                CONF_P_GIVEN_F: 0.05,
                CONF_NAME: "Daylight hours",
            },
        ],
    }

    # next test templates:
    result0 = await hass.config_entries.options.async_init(config_entry.entry_id)
    result1 = await hass.config_entries.options.async_configure(
        result0["flow_id"],
        {"next_step_id": str(OptionsFlowSteps.SELECT_EDIT_OBSERVATION)},
    )
    await hass.async_block_till_done()
    assert result1["data_schema"].schema["index"].container == {
        "0": "Office is bright (numeric_state)",
        "1": "Desktop on network (state)",
        "2": "Daylight hours (template)",
    }
    result2 = await hass.config_entries.options.async_configure(
        result1["flow_id"], {"index": "2"}
    )
    await hass.async_block_till_done()
    assert result2["step_id"] == str(OptionsFlowSteps.EDIT_OBSERVATION)
    assert result2["type"] is FlowResultType.FORM

    await hass.config_entries.options.async_configure(
        result2["flow_id"],
        {
            CONF_VALUE_TEMPLATE: """
{% set current_time = now().time() %}
{% set start_time = strptime("07:00", "%H:%M").time() %}
{% set end_time = strptime("17:30", "%H:%M").time() %}
{% if start_time <= current_time <= end_time %}
True
{% else %}
False
{% endif %}
""",
            CONF_P_GIVEN_T: 55,
            CONF_P_GIVEN_F: 13,
            CONF_NAME: "Office hours",
        },
    )
    await hass.async_block_till_done()
    assert hass.config_entries.async_get_entry(config_entry.entry_id).options == {
        CONF_NAME: "Office occupied",
        CONF_PROBABILITY_THRESHOLD: 0.5,
        CONF_PRIOR: 0.15,
        CONF_DEVICE_CLASS: "occupancy",
        CONF_OBSERVATIONS: [
            {
                CONF_PLATFORM: "numeric_state",
                CONF_ENTITY_ID: "sensor.office_illuminance_lumens",
                CONF_ABOVE: 2000,
                CONF_P_GIVEN_T: 0.8,
                CONF_P_GIVEN_F: 0.4,
                CONF_NAME: "Office is bright",
            },
            {
                CONF_PLATFORM: "state",
                CONF_ENTITY_ID: "sensor.desktop",
                CONF_TO_STATE: "on",
                CONF_P_GIVEN_T: 0.7,
                CONF_P_GIVEN_F: 0.12,
                CONF_NAME: "Desktop on network",
            },
            {
                CONF_PLATFORM: "template",
                CONF_VALUE_TEMPLATE: '{% set current_time = now().time() %}\n{% set start_time = strptime("07:00", "%H:%M").time() %}\n{% set end_time = strptime("17:30", "%H:%M").time() %}\n{% if start_time <= current_time <= end_time %}\nTrue\n{% else %}\nFalse\n{% endif %}',
                CONF_P_GIVEN_T: 0.55,
                CONF_P_GIVEN_F: 0.13,
                CONF_NAME: "Office hours",
            },
        ],
    }


async def test_delete_observations(hass: HomeAssistant) -> None:
    """Test deleting observations through options flow, one at a time and two at a time."""
    # Setup the config entry
    config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={
            CONF_NAME: "Office occupied",
            CONF_PROBABILITY_THRESHOLD: 0.5,
            CONF_PRIOR: 0.15,
            CONF_DEVICE_CLASS: "occupancy",
            CONF_OBSERVATIONS: [
                {
                    CONF_PLATFORM: "numeric_state",
                    CONF_ENTITY_ID: "sensor.office_illuminance_lux",
                    CONF_ABOVE: 40,
                    CONF_P_GIVEN_T: 0.85,
                    CONF_P_GIVEN_F: 0.45,
                    CONF_NAME: "Office is bright",
                },
                {
                    CONF_PLATFORM: "state",
                    CONF_ENTITY_ID: "sensor.work_laptop",
                    CONF_TO_STATE: "on",
                    CONF_P_GIVEN_T: 0.6,
                    CONF_P_GIVEN_F: 0.2,
                    CONF_NAME: "Work laptop on network",
                },
                {
                    CONF_PLATFORM: "template",
                    CONF_VALUE_TEMPLATE: '{% set current_time = now().time() %}\n{% set start_time = strptime("07:00", "%H:%M").time() %}\n{% set end_time = strptime("18:30", "%H:%M").time() %}\n{% if start_time <= current_time <= end_time %}\nTrue\n{% else %}\nFalse\n{% endif %}',
                    CONF_P_GIVEN_T: 0.45,
                    CONF_P_GIVEN_F: 0.05,
                    CONF_NAME: "Daylight hours",
                },
            ],
        },
        title="Office occupied",
    )
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    hass.states.async_set("sensor.office_illuminance_lux", 50)

    result0 = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result0["type"] is FlowResultType.MENU
    assert result0["step_id"] == "init"

    result1 = await hass.config_entries.options.async_configure(
        result0["flow_id"],
        {"next_step_id": str(OptionsFlowSteps.REMOVE_OBSERVATION)},
    )
    await hass.async_block_till_done()
    assert result1["step_id"] == str(OptionsFlowSteps.REMOVE_OBSERVATION)
    assert result1["type"] is FlowResultType.FORM
    assert result1["data_schema"].schema["index"].options == {
        "0": "Office is bright (numeric_state)",
        "1": "Work laptop on network (state)",
        "2": "Daylight hours (template)",
    }

    # First test delete a state observation
    await hass.config_entries.options.async_configure(
        result1["flow_id"], {"index": ["1"]}
    )
    await hass.async_block_till_done()

    assert hass.config_entries.async_get_entry(config_entry.entry_id).options == {
        CONF_NAME: "Office occupied",
        CONF_PROBABILITY_THRESHOLD: 0.5,
        CONF_PRIOR: 0.15,
        CONF_DEVICE_CLASS: "occupancy",
        CONF_OBSERVATIONS: [
            {
                CONF_PLATFORM: "numeric_state",
                CONF_ENTITY_ID: "sensor.office_illuminance_lux",
                CONF_ABOVE: 40,
                CONF_P_GIVEN_T: 0.85,
                CONF_P_GIVEN_F: 0.45,
                CONF_NAME: "Office is bright",
            },
            {
                CONF_PLATFORM: "template",
                CONF_VALUE_TEMPLATE: '{% set current_time = now().time() %}\n{% set start_time = strptime("07:00", "%H:%M").time() %}\n{% set end_time = strptime("18:30", "%H:%M").time() %}\n{% if start_time <= current_time <= end_time %}\nTrue\n{% else %}\nFalse\n{% endif %}',
                CONF_P_GIVEN_T: 0.45,
                CONF_P_GIVEN_F: 0.05,
                CONF_NAME: "Daylight hours",
            },
        ],
    }

    # next delete all remaining observations
    result0 = await hass.config_entries.options.async_init(config_entry.entry_id)
    result1 = await hass.config_entries.options.async_configure(
        result0["flow_id"],
        {"next_step_id": str(OptionsFlowSteps.REMOVE_OBSERVATION)},
    )
    await hass.async_block_till_done()
    assert result1["step_id"] == str(OptionsFlowSteps.REMOVE_OBSERVATION)
    assert result1["type"] is FlowResultType.FORM
    assert result1["data_schema"].schema["index"].options == {
        "0": "Office is bright (numeric_state)",
        "1": "Daylight hours (template)",
    }

    await hass.config_entries.options.async_configure(
        result1["flow_id"], {"index": ["0", "1"]}
    )
    await hass.async_block_till_done()

    assert hass.config_entries.async_get_entry(config_entry.entry_id).options == {
        CONF_NAME: "Office occupied",
        CONF_PROBABILITY_THRESHOLD: 0.5,
        CONF_PRIOR: 0.15,
        CONF_DEVICE_CLASS: "occupancy",
        CONF_OBSERVATIONS: [],
    }


async def test_invalid_configs(hass: HomeAssistant) -> None:
    """Test that invalid configs are refused."""
    with patch(
        "homeassistant.components.bayesian.async_setup_entry", return_value=True
    ):
        result0 = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result0["step_id"] == "user"
        assert result0["type"] is FlowResultType.FORM

        # priors should never be Zero, because then the sensor can never return 'on'
        result1 = await hass.config_entries.flow.async_configure(
            result0["flow_id"],
            {
                CONF_NAME: "Office occupied",
                CONF_PROBABILITY_THRESHOLD: 50,
                CONF_PRIOR: 0,
            },
        )

        await hass.async_block_till_done()
        assert result1["errors"] == {"base": "prior_low_error"}
        # Confirm that the config flow did not progress
        assert result1["step_id"] != "observation_selector"

        # priors should never be 1 because then the sensor can never be 'off'
        result1 = await hass.config_entries.flow.async_configure(
            result0["flow_id"],
            {
                CONF_NAME: "Office occupied",
                CONF_PROBABILITY_THRESHOLD: 50,
                CONF_PRIOR: 100,
            },
        )
        await hass.async_block_till_done()
        assert result1["errors"] == {"base": "prior_high_error"}

        # Threshold should never be 1 because then the sensor can never be 'on'
        result1 = await hass.config_entries.flow.async_configure(
            result0["flow_id"],
            {
                CONF_NAME: "Office occupied",
                CONF_PROBABILITY_THRESHOLD: 100,
                CONF_PRIOR: 30,
            },
        )
        await hass.async_block_till_done()
        assert result1["errors"] == {"base": "threshold_high_error"}

        # Threshold should never be 0 because then the sensor can never be 'off'
        result1 = await hass.config_entries.flow.async_configure(
            result0["flow_id"],
            {
                CONF_NAME: "Office occupied",
                CONF_PROBABILITY_THRESHOLD: 0,
                CONF_PRIOR: 30,
            },
        )
        await hass.async_block_till_done()
        assert result1["errors"] == {"base": "threshold_low_error"}

        # Now lets progress to testing observations
        result1 = await hass.config_entries.flow.async_configure(
            result0["flow_id"],
            {
                CONF_NAME: "Office occupied",
                CONF_PROBABILITY_THRESHOLD: 50,
                CONF_PRIOR: 30,
            },
        )
        await hass.async_block_till_done()
        assert result1.get("errors") is None

        assert result1["step_id"] == "observation_selector"
        assert result1["type"] is FlowResultType.MENU

        result2 = await hass.config_entries.flow.async_configure(
            result1["flow_id"], {"next_step_id": "state"}
        )
        await hass.async_block_till_done()

        assert result2["step_id"] == "state"
        assert result2["type"] is FlowResultType.FORM

        # Observations with equal probabilities have no effect
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {
                CONF_ENTITY_ID: "sensor.work_laptop",
                CONF_TO_STATE: "on",
                CONF_P_GIVEN_T: 60,
                CONF_P_GIVEN_F: 60,
                CONF_NAME: "Work laptop on network",
                "add_another": True,
            },
        )
        await hass.async_block_till_done()
        assert result3["errors"] == {"base": "equal_probabilities"}
        assert result3["step_id"] != "observation_selector"

        # Observations with a probability of 0 will create certainties
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {
                CONF_ENTITY_ID: "sensor.work_laptop",
                CONF_TO_STATE: "on",
                CONF_P_GIVEN_T: 0,
                CONF_P_GIVEN_F: 60,
                CONF_NAME: "Work laptop on network",
                "add_another": True,
            },
        )
        await hass.async_block_till_done()
        assert result3["errors"] == {"base": "extreme_prob_given_error"}

        # Observations with a probability of 1 will create certainties
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {
                CONF_ENTITY_ID: "sensor.work_laptop",
                CONF_TO_STATE: "on",
                CONF_P_GIVEN_T: 60,
                CONF_P_GIVEN_F: 100,
                CONF_NAME: "Work laptop on network",
                "add_another": True,
            },
        )
        await hass.async_block_till_done()
        assert result3["errors"] == {"base": "extreme_prob_given_error"}


@pytest.mark.parametrize(
    (
        "template_type",
        "value_template",
        "input_states",
        "template_states",
        "listeners",
    ),
    [
        (
            "binary_sensor",
            "{{ states.binary_sensor.one.state == 'on' or states.binary_sensor.two.state == 'on' }}",
            {"one": "on", "two": "off"},
            ["off", "on"],
            [["one", "two"], ["one"]],
        ),
        (
            "sensor",
            "{{ float(states('sensor.one'), default='') + float(states('sensor.two'), default='') }}",
            {"one": "30.0", "two": "20.0"},
            ["", STATE_UNAVAILABLE, "50.0"],
            [["one", "two"], ["one", "two"]],
        ),
    ],
)
async def test_config_flow_preview(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    template_type: str,
    value_template: str,
    input_states: list[str],
    template_states: str,
    listeners: list[list[str]],
) -> None:
    """Test the config flow preview."""
    client = await hass_ws_client(hass)
    input_entities = ["one", "two"]
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["step_id"] == "user"
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_NAME: "Office occupied",
            CONF_PROBABILITY_THRESHOLD: 50,
            CONF_PRIOR: 15,
            CONF_DEVICE_CLASS: "occupancy",
        },
    )
    await hass.async_block_till_done()
    assert result["step_id"] == "observation_selector"
    assert result["type"] is FlowResultType.MENU

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "template"}
    )
    await hass.async_block_till_done()

    assert result["step_id"] == "template"
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] is None
    assert result["preview"] == "template"

    await client.send_json_auto_id(
        {
            "type": "template/start_preview",
            "flow_id": result["flow_id"],
            "flow_type": "config_flow",
            "user_input": {
                CONF_VALUE_TEMPLATE: value_template,
                CONF_P_GIVEN_T: 30,
                CONF_P_GIVEN_F: 50,
                CONF_NAME: "tracking template",
            },
        }
    )
    msg = await client.receive_json()
    assert msg["success"]
    assert msg["result"] is None

    msg = await client.receive_json()
    assert msg["event"] == {
        "attributes": {"friendly_name": "Observation"},
        "listeners": {
            "all": False,
            "domains": [],
            "entities": unordered([f"{template_type}.{_id}" for _id in listeners[0]]),
            "time": False,
        },
        "state": result_as_boolean(template_states[0]),
    }

    for input_entity in input_entities:
        hass.states.async_set(
            f"{template_type}.{input_entity}", input_states[input_entity], {}
        )
        await hass.async_block_till_done()

    for template_state in template_states[1:]:
        msg = await client.receive_json(timeout=3)
        assert msg["event"] == {
            "attributes": {"friendly_name": "Observation"},
            "listeners": {
                "all": False,
                "domains": [],
                "entities": unordered(
                    [f"{template_type}.{_id}" for _id in listeners[1]]
                ),
                "time": False,
            },
            "state": result_as_boolean(template_state),
        }
    assert len(hass.states.async_all()) == 2


@pytest.mark.parametrize(
    (
        "template_type",
        "value_template",
        "input_states",
        "template_states",
        "listeners",
    ),
    [
        (
            "binary_sensor",
            "{{ states.binary_sensor.one.state == 'on' or states.binary_sensor.two.state == 'on' }}",
            {"one": "on", "two": "off"},
            ["off", "on"],
            [["one", "two"], ["one"]],
        ),
        (
            "sensor",
            "{{ float(states('sensor.one'), default='') + float(states('sensor.two'), default='') }}",
            {"one": "30.0", "two": "20.0"},
            ["", STATE_UNAVAILABLE, "50.0"],
            [["one", "two"], ["one", "two"]],
        ),
    ],
)
async def test_options_flow_preview(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    template_type: str,
    value_template: str,
    input_states: list[str],
    template_states: str,
    listeners: list[list[str]],
) -> None:
    """Test the config flow preview."""
    # Setup the config entry
    config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={
            CONF_NAME: "Office occupied",
            CONF_PROBABILITY_THRESHOLD: 0.5,
            CONF_PRIOR: 0.15,
            CONF_DEVICE_CLASS: "occupancy",
            CONF_OBSERVATIONS: [],
        },
        title="Office occupied",
    )
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    client = await hass_ws_client(hass)
    input_entities = ["one", "two"]
    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["step_id"] == "init"
    assert result["type"] is FlowResultType.MENU
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": str(OptionsFlowSteps.ADD_OBSERVATION)}
    )
    await hass.async_block_till_done()
    assert result["step_id"] == str(OptionsFlowSteps.ADD_OBSERVATION)
    assert result["type"] is FlowResultType.MENU

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": str(ObservationTypes.TEMPLATE)}
    )
    await hass.async_block_till_done()

    assert result["step_id"] == str(ObservationTypes.TEMPLATE)
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] is None
    assert result["preview"] == str(ObservationTypes.TEMPLATE)

    await client.send_json_auto_id(
        {
            "type": "template/start_preview",
            "flow_id": result["flow_id"],
            "flow_type": "options_flow",
            "user_input": {
                CONF_VALUE_TEMPLATE: value_template,
                CONF_P_GIVEN_T: 30,
                CONF_P_GIVEN_F: 50,
                CONF_NAME: "tracking template",
            },
        }
    )
    msg = await client.receive_json()
    assert msg["success"]
    assert msg["result"] is None

    msg = await client.receive_json()
    assert msg["event"] == {
        "attributes": {"friendly_name": "Observation"},
        "listeners": {
            "all": False,
            "domains": [],
            "entities": unordered([f"{template_type}.{_id}" for _id in listeners[0]]),
            "time": False,
        },
        "state": result_as_boolean(template_states[0]),
    }

    for input_entity in input_entities:
        hass.states.async_set(
            f"{template_type}.{input_entity}", input_states[input_entity], {}
        )
        await hass.async_block_till_done()

    for template_state in template_states[1:]:
        msg = await client.receive_json(timeout=3)
        assert msg["event"] == {
            "attributes": {"friendly_name": "Observation"},
            "listeners": {
                "all": False,
                "domains": [],
                "entities": unordered(
                    [f"{template_type}.{_id}" for _id in listeners[1]]
                ),
                "time": False,
            },
            "state": result_as_boolean(template_state),
        }
    # length is the two pytest entities and the bayesian sensor
    assert len(hass.states.async_all()) == 3


@pytest.mark.parametrize(
    (
        "template_type",
        "value_template",
        "input_states",
        "template_states",
        "listeners",
    ),
    [
        (
            "binary_sensor",
            "{{ states.binary_sensor.one.state == 'on' or states.binary_sensor.two.state = 'on' }}",
            {"one": "on", "two": "off"},
            ["off", "on"],
            [["one", "two"], ["one"]],
        ),
        (
            "sensor",
            "{{ float(states('sensor.one'), default='') + float(states('sensor.two'), default=''",
            {"one": "30.0", "two": "20.0"},
            ["", STATE_UNAVAILABLE, "50.0"],
            [["one", "two"], ["one", "two"]],
        ),
    ],
)
async def test_bad_config_flow_preview(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    template_type: str,
    value_template: str,
    input_states: list[str],
    template_states: str,
    listeners: list[list[str]],
) -> None:
    """Test the config flow preview."""
    client = await hass_ws_client(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["step_id"] == "user"
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_NAME: "Office occupied",
            CONF_PROBABILITY_THRESHOLD: 50,
            CONF_PRIOR: 15,
            CONF_DEVICE_CLASS: "occupancy",
        },
    )
    await hass.async_block_till_done()
    assert result["step_id"] == "observation_selector"
    assert result["type"] is FlowResultType.MENU

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "template"}
    )
    await hass.async_block_till_done()

    assert result["step_id"] == "template"
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] is None
    assert result["preview"] == "template"

    await client.send_json_auto_id(
        {
            "type": "template/start_preview",
            "flow_id": result["flow_id"],
            "flow_type": "config_flow",
            "user_input": {
                CONF_VALUE_TEMPLATE: value_template,
                CONF_P_GIVEN_T: 30,
                CONF_P_GIVEN_F: 50,
                CONF_NAME: "tracking template",
            },
        }
    )
    msg = await client.receive_json()
    assert not msg["success"]
    assert msg["error"] is not None


@pytest.mark.parametrize(
    (
        "template_type",
        "value_template",
        "input_states",
        "template_states",
        "error_events",
    ),
    [
        (
            "sensor",
            "{{ float(states('sensor.one')) + float(states('sensor.two')) }}",
            {"one": "30.0", "two": "20.0"},
            ["unavailable", "50.0"],
            [
                (
                    "ValueError: Template error: float got invalid input 'unknown' "
                    "when rendering template '{{ float(states('sensor.one')) + "
                    "float(states('sensor.two')) }}' but no default was specified"
                )
            ],
        ),
    ],
)
async def test_config_flow_preview_template_startup_error(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    template_type: str,
    value_template: str,
    input_states: dict[str, str],
    template_states: list[str],
    error_events: list[str],
) -> None:
    """Tests an error when using states('') syntax without default."""
    client = await hass_ws_client(hass)
    input_entities = ["one", "two"]
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["step_id"] == "user"
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_NAME: "Office occupied",
            CONF_PROBABILITY_THRESHOLD: 50,
            CONF_PRIOR: 15,
            CONF_DEVICE_CLASS: "occupancy",
        },
    )
    await hass.async_block_till_done()
    assert result["step_id"] == "observation_selector"
    assert result["type"] is FlowResultType.MENU

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "template"}
    )
    await hass.async_block_till_done()

    assert result["step_id"] == "template"
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] is None
    assert result["preview"] == "template"

    await client.send_json_auto_id(
        {
            "type": "template/start_preview",
            "flow_id": result["flow_id"],
            "flow_type": "config_flow",
            "user_input": {
                CONF_VALUE_TEMPLATE: value_template,
                CONF_P_GIVEN_T: 30,
                CONF_P_GIVEN_F: 50,
                CONF_NAME: "tracking template",
            },
        }
    )
    msg = await client.receive_json()
    assert msg["type"] == "result"
    assert msg["success"]

    for error_event in error_events:
        msg = await client.receive_json()
        assert msg["type"] == "event"
        assert msg["event"] == {"error": error_event}

    msg = await client.receive_json()
    assert msg["type"] == "event"
    assert msg["event"]["state"] == result_as_boolean(template_states[0])

    for input_entity in input_entities:
        hass.states.async_set(
            f"{template_type}.{input_entity}", input_states[input_entity], {}
        )

    msg = await client.receive_json()
    assert msg["type"] == "event"
    assert msg["event"]["state"] == result_as_boolean(template_states[1])
