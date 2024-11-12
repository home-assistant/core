"""Test the Config flow for the Bayesian integration."""

from __future__ import annotations

from unittest.mock import patch

import pytest
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components.bayesian.config_flow import (
    OBSERVATION_SELECTOR,
    USER,
    ObservationTypes,
    OptionsFlowSteps,
)
from homeassistant.components.bayesian.const import (
    CONF_INDEX,
    CONF_OBSERVATIONS,
    CONF_P_GIVEN_F,
    CONF_P_GIVEN_T,
    CONF_PRIOR,
    CONF_PROBABILITY_THRESHOLD,
    CONF_TO_STATE,
    DOMAIN,
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
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


async def test_config_flow(hass: HomeAssistant) -> None:
    """Test the config flow with a full example."""
    with patch(
        "homeassistant.components.bayesian.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        # Open config flow
        result0 = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result0["step_id"] == USER
        assert result0["type"] is FlowResultType.FORM

        # Enter basic settings
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

        # Confirm the next page is the observation type selector
        assert result1["step_id"] == OBSERVATION_SELECTOR
        assert result1["type"] is FlowResultType.MENU

        # Set up a numeric state observation first
        result2 = await hass.config_entries.flow.async_configure(
            result1["flow_id"], {"next_step_id": str(ObservationTypes.NUMERIC_STATE)}
        )
        await hass.async_block_till_done()

        assert result2["step_id"] == str(ObservationTypes.NUMERIC_STATE)
        assert result2["type"] is FlowResultType.FORM

        # Set up a numeric range with only 'Above'
        # Also indirectly tests the conversion of proabilities to fractions
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

        # Since "add_another" was True, we should return to the observation selector
        assert result3["step_id"] == OBSERVATION_SELECTOR
        assert result3["type"] is FlowResultType.MENU

        # Add a state observation
        result4 = await hass.config_entries.flow.async_configure(
            result3["flow_id"], {"next_step_id": str(ObservationTypes.STATE)}
        )
        await hass.async_block_till_done()

        assert result4["step_id"] == str(ObservationTypes.STATE)
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

        # Since "add_another" was True, we should return to the observation selector
        assert result5["step_id"] == OBSERVATION_SELECTOR
        assert result5["type"] is FlowResultType.MENU

        # Lastly, add a template observation
        result6 = await hass.config_entries.flow.async_configure(
            result5["flow_id"], {"next_step_id": str(ObservationTypes.TEMPLATE)}
        )
        await hass.async_block_till_done()

        assert result6["step_id"] == str(ObservationTypes.TEMPLATE)
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

        # Since add_another is false, we should now be done.
        assert result7["version"] == 1
        assert result7["options"] == {
            CONF_NAME: "Office occupied",
            CONF_PROBABILITY_THRESHOLD: 0.5,
            CONF_PRIOR: 0.15,
            CONF_DEVICE_CLASS: "occupancy",
            CONF_OBSERVATIONS: [
                {
                    CONF_PLATFORM: str(ObservationTypes.NUMERIC_STATE),
                    CONF_ENTITY_ID: "sensor.office_illuminance_lux",
                    CONF_ABOVE: 40,
                    CONF_P_GIVEN_T: 0.85,
                    CONF_P_GIVEN_F: 0.45,
                    CONF_NAME: "Office is bright",
                },
                {
                    CONF_PLATFORM: str(ObservationTypes.STATE),
                    CONF_ENTITY_ID: "sensor.work_laptop",
                    CONF_TO_STATE: "on",
                    CONF_P_GIVEN_T: 0.6,
                    CONF_P_GIVEN_F: 0.2,
                    CONF_NAME: "Work laptop on network",
                },
                {
                    CONF_PLATFORM: str(ObservationTypes.TEMPLATE),
                    CONF_VALUE_TEMPLATE: '{% set current_time = now().time() %}\n{% set start_time = strptime("07:00", "%H:%M").time() %}\n{% set end_time = strptime("18:30", "%H:%M").time() %}\n{% if start_time <= current_time <= end_time %}\nTrue\n{% else %}\nFalse\n{% endif %}',
                    CONF_P_GIVEN_T: 0.45,
                    CONF_P_GIVEN_F: 0.05,
                    CONF_NAME: "Daylight hours",
                },
            ],
        }

    assert len(mock_setup_entry.mock_calls) == 1


async def test_single_state_observation(hass: HomeAssistant) -> None:
    """Test a Bayesian sensor with just one state observation added.

    Technically a subset of the tests in test_config_flow() but may help to
    narrow down errors more quickly.
    """

    with patch(
        "homeassistant.components.bayesian.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        result0 = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result0["step_id"] == USER
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
        assert result1["step_id"] == OBSERVATION_SELECTOR
        assert result1["type"] is FlowResultType.MENU

        result2 = await hass.config_entries.flow.async_configure(
            result1["flow_id"], {"next_step_id": str(ObservationTypes.STATE)}
        )
        await hass.async_block_till_done()

        assert result2["step_id"] == str(ObservationTypes.STATE)
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
    """Test a Bayesian sensor with just one numeric_state observation added.

    Technically a subset of the tests in test_config_flow() but may help to
    narrow down errors more quickly.
    """

    with patch(
        "homeassistant.components.bayesian.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        result0 = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result0["step_id"] == USER
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
        assert result1["step_id"] == OBSERVATION_SELECTOR
        assert result1["type"] is FlowResultType.MENU

        result2 = await hass.config_entries.flow.async_configure(
            result1["flow_id"], {"next_step_id": str(ObservationTypes.NUMERIC_STATE)}
        )
        await hass.async_block_till_done()

        assert result2["step_id"] == str(ObservationTypes.NUMERIC_STATE)
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
                    CONF_PLATFORM: str(ObservationTypes.NUMERIC_STATE),
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


async def test_multi_numeric_state_observation(hass: HomeAssistant) -> None:
    """Test a Bayesian sensor with just more than one numeric_state observation added.

    Technically a subset of the tests in test_config_flow() but may help to
    narrow down errors more quickly.
    """

    with patch(
        "homeassistant.components.bayesian.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        result0 = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result0["step_id"] == USER
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
        assert result1["step_id"] == OBSERVATION_SELECTOR
        assert result1["type"] is FlowResultType.MENU

        result2 = await hass.config_entries.flow.async_configure(
            result1["flow_id"], {"next_step_id": str(ObservationTypes.NUMERIC_STATE)}
        )
        await hass.async_block_till_done()

        assert result2["step_id"] == str(ObservationTypes.NUMERIC_STATE)
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
                "add_another": True,
            },
        )
        result4 = await hass.config_entries.flow.async_configure(
            result3["flow_id"], {"next_step_id": str(ObservationTypes.NUMERIC_STATE)}
        )
        await hass.async_block_till_done()

        # This should fail as overlapping ranges for the same entity are not allowed
        with pytest.raises(vol.Invalid) as excinfo:
            await hass.config_entries.flow.async_configure(
                result4["flow_id"],
                {
                    CONF_ENTITY_ID: "sensor.outside_temperature",
                    CONF_ABOVE: 30,
                    CONF_BELOW: 40,
                    CONF_P_GIVEN_T: 95,
                    CONF_P_GIVEN_F: 8,
                    CONF_NAME: "30 - 40 outside",
                    "add_another": False,
                },
            )
        assert (
            excinfo.value.error_message
            == "Ranges for bayesian numeric state entities must not overlap, but sensor.outside_temperature has overlapping ranges, above:20.0, below:35.0 overlaps with above:30.0, below:40.0."
        )

        # This should fail as above should always be less than below
        with pytest.raises(vol.Invalid) as excinfo:
            await hass.config_entries.flow.async_configure(
                result4["flow_id"],
                {
                    CONF_ENTITY_ID: "sensor.outside_temperature",
                    CONF_ABOVE: 40,
                    CONF_BELOW: 35,
                    CONF_P_GIVEN_T: 95,
                    CONF_P_GIVEN_F: 8,
                    CONF_NAME: "35 - 40 outside",
                    "add_another": False,
                },
            )
        assert excinfo.value.error_message == "'above' is greater than 'below'"

        # This should work
        result5 = await hass.config_entries.flow.async_configure(
            result4["flow_id"],
            {
                CONF_ENTITY_ID: "sensor.outside_temperature",
                CONF_ABOVE: 35,
                CONF_BELOW: 40,
                CONF_P_GIVEN_T: 70,
                CONF_P_GIVEN_F: 20,
                CONF_NAME: "35 - 40 outside",
                "add_another": False,
            },
        )
        await hass.async_block_till_done()

        assert result5["version"] == 1
        assert result5["options"] == {
            CONF_NAME: "Nice day",
            CONF_PROBABILITY_THRESHOLD: 0.51,
            CONF_PRIOR: 0.2,
            CONF_OBSERVATIONS: [
                {
                    CONF_PLATFORM: str(ObservationTypes.NUMERIC_STATE),
                    CONF_ENTITY_ID: "sensor.outside_temperature",
                    CONF_ABOVE: 20.0,
                    CONF_BELOW: 35.0,
                    CONF_P_GIVEN_T: 0.95,
                    CONF_P_GIVEN_F: 0.08,
                    CONF_NAME: "20 - 35 outside",
                },
                {
                    CONF_PLATFORM: str(ObservationTypes.NUMERIC_STATE),
                    CONF_ENTITY_ID: "sensor.outside_temperature",
                    CONF_ABOVE: 35.0,
                    CONF_BELOW: 40.0,
                    CONF_P_GIVEN_T: 0.7,
                    CONF_P_GIVEN_F: 0.2,
                    CONF_NAME: "35 - 40 outside",
                },
            ],
        }

    assert len(mock_setup_entry.mock_calls) == 1


async def test_single_template_observation(hass: HomeAssistant) -> None:
    """Test a Bayesian sensor with just one template observation added.

    Technically a subset of the tests in test_config_flow() but may help to
    narrow down errors more quickly.
    """

    with patch(
        "homeassistant.components.bayesian.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        result0 = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result0["step_id"] == USER
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
        assert result1["step_id"] == OBSERVATION_SELECTOR
        assert result1["type"] is FlowResultType.MENU

        result2 = await hass.config_entries.flow.async_configure(
            result1["flow_id"], {"next_step_id": str(ObservationTypes.TEMPLATE)}
        )
        await hass.async_block_till_done()
        assert result2["step_id"] == str(ObservationTypes.TEMPLATE)
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
                    CONF_PLATFORM: str(ObservationTypes.TEMPLATE),
                    CONF_VALUE_TEMPLATE: "{{is_state('device_tracker.paulus','not_home') and ((as_timestamp(now()) - as_timestamp(states.device_tracker.paulus.last_changed)) > 300)}}",
                    CONF_P_GIVEN_T: 0.05,
                    CONF_P_GIVEN_F: 0.99,
                    CONF_NAME: "Not seen in last 5 minutes",
                }
            ],
        }

    assert len(mock_setup_entry.mock_calls) == 1


async def test_basic_options(hass: HomeAssistant) -> None:
    """Test reconfiguring the basic options using an options flow."""

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
                    CONF_PLATFORM: str(ObservationTypes.NUMERIC_STATE),
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
    # Setup the mock config entry
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    # Give the sensor a real value
    hass.states.async_set("sensor.office_illuminance_lux", 50)

    # Start the options flow
    result0 = await hass.config_entries.options.async_init(config_entry.entry_id)

    # Confirm the first page is the menu of options flow functions
    assert result0["type"] is FlowResultType.MENU
    assert result0["step_id"] == str(OptionsFlowSteps.INIT)

    # Choose to reconfigure the basic options
    result1 = await hass.config_entries.options.async_configure(
        result0["flow_id"], {"next_step_id": str(OptionsFlowSteps.BASE_OPTIONS)}
    )
    await hass.async_block_till_done()
    assert result1["step_id"] == str(OptionsFlowSteps.BASE_OPTIONS)
    assert result1["type"] is FlowResultType.FORM

    # Change all possible settings (name can be changed elsewhere in the UI)
    await hass.config_entries.options.async_configure(
        result1["flow_id"],
        {
            CONF_PROBABILITY_THRESHOLD: 49,
            CONF_PRIOR: 14,
            CONF_DEVICE_CLASS: "presence",
        },
    )
    await hass.async_block_till_done()

    # Confirm the changes stuck
    assert hass.config_entries.async_get_entry(config_entry.entry_id).options == {
        CONF_NAME: "Office occupied",
        CONF_PROBABILITY_THRESHOLD: 0.49,
        CONF_PRIOR: 0.14,
        CONF_DEVICE_CLASS: "presence",
        CONF_OBSERVATIONS: [
            {
                CONF_PLATFORM: str(ObservationTypes.NUMERIC_STATE),
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
                    CONF_PLATFORM: str(ObservationTypes.NUMERIC_STATE),
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
    # Add the config entry
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    hass.states.async_set("sensor.office_illuminance_lux", 50)

    result0 = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result0["type"] is FlowResultType.MENU
    assert result0["step_id"] == str(OptionsFlowSteps.INIT)

    result1 = await hass.config_entries.options.async_configure(
        result0["flow_id"], {"next_step_id": str(OptionsFlowSteps.ADD_OBSERVATION)}
    )
    await hass.async_block_till_done()
    assert result1["step_id"] == str(OptionsFlowSteps.ADD_OBSERVATION)
    assert result1["type"] is FlowResultType.MENU

    # Test adding a single state observation
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
                CONF_PLATFORM: str(ObservationTypes.NUMERIC_STATE),
                CONF_ENTITY_ID: "sensor.office_illuminance_lux",
                CONF_ABOVE: 40,
                CONF_P_GIVEN_T: 0.85,
                CONF_P_GIVEN_F: 0.45,
                CONF_NAME: "Office is bright",
            },
            {
                CONF_PLATFORM: str(ObservationTypes.STATE),
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
                    CONF_PLATFORM: str(ObservationTypes.NUMERIC_STATE),
                    CONF_ENTITY_ID: "sensor.office_illuminance_lux",
                    CONF_ABOVE: 40,
                    CONF_P_GIVEN_T: 0.85,
                    CONF_P_GIVEN_F: 0.45,
                    CONF_NAME: "Office is bright",
                },
                {
                    CONF_PLATFORM: str(ObservationTypes.STATE),
                    CONF_ENTITY_ID: "sensor.work_laptop",
                    CONF_TO_STATE: "on",
                    CONF_P_GIVEN_T: 0.6,
                    CONF_P_GIVEN_F: 0.2,
                    CONF_NAME: "Work laptop on network",
                },
                {
                    CONF_PLATFORM: str(ObservationTypes.TEMPLATE),
                    CONF_VALUE_TEMPLATE: '{% set current_time = now().time() %}\n{% set start_time = strptime("07:00", "%H:%M").time() %}\n{% set end_time = strptime("18:30", "%H:%M").time() %}\n{% if start_time <= current_time <= end_time %}\nTrue\n{% else %}\nFalse\n{% endif %}',
                    CONF_P_GIVEN_T: 0.45,
                    CONF_P_GIVEN_F: 0.05,
                    CONF_NAME: "Daylight hours",
                },
            ],
        },
        title="Office occupied",
    )

    # Set up the mock entry
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    hass.states.async_set("sensor.office_illuminance_lux", 50)

    # Move through the options flow steps to edit an observation
    result0 = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result0["type"] is FlowResultType.MENU
    assert result0["step_id"] == str(OptionsFlowSteps.INIT)

    result1 = await hass.config_entries.options.async_configure(
        result0["flow_id"],
        {"next_step_id": str(OptionsFlowSteps.SELECT_EDIT_OBSERVATION)},
    )
    await hass.async_block_till_done()
    assert result1["step_id"] == str(OptionsFlowSteps.SELECT_EDIT_OBSERVATION)
    assert result1["type"] is FlowResultType.FORM
    assert result1["data_schema"].schema[CONF_INDEX].container == {
        "0": "Office is bright (numeric_state)",
        "1": "Work laptop on network (state)",
        "2": "Daylight hours (template)",
    }

    # First test edit a state observation
    result2 = await hass.config_entries.options.async_configure(
        result1["flow_id"], {CONF_INDEX: "1"}
    )
    await hass.async_block_till_done()

    # Confirm that we get the edit observation page
    assert result2["step_id"] == str(ObservationTypes.STATE)
    assert result2["type"] is FlowResultType.FORM

    # Edit all settings
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

    # Confirm the changes to the state config
    assert hass.config_entries.async_get_entry(config_entry.entry_id).options == {
        CONF_NAME: "Office occupied",
        CONF_PROBABILITY_THRESHOLD: 0.5,
        CONF_PRIOR: 0.15,
        CONF_DEVICE_CLASS: "occupancy",
        CONF_OBSERVATIONS: [
            {
                CONF_PLATFORM: str(ObservationTypes.NUMERIC_STATE),
                CONF_ENTITY_ID: "sensor.office_illuminance_lux",
                CONF_ABOVE: 40,
                CONF_P_GIVEN_T: 0.85,
                CONF_P_GIVEN_F: 0.45,
                CONF_NAME: "Office is bright",
            },
            {
                CONF_PLATFORM: str(ObservationTypes.STATE),
                CONF_ENTITY_ID: "sensor.desktop",
                CONF_TO_STATE: "on",
                CONF_P_GIVEN_T: 0.7,
                CONF_P_GIVEN_F: 0.12,
                CONF_NAME: "Desktop on network",
            },
            {
                CONF_PLATFORM: str(ObservationTypes.TEMPLATE),
                CONF_VALUE_TEMPLATE: '{% set current_time = now().time() %}\n{% set start_time = strptime("07:00", "%H:%M").time() %}\n{% set end_time = strptime("18:30", "%H:%M").time() %}\n{% if start_time <= current_time <= end_time %}\nTrue\n{% else %}\nFalse\n{% endif %}',
                CONF_P_GIVEN_T: 0.45,
                CONF_P_GIVEN_F: 0.05,
                CONF_NAME: "Daylight hours",
            },
        ],
    }

    # Next test editing a numeric_state observation
    result0 = await hass.config_entries.options.async_init(config_entry.entry_id)
    result1 = await hass.config_entries.options.async_configure(
        result0["flow_id"],
        {"next_step_id": str(OptionsFlowSteps.SELECT_EDIT_OBSERVATION)},
    )
    await hass.async_block_till_done()
    assert result1["data_schema"].schema[CONF_INDEX].container == {
        "0": "Office is bright (numeric_state)",
        "1": "Desktop on network (state)",
        "2": "Daylight hours (template)",
    }
    result2 = await hass.config_entries.options.async_configure(
        result1["flow_id"], {CONF_INDEX: "0"}
    )
    await hass.async_block_till_done()
    assert result2["step_id"] == str(ObservationTypes.NUMERIC_STATE)
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
                CONF_PLATFORM: str(ObservationTypes.NUMERIC_STATE),
                CONF_ENTITY_ID: "sensor.office_illuminance_lumens",
                CONF_ABOVE: 2000,
                CONF_P_GIVEN_T: 0.8,
                CONF_P_GIVEN_F: 0.4,
                CONF_NAME: "Office is bright",
            },
            {
                CONF_PLATFORM: str(ObservationTypes.STATE),
                CONF_ENTITY_ID: "sensor.desktop",
                CONF_TO_STATE: "on",
                CONF_P_GIVEN_T: 0.7,
                CONF_P_GIVEN_F: 0.12,
                CONF_NAME: "Desktop on network",
            },
            {
                CONF_PLATFORM: str(ObservationTypes.TEMPLATE),
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
    assert result1["data_schema"].schema[CONF_INDEX].container == {
        "0": "Office is bright (numeric_state)",
        "1": "Desktop on network (state)",
        "2": "Daylight hours (template)",
    }
    result2 = await hass.config_entries.options.async_configure(
        result1["flow_id"], {CONF_INDEX: "2"}
    )
    await hass.async_block_till_done()
    assert result2["step_id"] == str(ObservationTypes.TEMPLATE)
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
""",  # changed the end_time
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
                CONF_PLATFORM: str(ObservationTypes.NUMERIC_STATE),
                CONF_ENTITY_ID: "sensor.office_illuminance_lumens",
                CONF_ABOVE: 2000,
                CONF_P_GIVEN_T: 0.8,
                CONF_P_GIVEN_F: 0.4,
                CONF_NAME: "Office is bright",
            },
            {
                CONF_PLATFORM: str(ObservationTypes.STATE),
                CONF_ENTITY_ID: "sensor.desktop",
                CONF_TO_STATE: "on",
                CONF_P_GIVEN_T: 0.7,
                CONF_P_GIVEN_F: 0.12,
                CONF_NAME: "Desktop on network",
            },
            {
                CONF_PLATFORM: str(ObservationTypes.TEMPLATE),
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
                    CONF_PLATFORM: str(ObservationTypes.NUMERIC_STATE),
                    CONF_ENTITY_ID: "sensor.office_illuminance_lux",
                    CONF_ABOVE: 40,
                    CONF_P_GIVEN_T: 0.85,
                    CONF_P_GIVEN_F: 0.45,
                    CONF_NAME: "Office is bright",
                },
                {
                    CONF_PLATFORM: str(ObservationTypes.STATE),
                    CONF_ENTITY_ID: "sensor.work_laptop",
                    CONF_TO_STATE: "on",
                    CONF_P_GIVEN_T: 0.6,
                    CONF_P_GIVEN_F: 0.2,
                    CONF_NAME: "Work laptop on network",
                },
                {
                    CONF_PLATFORM: str(ObservationTypes.TEMPLATE),
                    CONF_VALUE_TEMPLATE: '{% set current_time = now().time() %}\n{% set start_time = strptime("07:00", "%H:%M").time() %}\n{% set end_time = strptime("18:30", "%H:%M").time() %}\n{% if start_time <= current_time <= end_time %}\nTrue\n{% else %}\nFalse\n{% endif %}',
                    CONF_P_GIVEN_T: 0.45,
                    CONF_P_GIVEN_F: 0.05,
                    CONF_NAME: "Daylight hours",
                },
            ],
        },
        title="Office occupied",
    )
    # Set up the config entry
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    hass.states.async_set("sensor.office_illuminance_lux", 50)

    # Move through the options flow to removing observations
    result0 = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result0["type"] is FlowResultType.MENU
    assert result0["step_id"] == str(OptionsFlowSteps.INIT)

    result1 = await hass.config_entries.options.async_configure(
        result0["flow_id"],
        {"next_step_id": str(OptionsFlowSteps.REMOVE_OBSERVATION)},
    )
    await hass.async_block_till_done()

    # Confirm the remove observation page shows correctly with all obs present
    assert result1["step_id"] == str(OptionsFlowSteps.REMOVE_OBSERVATION)
    assert result1["type"] is FlowResultType.FORM
    assert result1["data_schema"].schema[CONF_INDEX].options == {
        "0": "Office is bright (numeric_state)",
        "1": "Work laptop on network (state)",
        "2": "Daylight hours (template)",
    }

    # First test deleting a single state observation
    await hass.config_entries.options.async_configure(
        result1["flow_id"], {CONF_INDEX: ["1"]}
    )
    await hass.async_block_till_done()

    assert hass.config_entries.async_get_entry(config_entry.entry_id).options == {
        CONF_NAME: "Office occupied",
        CONF_PROBABILITY_THRESHOLD: 0.5,
        CONF_PRIOR: 0.15,
        CONF_DEVICE_CLASS: "occupancy",
        CONF_OBSERVATIONS: [
            {
                CONF_PLATFORM: str(ObservationTypes.NUMERIC_STATE),
                CONF_ENTITY_ID: "sensor.office_illuminance_lux",
                CONF_ABOVE: 40,
                CONF_P_GIVEN_T: 0.85,
                CONF_P_GIVEN_F: 0.45,
                CONF_NAME: "Office is bright",
            },
            {
                CONF_PLATFORM: str(ObservationTypes.TEMPLATE),
                CONF_VALUE_TEMPLATE: '{% set current_time = now().time() %}\n{% set start_time = strptime("07:00", "%H:%M").time() %}\n{% set end_time = strptime("18:30", "%H:%M").time() %}\n{% if start_time <= current_time <= end_time %}\nTrue\n{% else %}\nFalse\n{% endif %}',
                CONF_P_GIVEN_T: 0.45,
                CONF_P_GIVEN_F: 0.05,
                CONF_NAME: "Daylight hours",
            },
        ],
    }

    # next delete the two remaining observations
    result0 = await hass.config_entries.options.async_init(config_entry.entry_id)
    result1 = await hass.config_entries.options.async_configure(
        result0["flow_id"],
        {"next_step_id": str(OptionsFlowSteps.REMOVE_OBSERVATION)},
    )
    await hass.async_block_till_done()
    assert result1["step_id"] == str(OptionsFlowSteps.REMOVE_OBSERVATION)
    assert result1["type"] is FlowResultType.FORM
    assert result1["data_schema"].schema[CONF_INDEX].options == {
        "0": "Office is bright (numeric_state)",
        "1": "Daylight hours (template)",
    }

    await hass.config_entries.options.async_configure(
        result1["flow_id"], {CONF_INDEX: ["0", "1"]}
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
        assert result0["step_id"] == USER
        assert result0["type"] is FlowResultType.FORM

        # priors should never be Zero, because then the sensor can never return 'on'
        with pytest.raises(vol.Invalid) as excinfo:
            result1 = await hass.config_entries.flow.async_configure(
                result0["flow_id"],
                {
                    CONF_NAME: "Office occupied",
                    CONF_PROBABILITY_THRESHOLD: 50,
                    CONF_PRIOR: 0,
                },
            )
        assert CONF_PRIOR in excinfo.value.path
        assert excinfo.value.error_message == "extreme_prior_error"

        # priors should never be 100% because then the sensor can never be 'off'
        with pytest.raises(vol.Invalid) as excinfo:
            result1 = await hass.config_entries.flow.async_configure(
                result0["flow_id"],
                {
                    CONF_NAME: "Office occupied",
                    CONF_PROBABILITY_THRESHOLD: 50,
                    CONF_PRIOR: 100,
                },
            )
        assert CONF_PRIOR in excinfo.value.path
        assert excinfo.value.error_message == "extreme_prior_error"

        # Threshold should never be 100% because then the sensor can never be 'on'
        with pytest.raises(vol.Invalid) as excinfo:
            result1 = await hass.config_entries.flow.async_configure(
                result0["flow_id"],
                {
                    CONF_NAME: "Office occupied",
                    CONF_PROBABILITY_THRESHOLD: 100,
                    CONF_PRIOR: 50,
                },
            )
        assert CONF_PROBABILITY_THRESHOLD in excinfo.value.path
        assert excinfo.value.error_message == "extreme_threshold_error"

        # Threshold should never be 0 because then the sensor can never be 'off'
        with pytest.raises(vol.Invalid) as excinfo:
            result1 = await hass.config_entries.flow.async_configure(
                result0["flow_id"],
                {
                    CONF_NAME: "Office occupied",
                    CONF_PROBABILITY_THRESHOLD: 0,
                    CONF_PRIOR: 50,
                },
            )
        assert CONF_PROBABILITY_THRESHOLD in excinfo.value.path
        assert excinfo.value.error_message == "extreme_threshold_error"

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

        assert result1["step_id"] == OBSERVATION_SELECTOR
        assert result1["type"] is FlowResultType.MENU

        result2 = await hass.config_entries.flow.async_configure(
            result1["flow_id"], {"next_step_id": str(ObservationTypes.STATE)}
        )
        await hass.async_block_till_done()

        assert result2["step_id"] == str(ObservationTypes.STATE)
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
        assert result3["step_id"] != OBSERVATION_SELECTOR

        # Observations with a probability of 0 will create certainties
        with pytest.raises(vol.Invalid) as excinfo:
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
        assert CONF_P_GIVEN_T in excinfo.value.path
        assert excinfo.value.error_message == "extreme_prob_given_error"

        # Observations with a probability of 1 will create certainties
        with pytest.raises(vol.Invalid) as excinfo:
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
        assert CONF_P_GIVEN_F in excinfo.value.path
        assert excinfo.value.error_message == "extreme_prob_given_error"
