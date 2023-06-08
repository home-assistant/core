"""The tests for the Rfxtrx sensor platform."""
import pytest

from homeassistant.components.rfxtrx import DOMAIN
from homeassistant.components.rfxtrx.const import ATTR_EVENT
from homeassistant.const import STATE_UNKNOWN
from homeassistant.core import HomeAssistant, State

from .conftest import create_rfx_test_cfg

from tests.common import MockConfigEntry, mock_restore_cache

EVENT_SMOKE_DETECTOR_PANIC = "08200300a109000670"
EVENT_SMOKE_DETECTOR_NO_PANIC = "08200300a109000770"

EVENT_MOTION_DETECTOR_MOTION = "08200100a109000470"
EVENT_MOTION_DETECTOR_NO_MOTION = "08200100a109000570"

EVENT_LIGHT_DETECTOR_LIGHT = "08200100a109001570"
EVENT_LIGHT_DETECTOR_DARK = "08200100a109001470"

EVENT_AC_118CDEA_2_ON = "0b1100100118cdea02010f70"


async def test_one(hass: HomeAssistant, rfxtrx) -> None:
    """Test with 1 sensor."""
    entry_data = create_rfx_test_cfg(devices={"0b1100cd0213c7f230010f71": {}})
    mock_entry = MockConfigEntry(domain="rfxtrx", unique_id=DOMAIN, data=entry_data)

    mock_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.ac_213c7f2_48")
    assert state
    assert state.state == STATE_UNKNOWN
    assert state.attributes.get("friendly_name") == "AC 213c7f2:48"


async def test_one_pt2262(hass: HomeAssistant, rfxtrx) -> None:
    """Test with 1 PT2262 sensor."""
    entry_data = create_rfx_test_cfg(
        devices={
            "0913000022670e013970": {
                "data_bits": 4,
                "command_on": 0xE,
                "command_off": 0x7,
            }
        }
    )
    mock_entry = MockConfigEntry(domain="rfxtrx", unique_id=DOMAIN, data=entry_data)

    mock_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()
    await hass.async_start()

    state = hass.states.get("binary_sensor.pt2262_22670e")
    assert state
    assert state.state == STATE_UNKNOWN
    assert state.attributes.get("friendly_name") == "PT2262 22670e"

    await rfxtrx.signal("0913000022670e013970")
    state = hass.states.get("binary_sensor.pt2262_22670e")
    assert state.state == "on"

    await rfxtrx.signal("09130000226707013d70")
    state = hass.states.get("binary_sensor.pt2262_22670e")
    assert state.state == "off"


async def test_pt2262_unconfigured(hass: HomeAssistant, rfxtrx) -> None:
    """Test with discovery for PT2262."""
    entry_data = create_rfx_test_cfg(
        devices={"0913000022670e013970": {}, "09130000226707013970": {}}
    )
    mock_entry = MockConfigEntry(domain="rfxtrx", unique_id=DOMAIN, data=entry_data)

    mock_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()
    await hass.async_start()

    state = hass.states.get("binary_sensor.pt2262_22670e")
    assert state
    assert state.state == STATE_UNKNOWN
    assert state.attributes.get("friendly_name") == "PT2262 22670e"

    state = hass.states.get("binary_sensor.pt2262_226707")
    assert state
    assert state.state == STATE_UNKNOWN
    assert state.attributes.get("friendly_name") == "PT2262 226707"


@pytest.mark.parametrize(
    ("state", "event"),
    [["on", "0b1100cd0213c7f230010f71"], ["off", "0b1100cd0213c7f230000f71"]],
)
async def test_state_restore(hass: HomeAssistant, rfxtrx, state, event) -> None:
    """State restoration."""

    entity_id = "binary_sensor.ac_213c7f2_48"

    mock_restore_cache(hass, [State(entity_id, state, attributes={ATTR_EVENT: event})])

    entry_data = create_rfx_test_cfg(devices={"0b1100cd0213c7f230010f71": {}})
    mock_entry = MockConfigEntry(domain="rfxtrx", unique_id=DOMAIN, data=entry_data)

    mock_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == state


async def test_several(hass: HomeAssistant, rfxtrx) -> None:
    """Test with 3."""
    entry_data = create_rfx_test_cfg(
        devices={
            "0b1100cd0213c7f230010f71": {},
            "0b1100100118cdea02010f70": {},
            "0b1100100118cdea03010f70": {},
        }
    )
    mock_entry = MockConfigEntry(domain="rfxtrx", unique_id=DOMAIN, data=entry_data)

    mock_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.ac_213c7f2_48")
    assert state
    assert state.state == STATE_UNKNOWN
    assert state.attributes.get("friendly_name") == "AC 213c7f2:48"

    state = hass.states.get("binary_sensor.ac_118cdea_2")
    assert state
    assert state.state == STATE_UNKNOWN
    assert state.attributes.get("friendly_name") == "AC 118cdea:2"

    state = hass.states.get("binary_sensor.ac_118cdea_3")
    assert state
    assert state.state == STATE_UNKNOWN
    assert state.attributes.get("friendly_name") == "AC 118cdea:3"

    # "2: Group on"
    await rfxtrx.signal("0b1100100118cdea03040f70")
    assert hass.states.get("binary_sensor.ac_118cdea_2").state == "on"
    assert hass.states.get("binary_sensor.ac_118cdea_3").state == "on"

    # "2: Group off"
    await rfxtrx.signal("0b1100100118cdea03030f70")
    assert hass.states.get("binary_sensor.ac_118cdea_2").state == "off"
    assert hass.states.get("binary_sensor.ac_118cdea_3").state == "off"


async def test_discover(hass: HomeAssistant, rfxtrx_automatic) -> None:
    """Test with discovery."""
    rfxtrx = rfxtrx_automatic

    await rfxtrx.signal("0b1100100118cdea02010f70")
    state = hass.states.get("binary_sensor.ac_118cdea_2")
    assert state
    assert state.state == "on"

    await rfxtrx.signal("0b1100100118cdeb02010f70")
    state = hass.states.get("binary_sensor.ac_118cdeb_2")
    assert state
    assert state.state == "on"


async def test_off_delay_restore(hass: HomeAssistant, rfxtrx) -> None:
    """Make sure binary sensor restore as off, if off delay is active."""
    mock_restore_cache(
        hass,
        [
            State(
                "binary_sensor.ac_118cdea_2",
                "on",
                attributes={ATTR_EVENT: EVENT_AC_118CDEA_2_ON},
            )
        ],
    )

    entry_data = create_rfx_test_cfg(devices={EVENT_AC_118CDEA_2_ON: {"off_delay": 5}})
    mock_entry = MockConfigEntry(domain="rfxtrx", unique_id=DOMAIN, data=entry_data)

    mock_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()
    await hass.async_start()

    state = hass.states.get("binary_sensor.ac_118cdea_2")
    assert state
    assert state.state == "off"


async def test_off_delay(hass: HomeAssistant, rfxtrx, timestep) -> None:
    """Test with discovery."""
    entry_data = create_rfx_test_cfg(
        devices={"0b1100100118cdea02010f70": {"off_delay": 5}}
    )
    mock_entry = MockConfigEntry(domain="rfxtrx", unique_id=DOMAIN, data=entry_data)

    mock_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()
    await hass.async_start()

    state = hass.states.get("binary_sensor.ac_118cdea_2")
    assert state
    assert state.state == STATE_UNKNOWN

    await rfxtrx.signal("0b1100100118cdea02010f70")
    state = hass.states.get("binary_sensor.ac_118cdea_2")
    assert state
    assert state.state == "on"

    await timestep(4)
    state = hass.states.get("binary_sensor.ac_118cdea_2")
    assert state
    assert state.state == "on"

    await timestep(4)
    state = hass.states.get("binary_sensor.ac_118cdea_2")
    assert state
    assert state.state == "off"

    await rfxtrx.signal("0b1100100118cdea02010f70")
    state = hass.states.get("binary_sensor.ac_118cdea_2")
    assert state
    assert state.state == "on"

    await timestep(3)
    await rfxtrx.signal("0b1100100118cdea02010f70")

    await timestep(4)
    state = hass.states.get("binary_sensor.ac_118cdea_2")
    assert state
    assert state.state == "on"

    await timestep(4)
    state = hass.states.get("binary_sensor.ac_118cdea_2")
    assert state
    assert state.state == "off"


async def test_panic(hass: HomeAssistant, rfxtrx_automatic) -> None:
    """Test panic entities."""
    rfxtrx = rfxtrx_automatic

    entity_id = "binary_sensor.kd101_smoke_detector_a10900_32"

    await rfxtrx.signal(EVENT_SMOKE_DETECTOR_PANIC)
    assert hass.states.get(entity_id).state == "on"
    assert hass.states.get(entity_id).attributes.get("device_class") == "smoke"

    await rfxtrx.signal(EVENT_SMOKE_DETECTOR_NO_PANIC)
    assert hass.states.get(entity_id).state == "off"


async def test_motion(hass: HomeAssistant, rfxtrx_automatic) -> None:
    """Test motion entities."""
    rfxtrx = rfxtrx_automatic

    entity_id = "binary_sensor.x10_security_motion_detector_a10900_32"

    await rfxtrx.signal(EVENT_MOTION_DETECTOR_MOTION)
    assert hass.states.get(entity_id).state == "on"
    assert hass.states.get(entity_id).attributes.get("device_class") == "motion"

    await rfxtrx.signal(EVENT_MOTION_DETECTOR_NO_MOTION)
    assert hass.states.get(entity_id).state == "off"


async def test_light(hass: HomeAssistant, rfxtrx_automatic) -> None:
    """Test light entities."""
    rfxtrx = rfxtrx_automatic

    entity_id = "binary_sensor.x10_security_motion_detector_a10900_32"

    await rfxtrx.signal(EVENT_LIGHT_DETECTOR_LIGHT)
    assert hass.states.get(entity_id).state == "on"

    await rfxtrx.signal(EVENT_LIGHT_DETECTOR_DARK)
    assert hass.states.get(entity_id).state == "off"


async def test_pt2262_duplicate_id(hass: HomeAssistant, rfxtrx) -> None:
    """Test with 1 sensor."""
    entry_data = create_rfx_test_cfg(
        devices={
            "0913000022670e013970": {
                "data_bits": 4,
                "command_on": 0xE,
                "command_off": 0x7,
            },
            "09130000226707013970": {
                "data_bits": 4,
                "command_on": 0xE,
                "command_off": 0x7,
            },
        }
    )
    mock_entry = MockConfigEntry(domain="rfxtrx", unique_id=DOMAIN, data=entry_data)

    mock_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()
    await hass.async_start()

    state = hass.states.get("binary_sensor.pt2262_22670e")
    assert state
    assert state.state == STATE_UNKNOWN
    assert state.attributes.get("friendly_name") == "PT2262 22670e"
