"""Tests for Poolside TEMPERATURE controls exposed as climate entities."""

from aiopoolside import PoolsideControl
from aiopoolside.const import ControlType
import pytest

from homeassistant.components.climate import (
    ATTR_CURRENT_TEMPERATURE,
    ATTR_TEMPERATURE,
    DOMAIN as CLIMATE_DOMAIN,
    SERVICE_SET_HVAC_MODE,
    SERVICE_SET_TEMPERATURE,
    HVACMode,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_OFF, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.util.unit_system import US_CUSTOMARY_SYSTEM

from .conftest import (
    TEST_BODY_OF_WATER_UUID,
    TEST_SITE,
    TEST_SITE_UUID,
    FakePoolsideClient,
    make_control,
)

from tests.common import MockConfigEntry

HEATER_UUID = "heater-1"
ENTITY_ID = "climate.pool_heater"


@pytest.fixture
def controls(hass: HomeAssistant) -> list[PoolsideControl]:
    """A single TEMPERATURE control.

    Uses imperial units so the entity's Fahrenheit native unit matches the
    test hass's unit system and service calls need no conversion.
    """
    hass.config.units = US_CUSTOMARY_SYSTEM
    return [
        make_control(
            HEATER_UUID,
            "Heater",
            ControlType.TEMPERATURE,
            MinSetPoint=40,
            MaxSetPoint=104,
        )
    ]


@pytest.mark.usefixtures("setup_integration")
async def test_state_reflects_status(
    hass: HomeAssistant,
    fake_client: FakePoolsideClient,
) -> None:
    """Status/SetPoint/ControlMode are optimistic; Temperature is confirmed by the body."""
    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == STATE_OFF

    # Optimistic desired-state fields are keyed by the control's own UUID.
    fake_client.set_status(HEATER_UUID, "Status", "ON")
    fake_client.set_status(HEATER_UUID, "SetPoint", 88)
    # Confirmed body telemetry is keyed by the group's BodyOfWaterUUID.
    fake_client.set_status(TEST_BODY_OF_WATER_UUID, "Temperature", 79)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == HVACMode.HEAT
    assert state.attributes[ATTR_TEMPERATURE] == 88
    assert state.attributes[ATTR_CURRENT_TEMPERATURE] == 79


@pytest.mark.usefixtures("setup_integration")
async def test_state_tolerates_stringly_typed_temperatures(
    hass: HomeAssistant,
    fake_client: FakePoolsideClient,
) -> None:
    """Temperature/SetPoint values may arrive as strings; they must still render."""
    fake_client.set_status(HEATER_UUID, "SetPoint", "88")
    fake_client.set_status(TEST_BODY_OF_WATER_UUID, "Temperature", "76")
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.attributes[ATTR_TEMPERATURE] == 88.0
    assert state.attributes[ATTR_CURRENT_TEMPERATURE] == 76.0


@pytest.mark.parametrize(
    "status_key",
    [
        pytest.param(TEST_BODY_OF_WATER_UUID, id="keyed-by-body-of-water"),
        pytest.param(HEATER_UUID, id="keyed-by-heater-control"),
    ],
)
@pytest.mark.usefixtures("setup_integration")
async def test_hvac_modes_built_from_reported_capabilities(
    hass: HomeAssistant,
    fake_client: FakePoolsideClient,
    status_key: str,
) -> None:
    """hvac_modes reflects the confirmed ControlModesSupported, not a fixed list.

    Pushes may be keyed by the group's BodyOfWaterUUID or by the heater
    control's own UUID, and carry the list JSON-encoded inside the string
    value; both keys must work.
    """
    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.attributes["hvac_modes"] == [HVACMode.OFF, HVACMode.HEAT]

    fake_client.set_status(
        status_key, "ControlModesSupported", '[\n  "HEAT",\n  "COOL",\n  "AUTO"\n]'
    )
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert set(state.attributes["hvac_modes"]) == {
        HVACMode.OFF,
        HVACMode.HEAT,
        HVACMode.COOL,
        HVACMode.HEAT_COOL,
    }


async def test_hvac_modes_from_layout_capabilities(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_poolside_client: FakePoolsideClient,
) -> None:
    """ControlModesSupported in the control layout drives hvac_modes at setup."""
    mock_poolside_client.async_get_control_layout.return_value = (
        TEST_SITE,
        [
            make_control(
                HEATER_UUID,
                "Heater",
                ControlType.TEMPERATURE,
                ControlModesSupported=["HEAT", "COOL", "AUTO"],
            )
        ],
    )
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert set(state.attributes["hvac_modes"]) == {
        HVACMode.OFF,
        HVACMode.HEAT,
        HVACMode.COOL,
        HVACMode.HEAT_COOL,
    }


@pytest.mark.usefixtures("setup_integration")
async def test_set_hvac_mode_heat(
    hass: HomeAssistant,
    fake_client: FakePoolsideClient,
) -> None:
    """Setting HVAC mode to heat writes Status and the matching ControlMode."""
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: ENTITY_ID, "hvac_mode": HVACMode.HEAT},
        blocking=True,
    )
    fake_client.async_set_desired_state.assert_awaited_with(
        HEATER_UUID, Status="ON", ControlMode="HEAT"
    )


@pytest.mark.usefixtures("setup_integration")
async def test_set_hvac_mode_off(
    hass: HomeAssistant,
    fake_client: FakePoolsideClient,
) -> None:
    """Setting HVAC mode to off writes only Status=OFF."""
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: ENTITY_ID, "hvac_mode": HVACMode.OFF},
        blocking=True,
    )
    fake_client.async_set_desired_state.assert_awaited_with(HEATER_UUID, Status="OFF")


@pytest.mark.usefixtures("setup_integration")
async def test_set_temperature_writes_integer_setpoint(
    hass: HomeAssistant,
    fake_client: FakePoolsideClient,
) -> None:
    """Setting the target temperature writes an integer-string SetPoint."""
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_TEMPERATURE: 90.4},
        blocking=True,
    )
    fake_client.async_set_desired_state.assert_awaited_with(HEATER_UUID, SetPoint="90")


@pytest.mark.usefixtures("setup_integration")
async def test_installer_mode_makes_control_unavailable(
    hass: HomeAssistant,
    fake_client: FakePoolsideClient,
) -> None:
    """INSTALLER mode grays out every control until the site returns to NORMAL."""
    fake_client.set_status(TEST_SITE_UUID, "Mode", "INSTALLER")
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE

    fake_client.set_status(TEST_SITE_UUID, "Mode", "NORMAL")
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == STATE_OFF


@pytest.mark.parametrize("mode", ["FAULT", "FACTORY"])
@pytest.mark.usefixtures("setup_integration")
async def test_writes_rejected_outside_normal_mode(
    hass: HomeAssistant,
    fake_client: FakePoolsideClient,
    mode: str,
) -> None:
    """Desired-state writes are refused in any mode other than NORMAL.

    INSTALLER isn't parameterized here: it makes the entity unavailable, so
    the service layer already skips it before the write guard is reached.
    """
    fake_client.set_status(TEST_SITE_UUID, "Mode", mode)
    await hass.async_block_till_done()

    with pytest.raises(HomeAssistantError, match=f"in {mode} mode"):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_TEMPERATURE,
            {ATTR_ENTITY_ID: ENTITY_ID, ATTR_TEMPERATURE: 90},
            blocking=True,
        )
    fake_client.async_set_desired_state.assert_not_awaited()


@pytest.mark.usefixtures("setup_integration")
async def test_writes_allowed_in_normal_mode(
    hass: HomeAssistant,
    fake_client: FakePoolsideClient,
) -> None:
    """An explicitly reported NORMAL mode leaves writes working."""
    fake_client.set_status(TEST_SITE_UUID, "Mode", "NORMAL")
    await hass.async_block_till_done()

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_TEMPERATURE: 90},
        blocking=True,
    )
    fake_client.async_set_desired_state.assert_awaited_with(HEATER_UUID, SetPoint="90")


@pytest.mark.usefixtures("setup_integration")
async def test_bare_disabled_status_keeps_control_operable(
    hass: HomeAssistant,
    fake_client: FakePoolsideClient,
) -> None:
    """Status=DISABLED alone is only a suggestion; the control stays operable.

    It means activating this control will turn something else off (e.g. the
    spa is using the shared pump), not that it's locked out.
    """
    fake_client.set_status(HEATER_UUID, "Status", "DISABLED")
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == STATE_OFF

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: ENTITY_ID, "hvac_mode": HVACMode.HEAT},
        blocking=True,
    )
    fake_client.async_set_desired_state.assert_awaited_with(
        HEATER_UUID, Status="ON", ControlMode="HEAT"
    )


@pytest.mark.parametrize(
    "reason",
    [
        pytest.param("WINTERIZED", id="winterized"),
        pytest.param("FREEZE_PROTECT", id="freeze-protect"),
        pytest.param("cover-uuid-1", id="pool-cover"),
    ],
)
@pytest.mark.usefixtures("setup_integration")
async def test_disabled_reasons_make_control_unavailable(
    hass: HomeAssistant,
    fake_client: FakePoolsideClient,
    reason: str,
) -> None:
    """Any DisabledReasons entry takes the control out of service until cleared."""
    fake_client.set_status(HEATER_UUID, "DisabledReasons", f'["{reason}"]')
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE

    fake_client.set_status(HEATER_UUID, "DisabledReasons", "[]")
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == STATE_OFF
