"""Test the alarm outputs, alarm inputs and holidays of a Hikvision device."""

from functools import partial
from unittest.mock import MagicMock

from freezegun.api import FrozenDateTimeFactory
from pyhik.image import ImageWriteResult
from pyhik.isapi import InputPort, ISAPIAuthError, ISAPIError, ISAPINotSupportedError
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed

from homeassistant.components.hikvision.coordinator import (
    DEVICE_SCAN_INTERVAL,
    SCAN_INTERVAL,
    HikvisionDeviceCoordinator,
)
from homeassistant.components.switch import (
    DOMAIN as SWITCH_DOMAIN,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.config_entries import SOURCE_REAUTH
from homeassistant.const import (
    ATTR_ENTITY_ID,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import setup_integration
from .conftest import TEST_DEVICE_ID

OUTPUT_1 = "switch.front_camera_alarm_output_1"
OUTPUT_2 = "switch.front_camera_alarm_output_2"
INPUT_1 = "switch.front_camera_alarm_input_1_enabled"
INPUT_1_STATE = "binary_sensor.front_camera_alarm_input_1"
HOLIDAY = "switch.front_camera_christmas"


@pytest.fixture
def platforms() -> list[Platform]:
    """Return platforms to load during test."""
    return [Platform.SWITCH, Platform.BINARY_SENSOR]


async def _async_poll(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    freezer.tick(DEVICE_SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)


def _states(hass: HomeAssistant, *entity_ids: str) -> dict[str, str]:
    return {entity_id: hass.states.get(entity_id).state for entity_id in entity_ids}


@pytest.mark.usefixtures(
    "mock_hikcamera", "mock_image_settings", "mock_device_controls"
)
async def test_an_entity_for_each_control(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test each output, input and holiday gets its entities, in Controls."""
    await setup_integration(hass, mock_config_entry)

    assert _states(hass, OUTPUT_1, OUTPUT_2, INPUT_1, INPUT_1_STATE, HOLIDAY) == {
        OUTPUT_1: STATE_OFF,
        OUTPUT_2: STATE_ON,
        INPUT_1: STATE_ON,
        INPUT_1_STATE: STATE_OFF,
        HOLIDAY: STATE_OFF,
    }
    assert hass.states.get(OUTPUT_1).name == "Front Camera Alarm output 1"
    assert hass.states.get(INPUT_1).name == "Front Camera Alarm input 1 enabled"
    assert hass.states.get(INPUT_1_STATE).name == "Front Camera Alarm input 1"
    assert hass.states.get(HOLIDAY).name == "Front Camera Christmas"
    # Its dates, as the device gives them.
    attributes = hass.states.get(HOLIDAY).attributes
    assert (attributes["mode"], attributes["start"], attributes["end"]) == (
        "date",
        "2026-12-24",
        "2026-12-26",
    )
    device = device_registry.async_get_device_by_identifier(
        ("hikvision", TEST_DEVICE_ID), mock_config_entry.entry_id
    )
    assert device is not None
    for entity_id, key in (
        (OUTPUT_1, "alarm_output_1"),
        (OUTPUT_2, "alarm_output_2"),
        (INPUT_1, "alarm_input_1"),
        (INPUT_1_STATE, "alarm_input_state_1"),
        (HOLIDAY, "holiday_1"),
    ):
        entry = entity_registry.async_get(entity_id)
        assert entry is not None
        assert entry.unique_id == f"{TEST_DEVICE_ID}_{key}"
        # Controls, on the device itself.
        assert entry.entity_category is None
        assert entry.disabled_by is None
        assert entry.device_id == device.id


@pytest.mark.usefixtures("mock_hikcamera", "mock_device_controls")
async def test_without_image_settings(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_isapi_client: MagicMock,
) -> None:
    """Test a device without image settings still gets its controls.

    Its client stays open for them.
    """
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get(OUTPUT_1).state == STATE_OFF
    [coordinator] = mock_config_entry.runtime_data.image_coordinators
    assert isinstance(coordinator, HikvisionDeviceCoordinator)
    mock_isapi_client.return_value.close.assert_not_called()


@pytest.mark.usefixtures("mock_hikcamera")
async def test_none_without_controls(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_isapi_client: MagicMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test a device without any of them gets none, and its client is closed."""
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.runtime_data.image_coordinators == []
    mock_isapi_client.return_value.close.assert_called_once()
    assert not hass.states.async_entity_ids(SWITCH_DOMAIN)


@pytest.mark.usefixtures(
    "mock_hikcamera", "mock_image_settings", "mock_device_controls"
)
@pytest.mark.parametrize(
    ("service", "entity_id", "method", "args", "state"),
    [
        (SERVICE_TURN_ON, OUTPUT_1, "set_output_active", ("1", True), STATE_ON),
        (SERVICE_TURN_OFF, OUTPUT_2, "set_output_active", ("2", False), STATE_OFF),
        (SERVICE_TURN_OFF, INPUT_1, "set_input_enabled", ("1", False), STATE_OFF),
        (SERVICE_TURN_ON, INPUT_1, "set_input_enabled", ("1", True), STATE_ON),
        (SERVICE_TURN_ON, HOLIDAY, "set_holiday_enabled", ("1", True), STATE_ON),
        (SERVICE_TURN_OFF, HOLIDAY, "set_holiday_enabled", ("1", False), STATE_OFF),
    ],
)
async def test_turn_on_off(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_isapi_client: MagicMock,
    service: str,
    entity_id: str,
    method: str,
    args: tuple[object, ...],
    state: str,
) -> None:
    """Test a switch sets its control, and shows it."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        SWITCH_DOMAIN, service, {ATTR_ENTITY_ID: entity_id}, blocking=True
    )
    await hass.async_block_till_done(wait_background_tasks=True)

    getattr(mock_isapi_client.return_value, method).assert_called_once_with(*args)
    assert hass.states.get(entity_id).state == state


@pytest.mark.usefixtures("mock_hikcamera", "mock_device_controls")
async def test_a_pulse_output_goes_back_at_the_next_poll(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_isapi_client: MagicMock,
    device_controls: dict[str, dict[str, bool]],
) -> None:
    """Test an output the device turns back off by itself shows off again."""
    await setup_integration(hass, mock_config_entry)
    client = mock_isapi_client.return_value
    # The device pulses it: it is not active by the time it is read again.
    client.set_output_active.side_effect = None
    client.set_output_active.return_value = ImageWriteResult(True, 200, "ok")

    await hass.services.async_call(
        SWITCH_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: OUTPUT_1}, blocking=True
    )
    await hass.async_block_till_done(wait_background_tasks=True)

    # Read again after the write.
    assert hass.states.get(OUTPUT_1).state == STATE_OFF
    assert device_controls["outputs"]["1"] is False


@pytest.mark.usefixtures(
    "mock_hikcamera", "mock_image_settings", "mock_device_controls"
)
async def test_a_few_requests_a_minute(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_isapi_client: MagicMock,
) -> None:
    """Test the controls are read once a minute, every state in one request.

    The input list gives whether each input raises alarms, and the outputs are
    listed once, when the entry is set up.
    """
    await setup_integration(hass, mock_config_entry)
    client = mock_isapi_client.return_value
    statuses = client.get_io_status.call_count
    polls = client.get_image_values.call_count

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert client.get_image_values.call_count == polls + 1
    assert client.get_io_status.call_count == statuses

    await _async_poll(hass, freezer)

    assert client.get_io_status.call_count == statuses + 1
    client.get_output_ports.assert_called_once()
    assert client.get_input_ports.call_count == 2
    assert client.get_holidays.call_count == 2
    client.get_output_active.assert_not_called()
    client.get_input_active.assert_not_called()
    client.get_input_enabled.assert_not_called()


@pytest.mark.usefixtures("mock_hikcamera", "mock_device_controls")
@pytest.mark.parametrize("status_list", [False])
async def test_each_port_is_read_without_a_status_list(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_isapi_client: MagicMock,
) -> None:
    """Test a device without the status list is read port by port.

    It is not asked for the list again.
    """
    await setup_integration(hass, mock_config_entry)
    client = mock_isapi_client.return_value

    assert _states(hass, OUTPUT_1, OUTPUT_2, INPUT_1_STATE) == {
        OUTPUT_1: STATE_OFF,
        OUTPUT_2: STATE_ON,
        INPUT_1_STATE: STATE_OFF,
    }
    await _async_poll(hass, freezer)

    client.get_io_status.assert_called_once()
    assert client.get_output_active.call_count == 4
    assert client.get_input_active.call_count == 2


@pytest.mark.usefixtures("mock_hikcamera", "mock_device_controls")
@pytest.mark.parametrize("status_list", [False])
@pytest.mark.parametrize(
    ("error", "kept"),
    [
        (ISAPINotSupportedError("not supported", 403, "notSupport"), False),
        (ISAPIAuthError("Insufficient permissions", 403, "lowPrivilege"), False),
        (ISAPIError("Request failed with status 500", 500, "deviceError"), True),
    ],
)
async def test_a_listed_output_the_device_refuses_gets_no_switch(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_isapi_client: MagicMock,
    error: ISAPIError,
    kept: bool,
) -> None:
    """Test a listed output whose first read is refused is left out, and not polled.

    One that only failed now keeps its switch, unavailable until it is read.
    """
    read = mock_isapi_client.return_value.get_output_active
    answer = read.side_effect

    def _read(asked: str) -> bool:
        if asked == "2":
            raise error
        return answer(asked)

    read.side_effect = _read
    # A new bound method at each lookup, as with the real client.
    type(mock_isapi_client.return_value).get_output_active = property(
        lambda _: partial(read)
    )
    await setup_integration(hass, mock_config_entry)
    asked = [call.args[0] for call in read.call_args_list].count("2")

    await _async_poll(hass, freezer)

    state = hass.states.get(OUTPUT_2)
    if kept:
        assert state is not None
        assert state.state == STATE_UNAVAILABLE
        assert [call.args[0] for call in read.call_args_list].count("2") == asked + 1
    else:
        assert state is None
        assert [call.args[0] for call in read.call_args_list].count("2") == asked
    assert not hass.config_entries.flow.async_progress()


@pytest.mark.usefixtures("mock_hikcamera", "mock_device_controls")
@pytest.mark.parametrize("status_list", [False])
@pytest.mark.parametrize(
    ("error", "kept"),
    [
        (ISAPINotSupportedError("not supported", 403, "notSupport"), False),
        (ISAPIAuthError("Insufficient permissions", 403, "lowPrivilege"), False),
        (ISAPIError("Request failed with status 500", 500, "deviceError"), True),
    ],
)
async def test_an_input_whose_signal_the_device_refuses_keeps_its_switch(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_isapi_client: MagicMock,
    error: ISAPIError,
    kept: bool,
) -> None:
    """Test an input whose signal is refused at its first read gets no sensor.

    Its switch stays, and its signal is not asked again. One that only failed now
    keeps its sensor, unavailable until it is read.
    """
    read = mock_isapi_client.return_value.get_input_active
    read.side_effect = error
    await setup_integration(hass, mock_config_entry)
    asked = read.call_count

    await _async_poll(hass, freezer)

    assert hass.states.get(INPUT_1).state == STATE_ON
    state = hass.states.get(INPUT_1_STATE)
    if kept:
        assert state is not None
        assert state.state == STATE_UNAVAILABLE
        assert read.call_count == asked + 1
    else:
        assert state is None
        assert read.call_count == asked
    assert not hass.config_entries.flow.async_progress()


@pytest.mark.usefixtures("mock_hikcamera", "mock_device_controls")
@pytest.mark.parametrize(
    ("error", "kept"),
    [
        (ISAPINotSupportedError("not supported", 403, "notSupport"), False),
        (ISAPIError("Request failed with status 500", 500, "deviceError"), True),
    ],
)
async def test_an_input_list_without_the_flag_is_read_port_by_port(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_isapi_client: MagicMock,
    error: ISAPIError,
    kept: bool,
) -> None:
    """Test an input the list does not say is enabled is read by itself.

    One the device refuses gets no switch.
    """
    client = mock_isapi_client.return_value
    client.get_input_ports.side_effect = lambda proxy=False: [
        InputPort(id="1", name="Door"),
        InputPort(id="2", name="Window"),
    ]
    read = client.get_input_enabled.side_effect

    def _read(asked: str) -> bool:
        if asked == "2":
            raise error
        return read(asked)

    client.get_input_enabled.side_effect = _read
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get(INPUT_1).state == STATE_ON
    state = hass.states.get("switch.front_camera_alarm_input_2_enabled")
    if kept:
        assert state is not None
        assert state.state == STATE_UNAVAILABLE
    else:
        assert state is None


@pytest.mark.usefixtures("mock_hikcamera", "mock_device_controls")
async def test_follows_the_device(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    device_controls: dict[str, dict[str, bool]],
) -> None:
    """Test a change made on the device shows at the next poll."""
    await setup_integration(hass, mock_config_entry)

    device_controls["holidays"]["1"] = True
    device_controls["inputs"]["1"] = False
    device_controls["input_states"]["1"] = True
    device_controls["outputs"]["1"] = True
    await _async_poll(hass, freezer)

    assert _states(hass, HOLIDAY, INPUT_1, INPUT_1_STATE, OUTPUT_1) == {
        HOLIDAY: STATE_ON,
        INPUT_1: STATE_OFF,
        INPUT_1_STATE: STATE_ON,
        OUTPUT_1: STATE_ON,
    }


@pytest.mark.usefixtures("mock_hikcamera", "mock_device_controls")
async def test_unavailable_while_it_cannot_be_read(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_isapi_client: MagicMock,
) -> None:
    """Test what cannot be read now is unavailable, and comes back.

    Without the states, the inputs' flags and the holidays are still shown.
    """
    await setup_integration(hass, mock_config_entry)
    client = mock_isapi_client.return_value
    status = client.get_io_status.side_effect
    client.get_io_status.side_effect = ISAPIError("busy", 503)

    await _async_poll(hass, freezer)

    assert _states(hass, OUTPUT_1, INPUT_1_STATE, INPUT_1, HOLIDAY) == {
        OUTPUT_1: STATE_UNAVAILABLE,
        INPUT_1_STATE: STATE_UNAVAILABLE,
        INPUT_1: STATE_ON,
        HOLIDAY: STATE_OFF,
    }

    client.get_io_status.side_effect = status
    await _async_poll(hass, freezer)

    assert hass.states.get(OUTPUT_1).state == STATE_OFF


@pytest.mark.usefixtures("mock_hikcamera", "mock_device_controls")
async def test_a_holiday_that_is_gone_is_unavailable(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_isapi_client: MagicMock,
    device_controls: dict[str, dict[str, bool]],
) -> None:
    """Test a holiday removed on the device, or a list that fails, is unavailable.

    A holiday added meanwhile waits for the next setup.
    """
    await setup_integration(hass, mock_config_entry)
    device_controls["holidays"] = {"2": True}

    await _async_poll(hass, freezer)

    assert hass.states.get(HOLIDAY).state == STATE_UNAVAILABLE
    assert hass.states.get("switch.front_camera_holiday2") is None

    device_controls["holidays"] = {"1": True}
    await _async_poll(hass, freezer)
    assert hass.states.get(HOLIDAY).state == STATE_ON

    mock_isapi_client.return_value.get_holidays.side_effect = ISAPIError("busy", 503)
    await _async_poll(hass, freezer)
    assert hass.states.get(HOLIDAY).state == STATE_UNAVAILABLE


@pytest.mark.usefixtures("mock_device_controls")
async def test_rejected_password_while_reading_starts_reauth(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_hikcamera: MagicMock,
    mock_isapi_client: MagicMock,
) -> None:
    """Test a 401 stops everything and asks for new credentials.

    Nothing more is asked with the rejected password.
    """
    await setup_integration(hass, mock_config_entry)
    client = mock_isapi_client.return_value
    client.get_input_ports.side_effect = ISAPIAuthError("Invalid credentials", 401)
    statuses = client.get_io_status.call_count

    await _async_poll(hass, freezer)

    assert client.get_io_status.call_count == statuses
    mock_hikcamera.return_value.disconnect.assert_called_once()
    assert hass.states.get(OUTPUT_1).state == STATE_UNAVAILABLE
    flows = hass.config_entries.flow.async_progress()
    assert [flow["context"]["source"] for flow in flows] == [SOURCE_REAUTH]


@pytest.mark.usefixtures("mock_device_controls")
async def test_rejected_password_while_listing_the_ports_starts_reauth(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hikcamera: MagicMock,
    mock_isapi_client: MagicMock,
) -> None:
    """Test a 401 when the ports are listed at setup stops everything too."""
    mock_isapi_client.return_value.get_output_ports.side_effect = ISAPIAuthError(
        "Invalid credentials", 401
    )
    await setup_integration(hass, mock_config_entry)
    await hass.async_block_till_done(wait_background_tasks=True)

    mock_isapi_client.return_value.get_input_ports.assert_not_called()
    mock_hikcamera.return_value.disconnect.assert_called()
    flows = hass.config_entries.flow.async_progress()
    assert [flow["context"]["source"] for flow in flows] == [SOURCE_REAUTH]


@pytest.mark.usefixtures("mock_hikcamera", "mock_device_controls")
@pytest.mark.parametrize(
    "error",
    [
        ISAPIError("busy", 503),
        ISAPIAuthError("Insufficient permissions", 403, "lowPrivilege"),
    ],
)
async def test_what_cannot_be_listed_gets_no_entity(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_isapi_client: MagicMock,
    error: ISAPIError,
) -> None:
    """Test outputs or holidays that cannot be listed leave out only theirs.

    Not allowed is not a reauthentication.
    """
    client = mock_isapi_client.return_value
    client.get_output_ports.side_effect = error
    client.get_holidays.side_effect = error
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get(OUTPUT_1) is None
    assert hass.states.get(HOLIDAY) is None
    assert hass.states.get(INPUT_1).state == STATE_ON
    assert not hass.config_entries.flow.async_progress()


@pytest.mark.usefixtures("mock_hikcamera", "mock_device_controls")
async def test_refused_change(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_isapi_client: MagicMock,
) -> None:
    """Test a change the device refuses is an error, and nothing changes."""
    await setup_integration(hass, mock_config_entry)
    client = mock_isapi_client.return_value
    client.set_holiday_enabled.side_effect = None
    client.set_holiday_enabled.return_value = ImageWriteResult(
        False, 403, "invalidOperation"
    )

    with pytest.raises(HomeAssistantError, match="invalidOperation"):
        await hass.services.async_call(
            SWITCH_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: HOLIDAY}, blocking=True
        )

    assert hass.states.get(HOLIDAY).state == STATE_OFF


@pytest.mark.usefixtures("mock_device_controls")
async def test_rejected_password_while_changing_starts_reauth(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hikcamera: MagicMock,
    mock_isapi_client: MagicMock,
) -> None:
    """Test a 401 for a change stops everything and asks for new credentials."""
    await setup_integration(hass, mock_config_entry)
    mock_isapi_client.return_value.set_output_active.side_effect = ISAPIAuthError(
        "Invalid credentials", 401
    )

    with pytest.raises(HomeAssistantError, match="rejected the username or password"):
        await hass.services.async_call(
            SWITCH_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: OUTPUT_1}, blocking=True
        )
    await hass.async_block_till_done(wait_background_tasks=True)

    mock_hikcamera.return_value.disconnect.assert_called_once()
    flows = hass.config_entries.flow.async_progress()
    assert [flow["context"]["source"] for flow in flows] == [SOURCE_REAUTH]


@pytest.mark.usefixtures("mock_hik_nvr", "mock_device_controls")
@pytest.mark.parametrize("amount_of_channels", [2])
async def test_nvr_cameras_ports_are_on_their_channels(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_isapi_client: MagicMock,
    device_controls: dict[str, dict[str, bool]],
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test the ports of an NVR's cameras are on their channel, by their own number.

    The NVR's own stay on the NVR. Their states come from the NVR's proxy, in one
    request.
    """
    device_controls["proxy_outputs"] = {"201": True}
    device_controls["proxy_inputs"] = {"203": False}
    device_controls["input_states"]["203"] = True
    await setup_integration(hass, mock_config_entry)

    channel_output = "switch.front_camera_channel_2_alarm_output_1"
    channel_input = "switch.front_camera_channel_2_alarm_input_3_enabled"
    channel_state = "binary_sensor.front_camera_channel_2_alarm_input_3"
    assert _states(hass, channel_output, channel_input, channel_state, OUTPUT_1) == {
        channel_output: STATE_ON,
        channel_input: STATE_OFF,
        channel_state: STATE_ON,
        OUTPUT_1: STATE_OFF,
    }
    for entity_id, unique_id, identifier in (
        (channel_output, f"{TEST_DEVICE_ID}_alarm_output_201", f"{TEST_DEVICE_ID}_2"),
        (channel_input, f"{TEST_DEVICE_ID}_alarm_input_203", f"{TEST_DEVICE_ID}_2"),
        (OUTPUT_1, f"{TEST_DEVICE_ID}_alarm_output_1", TEST_DEVICE_ID),
    ):
        entry = entity_registry.async_get(entity_id)
        assert entry is not None
        assert entry.unique_id == unique_id
        device = device_registry.async_get(entry.device_id)
        assert device is not None
        assert device.identifiers == {("hikvision", identifier)}
    client = mock_isapi_client.return_value
    assert {
        call.kwargs.get("proxy") for call in client.get_io_status.call_args_list
    } == {
        False,
        True,
    }

    await hass.services.async_call(
        SWITCH_DOMAIN, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: channel_output}, blocking=True
    )
    client.set_output_active.assert_called_once_with("201", False)


@pytest.mark.usefixtures("mock_hikcamera", "mock_device_controls")
@pytest.mark.parametrize("platforms", [[Platform.SWITCH]])
async def test_no_input_sensor_without_its_platform(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the inputs' switches do not need the binary sensor platform."""
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get(INPUT_1).state == STATE_ON
    assert hass.states.get(INPUT_1_STATE) is None
