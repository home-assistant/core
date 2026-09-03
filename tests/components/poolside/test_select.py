"""Tests for Poolside heating/cooling mode select entities."""

from aiopoolside import PoolsideControl
from aiopoolside.const import ControlType
import pytest

from homeassistant.components.select import (
    ATTR_OPTION,
    ATTR_OPTIONS,
    DOMAIN as SELECT_DOMAIN,
    SERVICE_SELECT_OPTION,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant

from .conftest import (
    TEST_BODY_OF_WATER_UUID,
    TEST_SITE,
    FakePoolsideClient,
    make_control,
)

from tests.common import MockConfigEntry

HEATER_UUID = "heater-1"
HEATING_ENTITY_ID = "select.pool_heater_heating_mode"
COOLING_ENTITY_ID = "select.pool_heater_cooling_mode"


@pytest.fixture
def controls() -> list[PoolsideControl]:
    """A single TEMPERATURE control."""
    return [make_control(HEATER_UUID, "Heater", ControlType.TEMPERATURE)]


@pytest.mark.usefixtures("setup_integration")
async def test_selects_appear_as_capabilities_are_reported(
    hass: HomeAssistant,
    fake_client: FakePoolsideClient,
) -> None:
    """Each select is added once its supported list is pushed, under either key.

    Pushed lists arrive JSON-encoded inside the string value, keyed by either
    the group's BodyOfWaterUUID or the heater control's own UUID.
    """
    assert hass.states.get(HEATING_ENTITY_ID) is None
    assert hass.states.get(COOLING_ENTITY_ID) is None

    fake_client.set_status(
        TEST_BODY_OF_WATER_UUID,
        "HeatingModesSupported",
        '[\n  "SMART",\n  "SOLAR",\n  "FUEL"\n]',
    )
    await hass.async_block_till_done()

    state = hass.states.get(HEATING_ENTITY_ID)
    assert state is not None
    assert state.attributes[ATTR_OPTIONS] == ["smart", "solar", "fuel"]
    assert hass.states.get(COOLING_ENTITY_ID) is None

    fake_client.set_status(HEATER_UUID, "CoolingModesSupported", '["SMART", "CHILLER"]')
    await hass.async_block_till_done()

    state = hass.states.get(COOLING_ENTITY_ID)
    assert state is not None
    assert state.attributes[ATTR_OPTIONS] == ["smart", "chiller"]


async def test_selects_created_from_layout_capabilities(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_poolside_client: FakePoolsideClient,
) -> None:
    """Supported-mode lists in the control layout create selects at setup.

    A later status push then overrides the layout's list.
    """
    mock_poolside_client.async_get_control_layout.return_value = (
        TEST_SITE,
        [
            make_control(
                HEATER_UUID,
                "Heater",
                ControlType.TEMPERATURE,
                HeatingModesSupported=["SMART", "SOLAR", "HEATPUMP", "FUEL"],
                CoolingModesSupported=["SMART", "HEATPUMP", "CHILLER"],
            )
        ],
    )
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(HEATING_ENTITY_ID)
    assert state is not None
    assert state.attributes[ATTR_OPTIONS] == ["smart", "solar", "heatpump", "fuel"]
    state = hass.states.get(COOLING_ENTITY_ID)
    assert state is not None
    assert state.attributes[ATTR_OPTIONS] == ["smart", "heatpump", "chiller"]

    mock_poolside_client.set_status(HEATER_UUID, "HeatingModesSupported", ["SMART"])
    await hass.async_block_till_done()

    state = hass.states.get(HEATING_ENTITY_ID)
    assert state is not None
    assert state.attributes[ATTR_OPTIONS] == ["smart"]


async def test_select_added_from_initial_snapshot(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_poolside_client: FakePoolsideClient,
) -> None:
    """Capabilities already in the connect-time snapshot create selects immediately."""
    mock_poolside_client.set_status(
        TEST_BODY_OF_WATER_UUID, "HeatingModesSupported", '["SMART", "HEATPUMP"]'
    )
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(HEATING_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_UNKNOWN
    assert state.attributes[ATTR_OPTIONS] == ["smart", "heatpump"]


@pytest.mark.usefixtures("setup_integration")
async def test_options_skip_unrecognized_modes(
    hass: HomeAssistant,
    fake_client: FakePoolsideClient,
) -> None:
    """Modes this integration doesn't know are skipped rather than rendered raw."""
    fake_client.set_status(
        TEST_BODY_OF_WATER_UUID, "HeatingModesSupported", '["SMART", "MAGMA"]'
    )
    await hass.async_block_till_done()

    state = hass.states.get(HEATING_ENTITY_ID)
    assert state is not None
    assert state.attributes[ATTR_OPTIONS] == ["smart"]


@pytest.mark.parametrize(
    ("entity_id", "supported_field", "supported", "desired_field", "desired"),
    [
        pytest.param(
            HEATING_ENTITY_ID,
            "HeatingModesSupported",
            '["SMART", "SOLAR"]',
            "HeatingMode",
            "SOLAR",
            id="heating",
        ),
        pytest.param(
            COOLING_ENTITY_ID,
            "CoolingModesSupported",
            '["SMART", "CHILLER"]',
            "CoolingMode",
            "CHILLER",
            id="cooling",
        ),
    ],
)
@pytest.mark.usefixtures("setup_integration")
async def test_state_reflects_selected_mode(
    hass: HomeAssistant,
    fake_client: FakePoolsideClient,
    entity_id: str,
    supported_field: str,
    supported: str,
    desired_field: str,
    desired: str,
) -> None:
    """The state is the desired mode tracked under the control's own UUID."""
    fake_client.set_status(TEST_BODY_OF_WATER_UUID, supported_field, supported)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_UNKNOWN

    fake_client.set_status(HEATER_UUID, desired_field, desired)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == desired.lower()


@pytest.mark.parametrize(
    ("entity_id", "supported_field", "supported", "option", "expected_write"),
    [
        pytest.param(
            HEATING_ENTITY_ID,
            "HeatingModesSupported",
            '["SMART", "SOLAR", "HEATPUMP", "FUEL"]',
            "solar",
            {"HeatingMode": "SOLAR"},
            id="heating",
        ),
        pytest.param(
            COOLING_ENTITY_ID,
            "CoolingModesSupported",
            '["SMART", "HEATPUMP", "CHILLER"]',
            "chiller",
            {"CoolingMode": "CHILLER"},
            id="cooling",
        ),
    ],
)
@pytest.mark.usefixtures("setup_integration")
async def test_select_option_writes_desired_state(
    hass: HomeAssistant,
    fake_client: FakePoolsideClient,
    entity_id: str,
    supported_field: str,
    supported: str,
    option: str,
    expected_write: dict[str, str],
) -> None:
    """Selecting an option writes the matching wire value via setDesiredState2."""
    fake_client.set_status(TEST_BODY_OF_WATER_UUID, supported_field, supported)
    await hass.async_block_till_done()

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: entity_id, ATTR_OPTION: option},
        blocking=True,
    )
    fake_client.async_set_desired_state.assert_awaited_with(
        HEATER_UUID, **expected_write
    )


@pytest.mark.usefixtures("setup_integration")
async def test_unavailable_when_capabilities_withdrawn(
    hass: HomeAssistant,
    fake_client: FakePoolsideClient,
) -> None:
    """A select whose supported list empties out becomes unavailable."""
    fake_client.set_status(
        TEST_BODY_OF_WATER_UUID, "HeatingModesSupported", '["SMART"]'
    )
    await hass.async_block_till_done()
    state = hass.states.get(HEATING_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_UNKNOWN

    fake_client.set_status(TEST_BODY_OF_WATER_UUID, "HeatingModesSupported", "[]")
    await hass.async_block_till_done()

    state = hass.states.get(HEATING_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE
