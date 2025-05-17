"""Mocks for the miele component."""

from unittest.mock import MagicMock

from homeassistant.components.miele.const import DOMAIN
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry, load_json_object_fixture


async def mock_sensor_transitions(
    hass: HomeAssistant,
    mock_miele_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    device_name: str,
    json_sequence: list[str],
    expected_sensor_states: dict[str, list[str]],
) -> None:
    """Fixture for setting up parametrized tests for transitions between appliance status."""

    num_steps = len(json_sequence) + 1  # +1 for the initial fixture

    # check that all expected sensor states have the same number of steps
    for sensor_suffix, states in expected_sensor_states.items():
        assert len(states) == num_steps, (
            f"Inconsistent number of steps for sensor '{sensor_suffix}'"
        )

    # for the initial state loaded from the fixture
    step_index = 0
    check_sensor_state(hass, device_name, expected_sensor_states, 0)

    # for each additional step in the sequence, load the corresponding JSON file
    for step_index, json_file in enumerate(json_sequence, start=1):
        # load the JSON file for the current step and force update of sensors
        mock_miele_client.get_devices.return_value = load_json_object_fixture(
            json_file, DOMAIN
        )
        await hass.config_entries.async_reload(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        # check that the state of each sensor matches the expected state
        check_sensor_state(hass, device_name, expected_sensor_states, step_index)


def check_sensor_state(
    hass: HomeAssistant,
    device_name: str,
    expected_sensor_states: dict[str, list[str]],
    step_index: int,
):
    """Check the state of each sensor matches the expected state."""

    for sensor_suffix, expected_states in expected_sensor_states.items():
        sensor_entity = (
            f"sensor.{device_name}"
            if sensor_suffix == ""
            else f"sensor.{device_name}_{sensor_suffix}"
        )
        state = hass.states.get(sensor_entity)
        expected = expected_states[step_index]

        assert state is not None, f"Missing entity: {sensor_entity}"
        assert state.state == expected, (
            f"[{sensor_entity}] Step {step_index + 1}: got {state.state}, expected {expected}"
        )
