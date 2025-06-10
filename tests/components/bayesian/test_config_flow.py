"""Test the Config flow for the Bayesian integration."""

from __future__ import annotations

from types import MappingProxyType
from unittest.mock import patch

import pytest
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components.bayesian.config_flow import (
    USER,
    ObservationTypes,
    OptionsFlowSteps,
)
from homeassistant.components.bayesian.const import (
    CONF_P_GIVEN_F,
    CONF_P_GIVEN_T,
    CONF_PRIOR,
    CONF_PROBABILITY_THRESHOLD,
    CONF_TO_STATE,
    DOMAIN,
)
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigSubentry,
    ConfigSubentryDataWithId,
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
    """Test the config flow with an example."""
    with patch(
        "homeassistant.components.bayesian.async_setup_entry", return_value=True
    ):
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
        assert result1["version"] == 1
        assert result1["handler"] == DOMAIN
        assert result1["title"] == "Office occupied"
        assert result1["options"] == {
            CONF_NAME: "Office occupied",
            CONF_PROBABILITY_THRESHOLD: 0.5,
            CONF_PRIOR: 0.15,
            CONF_DEVICE_CLASS: "occupancy",
        }


async def test_subentry_flow(hass: HomeAssistant) -> None:
    """Test the subentry flow with a full example."""
    with patch(
        "homeassistant.components.bayesian.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        # Set up the initial config entry as a mock to isolate testing of subentry flows
        config_entry = MockConfigEntry(
            domain=DOMAIN,
            data={
                CONF_NAME: "Office occupied",
                CONF_PROBABILITY_THRESHOLD: 50,
                CONF_PRIOR: 15,
                CONF_DEVICE_CLASS: "occupancy",
            },
        )
        config_entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        # Open subentry flow
        result = await hass.config_entries.subentries.async_init(
            (config_entry.entry_id, "observation"),
            context={"source": config_entries.SOURCE_USER},
        )
        # Confirm the next page is the observation type selector
        assert result["step_id"] == "user"
        assert result["type"] is FlowResultType.MENU
        assert result["flow_id"] is not None

        # Set up a numeric state observation first
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"], {"next_step_id": str(ObservationTypes.NUMERIC_STATE)}
        )
        await hass.async_block_till_done()

        assert result["step_id"] == str(ObservationTypes.NUMERIC_STATE)
        assert result["type"] is FlowResultType.FORM

        # Set up a numeric range with only 'Above'
        # Also indirectly tests the conversion of proabilities to fractions
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"],
            {
                CONF_ENTITY_ID: "sensor.office_illuminance_lux",
                CONF_ABOVE: 40,
                CONF_P_GIVEN_T: 85,
                CONF_P_GIVEN_F: 45,
                CONF_NAME: "Office is bright",
            },
        )
        await hass.async_block_till_done()

        # Open another subentry flow
        result = await hass.config_entries.subentries.async_init(
            (config_entry.entry_id, "observation"),
            context={"source": config_entries.SOURCE_USER},
        )
        assert result["step_id"] == "user"
        assert result["type"] is FlowResultType.MENU
        assert result["flow_id"] is not None

        # Add a state observation
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"], {"next_step_id": str(ObservationTypes.STATE)}
        )
        await hass.async_block_till_done()

        assert result["step_id"] == str(ObservationTypes.STATE)
        assert result["type"] is FlowResultType.FORM
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"],
            {
                CONF_ENTITY_ID: "sensor.work_laptop",
                CONF_TO_STATE: "on",
                CONF_P_GIVEN_T: 60,
                CONF_P_GIVEN_F: 20,
                CONF_NAME: "Work laptop on network",
            },
        )
        await hass.async_block_till_done()

        # Open another subentry flow
        result = await hass.config_entries.subentries.async_init(
            (config_entry.entry_id, "observation"),
            context={"source": config_entries.SOURCE_USER},
        )
        assert result["step_id"] == "user"
        assert result["type"] is FlowResultType.MENU
        assert result["flow_id"] is not None

        # Lastly, add a template observation
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"], {"next_step_id": str(ObservationTypes.TEMPLATE)}
        )
        await hass.async_block_till_done()

        assert result["step_id"] == str(ObservationTypes.TEMPLATE)
        assert result["type"] is FlowResultType.FORM
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"],
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
            },
        )

        observations = [
            dict(subentry.data) for subentry in config_entry.subentries.values()
        ]
        # assert config_entry["version"] == 1
        assert observations == [
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
        ]

    assert len(mock_setup_entry.mock_calls) == 1


async def test_single_state_observation(hass: HomeAssistant) -> None:
    """Test a Bayesian sensor with just one state observation added.

    This test combines the config flow and the options flow for a single state observation.
    """

    with patch(
        "homeassistant.components.bayesian.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["step_id"] == USER
        assert result["type"] is FlowResultType.FORM

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_NAME: "Anyone home",
                CONF_PROBABILITY_THRESHOLD: 50,
                CONF_PRIOR: 66,
                CONF_DEVICE_CLASS: "occupancy",
            },
        )
        await hass.async_block_till_done()

        # Confirm the config entry is created with the basic options
        assert result["options"] == {
            CONF_NAME: "Anyone home",
            CONF_PROBABILITY_THRESHOLD: 0.5,
            CONF_PRIOR: 0.66,
            CONF_DEVICE_CLASS: "occupancy",
        }

        # Confirm the config entry is created and then retrieve it again
        entry_id = result["result"].entry_id
        config_entry = hass.config_entries.async_get_entry(entry_id)
        assert config_entry is not None
        assert type(config_entry) is ConfigEntry

        # Open a subentry flow
        result = await hass.config_entries.subentries.async_init(
            (config_entry.entry_id, "observation"),
            context={"source": config_entries.SOURCE_USER},
        )
        assert result["step_id"] == "user"
        assert result["type"] is FlowResultType.MENU
        assert result["flow_id"] is not None

        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"], {"next_step_id": str(ObservationTypes.STATE)}
        )
        await hass.async_block_till_done()

        assert result["step_id"] == str(ObservationTypes.STATE)
        assert result["type"] is FlowResultType.FORM
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"],
            {
                CONF_ENTITY_ID: "sensor.kitchen_occupancy",
                CONF_TO_STATE: "on",
                CONF_P_GIVEN_T: 40,
                CONF_P_GIVEN_F: 0.5,
                CONF_NAME: "Kitchen Motion",
            },
        )

        assert config_entry.version == 1
        assert config_entry.options == {
            CONF_NAME: "Anyone home",
            CONF_PROBABILITY_THRESHOLD: 0.5,
            CONF_PRIOR: 0.66,
            CONF_DEVICE_CLASS: "occupancy",
        }
        assert len(config_entry.subentries) == 1
        assert list(config_entry.subentries.values())[0].data == {
            CONF_PLATFORM: CONF_STATE,
            CONF_ENTITY_ID: "sensor.kitchen_occupancy",
            CONF_TO_STATE: "on",
            CONF_P_GIVEN_T: 0.4,
            CONF_P_GIVEN_F: 0.005,
            CONF_NAME: "Kitchen Motion",
        }

    assert len(mock_setup_entry.mock_calls) == 1


async def test_single_numeric_state_observation(hass: HomeAssistant) -> None:
    """Test a Bayesian sensor with just one numeric_state observation added.

    Combines the config flow and the options flow for a single numeric_state observation.
    """

    with patch(
        "homeassistant.components.bayesian.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["step_id"] == USER
        assert result["type"] is FlowResultType.FORM

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_NAME: "Nice day",
                CONF_PROBABILITY_THRESHOLD: 51,
                CONF_PRIOR: 20,
            },
        )
        await hass.async_block_till_done()

        # Open a subentry flow, in this test we are less stringent about checking success as that is covered in other tests
        config_entry = result["result"]
        result = await hass.config_entries.subentries.async_init(
            (config_entry.entry_id, "observation"),
            context={"source": config_entries.SOURCE_USER},
        )

        # select numeric state observation
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"], {"next_step_id": str(ObservationTypes.NUMERIC_STATE)}
        )
        await hass.async_block_till_done()

        assert result["step_id"] == str(ObservationTypes.NUMERIC_STATE)
        assert result["type"] is FlowResultType.FORM
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"],
            {
                CONF_ENTITY_ID: "sensor.outside_temperature",
                CONF_ABOVE: 20,
                CONF_BELOW: 35,
                CONF_P_GIVEN_T: 95,
                CONF_P_GIVEN_F: 8,
                CONF_NAME: "20 - 35 outside",
            },
        )

        assert config_entry.options == {
            CONF_NAME: "Nice day",
            CONF_PROBABILITY_THRESHOLD: 0.51,
            CONF_PRIOR: 0.2,
        }
        assert len(config_entry.subentries) == 1
        assert list(config_entry.subentries.values())[0].data == {
            CONF_PLATFORM: str(ObservationTypes.NUMERIC_STATE),
            CONF_ENTITY_ID: "sensor.outside_temperature",
            CONF_ABOVE: 20,
            CONF_BELOW: 35,
            CONF_P_GIVEN_T: 0.95,
            CONF_P_GIVEN_F: 0.08,
            CONF_NAME: "20 - 35 outside",
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
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["step_id"] == USER
        assert result["type"] is FlowResultType.FORM

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_NAME: "Nice day",
                CONF_PROBABILITY_THRESHOLD: 51,
                CONF_PRIOR: 20,
            },
        )
        await hass.async_block_till_done()
        config_entry = result["result"]
        # Open a subentry flow, in this test we are less stringent about checking success as that is covered in other tests
        result = await hass.config_entries.subentries.async_init(
            (config_entry.entry_id, "observation"),
            context={"source": config_entries.SOURCE_USER},
        )

        # select numeric state observation
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"], {"next_step_id": str(ObservationTypes.NUMERIC_STATE)}
        )
        await hass.async_block_till_done()

        assert result["step_id"] == str(ObservationTypes.NUMERIC_STATE)
        assert result["type"] is FlowResultType.FORM
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"],
            {
                CONF_ENTITY_ID: "sensor.outside_temperature",
                CONF_ABOVE: 20,
                CONF_BELOW: 35,
                CONF_P_GIVEN_T: 95,
                CONF_P_GIVEN_F: 8,
                CONF_NAME: "20 - 35 outside",
            },
        )

        # open a second subentry flow for numeric state observation
        result = await hass.config_entries.subentries.async_init(
            (config_entry.entry_id, "observation"),
            context={"source": config_entries.SOURCE_USER},
        )
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"], {"next_step_id": str(ObservationTypes.NUMERIC_STATE)}
        )
        await hass.async_block_till_done()

        # This should fail as overlapping ranges for the same entity are not allowed
        with pytest.raises(vol.Invalid) as excinfo:
            await hass.config_entries.subentries.async_configure(
                result["flow_id"],
                {
                    CONF_ENTITY_ID: "sensor.outside_temperature",
                    CONF_ABOVE: 30,
                    CONF_BELOW: 40,
                    CONF_P_GIVEN_T: 95,
                    CONF_P_GIVEN_F: 8,
                    CONF_NAME: "30 - 40 outside",
                },
            )
        assert (
            excinfo.value.error_message
            == "Ranges for bayesian numeric state entities must not overlap, but sensor.outside_temperature has overlapping ranges, above:20.0, below:35.0 overlaps with above:30.0, below:40.0."
        )

        # This should fail as above should always be less than below
        with pytest.raises(vol.Invalid) as excinfo:
            await hass.config_entries.subentries.async_configure(
                result["flow_id"],
                {
                    CONF_ENTITY_ID: "sensor.outside_temperature",
                    CONF_ABOVE: 40,
                    CONF_BELOW: 35,
                    CONF_P_GIVEN_T: 95,
                    CONF_P_GIVEN_F: 8,
                    CONF_NAME: "35 - 40 outside",
                },
            )
        assert excinfo.value.error_message == "'above' is greater than 'below'"

        # This should work
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"],
            {
                CONF_ENTITY_ID: "sensor.outside_temperature",
                CONF_ABOVE: 35,
                CONF_BELOW: 40,
                CONF_P_GIVEN_T: 70,
                CONF_P_GIVEN_F: 20,
                CONF_NAME: "35 - 40 outside",
            },
        )
        await hass.async_block_till_done()

        assert config_entry.version == 1
        assert config_entry.options == {
            CONF_NAME: "Nice day",
            CONF_PROBABILITY_THRESHOLD: 0.51,
            CONF_PRIOR: 0.2,
        }
        observations = [
            dict(subentry.data) for subentry in config_entry.subentries.values()
        ]
        assert observations == [
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
        ]

    assert len(mock_setup_entry.mock_calls) == 1


async def test_single_template_observation(hass: HomeAssistant) -> None:
    """Test a Bayesian sensor with just one template observation added.

    Technically a subset of the tests in test_config_flow() but may help to
    narrow down errors more quickly.
    """

    with patch(
        "homeassistant.components.bayesian.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["step_id"] == USER
        assert result["type"] is FlowResultType.FORM

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_NAME: "Paulus Home",
                CONF_PROBABILITY_THRESHOLD: 90,
                CONF_PRIOR: 50,
                CONF_DEVICE_CLASS: "occupancy",
            },
        )
        await hass.async_block_till_done()
        config_entry = result["result"]

        # Open a subentry flow, in this test we are less stringent about checking success as that is covered in other tests
        result = await hass.config_entries.subentries.async_init(
            (config_entry.entry_id, "observation"),
            context={"source": config_entries.SOURCE_USER},
        )
        # Select template observation
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"], {"next_step_id": str(ObservationTypes.TEMPLATE)}
        )
        await hass.async_block_till_done()

        assert result["step_id"] == str(ObservationTypes.TEMPLATE)
        assert result["type"] is FlowResultType.FORM
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"],
            {
                CONF_VALUE_TEMPLATE: "{{is_state('device_tracker.paulus','not_home') and ((as_timestamp(now()) - as_timestamp(states.device_tracker.paulus.last_changed)) > 300)}}",
                CONF_P_GIVEN_T: 5,
                CONF_P_GIVEN_F: 99,
                CONF_NAME: "Not seen in last 5 minutes",
            },
        )

        assert config_entry.version == 1
        assert config_entry.options == {
            CONF_NAME: "Paulus Home",
            CONF_PROBABILITY_THRESHOLD: 0.9,
            CONF_PRIOR: 0.5,
            CONF_DEVICE_CLASS: "occupancy",
        }
        assert len(config_entry.subentries) == 1
        assert list(config_entry.subentries.values())[0].data == {
            CONF_PLATFORM: str(ObservationTypes.TEMPLATE),
            CONF_VALUE_TEMPLATE: "{{is_state('device_tracker.paulus','not_home') and ((as_timestamp(now()) - as_timestamp(states.device_tracker.paulus.last_changed)) > 300)}}",
            CONF_P_GIVEN_T: 0.05,
            CONF_P_GIVEN_F: 0.99,
            CONF_NAME: "Not seen in last 5 minutes",
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
        },
        subentries_data=[
            ConfigSubentryDataWithId(
                data=MappingProxyType(
                    {
                        CONF_PLATFORM: str(ObservationTypes.NUMERIC_STATE),
                        CONF_ENTITY_ID: "sensor.office_illuminance_lux",
                        CONF_ABOVE: 40,
                        CONF_P_GIVEN_T: 0.85,
                        CONF_P_GIVEN_F: 0.45,
                        CONF_NAME: "Office is bright",
                    }
                ),
                subentry_id="01JXCPHRM64Y84GQC58P5EKVHY",
                subentry_type="observation",
                title="Office is bright",
                unique_id=None,
            )
        ],
        title="Office occupied",
    )
    # Setup the mock config entry
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    # Give the sensor a real value
    hass.states.async_set("sensor.office_illuminance_lux", 50)

    # Start the options flow
    result = await hass.config_entries.options.async_init(config_entry.entry_id)

    # Confirm the first page is the form for editing the basic options
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == str(OptionsFlowSteps.INIT)

    # Change all possible settings (name can be changed elsewhere in the UI)
    await hass.config_entries.options.async_configure(
        result["flow_id"],
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
    }
    assert config_entry.subentries == {
        "01JXCPHRM64Y84GQC58P5EKVHY": ConfigSubentry(
            data=MappingProxyType(
                {
                    CONF_PLATFORM: str(ObservationTypes.NUMERIC_STATE),
                    CONF_ENTITY_ID: "sensor.office_illuminance_lux",
                    CONF_ABOVE: 40,
                    CONF_P_GIVEN_T: 0.85,
                    CONF_P_GIVEN_F: 0.45,
                    CONF_NAME: "Office is bright",
                }
            ),
            subentry_id="01JXCPHRM64Y84GQC58P5EKVHY",
            subentry_type="observation",
            title="Office is bright",
            unique_id=None,
        )
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
        },
        subentries_data=[
            ConfigSubentryDataWithId(
                data=MappingProxyType(
                    {
                        CONF_PLATFORM: str(ObservationTypes.NUMERIC_STATE),
                        CONF_ENTITY_ID: "sensor.office_illuminance_lux",
                        CONF_ABOVE: 40,
                        CONF_P_GIVEN_T: 0.85,
                        CONF_P_GIVEN_F: 0.45,
                        CONF_NAME: "Office is bright",
                    }
                ),
                subentry_id="01JXCPHRM64Y84GQC58P5EKVHY",
                subentry_type="observation",
                title="Office is bright",
                unique_id=None,
            ),
            ConfigSubentryDataWithId(
                data=MappingProxyType(
                    {
                        CONF_PLATFORM: str(ObservationTypes.STATE),
                        CONF_ENTITY_ID: "sensor.work_laptop",
                        CONF_TO_STATE: "on",
                        CONF_P_GIVEN_T: 0.6,
                        CONF_P_GIVEN_F: 0.2,
                        CONF_NAME: "Work laptop on network",
                    },
                ),
                subentry_id="13TCPHRM64Y84GQC58P5EKTHF",
                subentry_type="observation",
                title="Work laptop on network",
                unique_id=None,
            ),
            ConfigSubentryDataWithId(
                data=MappingProxyType(
                    {
                        CONF_PLATFORM: str(ObservationTypes.TEMPLATE),
                        CONF_VALUE_TEMPLATE: '{% set current_time = now().time() %}\n{% set start_time = strptime("07:00", "%H:%M").time() %}\n{% set end_time = strptime("18:30", "%H:%M").time() %}\n{% if start_time <= current_time <= end_time %}\nTrue\n{% else %}\nFalse\n{% endif %}',
                        CONF_P_GIVEN_T: 0.45,
                        CONF_P_GIVEN_F: 0.05,
                        CONF_NAME: "Daylight hours",
                    }
                ),
                subentry_id="27TCPHRM64Y84GQC58P5EIES",
                subentry_type="observation",
                title="Daylight hours",
                unique_id=None,
            ),
        ],
        title="Office occupied",
    )

    # Set up the mock entry
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    hass.states.async_set("sensor.office_illuminance_lux", 50)

    # select a subentry for reconfiguration
    result = await config_entry.start_subentry_reconfigure_flow(
        hass, "observation", subentry_id="13TCPHRM64Y84GQC58P5EKTHF"
    )
    await hass.async_block_till_done()

    # confirm the first page is the form for editing the observation
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    # Edit all settings
    await hass.config_entries.subentries.async_configure(
        result["flow_id"],
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
    }
    observations = [
        dict(subentry.data)
        for subentry in hass.config_entries.async_get_entry(
            config_entry.entry_id
        ).subentries.values()
    ]
    assert observations == [
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
    ]

    # Next test editing a numeric_state observation
    # select the subentry for reconfiguration
    result = await config_entry.start_subentry_reconfigure_flow(
        hass, "observation", subentry_id="01JXCPHRM64Y84GQC58P5EKVHY"
    )
    await hass.async_block_till_done()

    # confirm the first page is the form for editing the observation
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    await hass.async_block_till_done()

    await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {
            CONF_ENTITY_ID: "sensor.office_illuminance_lumens",
            CONF_ABOVE: 2000,
            CONF_P_GIVEN_T: 80,
            CONF_P_GIVEN_F: 40,
            CONF_NAME: "Office is bright",
        },
    )
    await hass.async_block_till_done()
    # Confirm the changes to the state config
    assert hass.config_entries.async_get_entry(config_entry.entry_id).options == {
        CONF_NAME: "Office occupied",
        CONF_PROBABILITY_THRESHOLD: 0.5,
        CONF_PRIOR: 0.15,
        CONF_DEVICE_CLASS: "occupancy",
    }
    observations = [
        dict(subentry.data)
        for subentry in hass.config_entries.async_get_entry(
            config_entry.entry_id
        ).subentries.values()
    ]
    assert observations == [
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
    ]

    # Next test editing a template observation
    # select the subentry for reconfiguration
    result = await config_entry.start_subentry_reconfigure_flow(
        hass, "observation", subentry_id="01JXCPHRM64Y84GQC58P5EKVHY"
    )
    await hass.async_block_till_done()

    # confirm the first page is the form for editing the observation
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"
    await hass.async_block_till_done()

    await hass.config_entries.subentries.async_configure(
        result["flow_id"],
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
    # Confirm the changes to the state config
    assert hass.config_entries.async_get_entry(config_entry.entry_id).options == {
        CONF_NAME: "Office occupied",
        CONF_PROBABILITY_THRESHOLD: 0.5,
        CONF_PRIOR: 0.15,
        CONF_DEVICE_CLASS: "occupancy",
    }
    observations = [
        dict(subentry.data)
        for subentry in hass.config_entries.async_get_entry(
            config_entry.entry_id
        ).subentries.values()
    ]
    assert observations == [
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
    ]


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

        # Now lets submit a valid config so we can test the subentry flows
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
        config_entry = result1["result"]

        # Open a subentry flow
        result = await hass.config_entries.subentries.async_init(
            (config_entry.entry_id, "observation"),
            context={"source": config_entries.SOURCE_USER},
        )

        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"], {"next_step_id": str(ObservationTypes.STATE)}
        )
        await hass.async_block_till_done()

        assert result["step_id"] == str(ObservationTypes.STATE)
        assert result["type"] is FlowResultType.FORM
        current_step = result["step_id"]

        # Observations with equal probabilities have no effect
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"],
            {
                CONF_ENTITY_ID: "sensor.work_laptop",
                CONF_TO_STATE: "on",
                CONF_P_GIVEN_T: 60,
                CONF_P_GIVEN_F: 60,
                CONF_NAME: "Work laptop on network",
            },
        )
        await hass.async_block_till_done()
        assert result["step_id"] == current_step
        assert result["errors"] == {"base": "equal_probabilities"}

        # Observations with a probability of 0 will create certainties
        with pytest.raises(vol.Invalid) as excinfo:
            result = await hass.config_entries.subentries.async_configure(
                result["flow_id"],
                {
                    CONF_ENTITY_ID: "sensor.work_laptop",
                    CONF_TO_STATE: "on",
                    CONF_P_GIVEN_T: 0,
                    CONF_P_GIVEN_F: 60,
                    CONF_NAME: "Work laptop on network",
                },
            )
        assert CONF_P_GIVEN_T in excinfo.value.path
        assert excinfo.value.error_message == "extreme_prob_given_error"

        # Observations with a probability of 1 will create certainties
        with pytest.raises(vol.Invalid) as excinfo:
            result = await hass.config_entries.subentries.async_configure(
                result["flow_id"],
                {
                    CONF_ENTITY_ID: "sensor.work_laptop",
                    CONF_TO_STATE: "on",
                    CONF_P_GIVEN_T: 60,
                    CONF_P_GIVEN_F: 100,
                    CONF_NAME: "Work laptop on network",
                },
            )
        assert CONF_P_GIVEN_F in excinfo.value.path
        assert excinfo.value.error_message == "extreme_prob_given_error"
