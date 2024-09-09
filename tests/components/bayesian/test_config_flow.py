"""Test the Config flow for the Bayesian integration."""

from __future__ import annotations

from unittest.mock import patch

from homeassistant import config_entries
from homeassistant.components.bayesian import DOMAIN
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
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


async def test_config_flow(hass: HomeAssistant) -> None:
    """Test the config flow."""
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

    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "init"

    # TODO Test editing the basic settings
