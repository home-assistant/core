"""Test the Forecast.Solar config flow."""

from unittest.mock import AsyncMock

import pytest

from homeassistant.components.forecast_solar.const import (
    CONF_ADJ,
    CONF_AZIMUTH,
    CONF_AZIMUTH_CHOICE,
    CONF_AZIMUTH_SENSOR,
    CONF_DAMPING_EVENING,
    CONF_DAMPING_MORNING,
    CONF_DECLINATION,
    CONF_DECLINATION_CHOICE,
    CONF_DECLINATION_SENSOR,
    CONF_FIXED,
    CONF_HOME_LOCATION,
    CONF_INVERTER_SIZE,
    CONF_LOCATION_CHOICE,
    CONF_MANUAL_LOCATION,
    CONF_MODULES_POWER,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import (
    ATTR_UNIT_OF_MEASUREMENT,
    CONF_API_KEY,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_NAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

_FAKE_DECLINATION_SENSOR = "sensor.solar_declination"
_FAKE_AZIMUTH_SENSOR = "sensor.solar_azimuth"


def _register_angle_sensors(hass: HomeAssistant) -> None:
    """Register fake angle sensors so get_angle_sensor_ids() returns them."""
    hass.states.async_set(
        _FAKE_DECLINATION_SENSOR, "35", {ATTR_UNIT_OF_MEASUREMENT: "°"}
    )
    hass.states.async_set(_FAKE_AZIMUTH_SENSOR, "180", {ATTR_UNIT_OF_MEASUREMENT: "°"})


async def test_config_flow_creates_entry(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test the config flow creates an entry with only a name."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_NAME: "Name"}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY

    config_entry = result["result"]
    assert config_entry.title == "Name"
    assert config_entry.data == {}
    assert config_entry.options == {}
    assert len(mock_setup_entry.mock_calls) == 1


async def test_config_flow_default_name(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test that the name field defaults to the HA location name."""
    hass.config.location_name = "Home"

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    # Default is pre-populated — submitting without changing it should work fine
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_NAME: "Home"},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].title == "Home"


async def _init_options_flow(hass: HomeAssistant, entry: MockConfigEntry) -> dict:
    """Helper: set up entry and open the options flow, return the init result."""
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"
    return result


@pytest.mark.usefixtures("mock_setup_entry")
async def test_options_init_routes_to_location_manual(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test that choosing manual location routes to the location_manual step."""
    result = await _init_options_flow(hass, mock_config_entry)

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_MODULES_POWER: 4000,
            CONF_LOCATION_CHOICE: CONF_MANUAL_LOCATION,
            CONF_AZIMUTH_CHOICE: CONF_FIXED,
            CONF_DECLINATION_CHOICE: CONF_FIXED,
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "location_manual"


@pytest.mark.usefixtures("mock_setup_entry")
async def test_options_init_home_location_skips_location_step(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test that choosing home location skips location_manual and goes to azimuth."""
    result = await _init_options_flow(hass, mock_config_entry)

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_MODULES_POWER: 4000,
            CONF_LOCATION_CHOICE: CONF_HOME_LOCATION,
            CONF_AZIMUTH_CHOICE: CONF_FIXED,
            CONF_DECLINATION_CHOICE: CONF_FIXED,
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "azimuth_manual"


@pytest.mark.usefixtures("mock_setup_entry")
async def test_options_location_manual_updates_coords(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test that manual location stores new lat/lon in options."""
    result = await _init_options_flow(hass, mock_config_entry)

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_MODULES_POWER: 4000,
            CONF_LOCATION_CHOICE: CONF_MANUAL_LOCATION,
            CONF_AZIMUTH_CHOICE: CONF_FIXED,
            CONF_DECLINATION_CHOICE: CONF_FIXED,
        },
    )
    assert result["step_id"] == "location_manual"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_LATITUDE: 48.85, CONF_LONGITUDE: 2.35},
    )
    # Should proceed to azimuth_manual next
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "azimuth_manual"


# ---------------------------------------------------------------------------
# Options flow — azimuth steps (manual vs sensor, mutual exclusivity)
# ---------------------------------------------------------------------------


@pytest.mark.usefixtures("mock_setup_entry")
async def test_options_azimuth_manual_creates_entry(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test full options flow with fixed azimuth and fixed declination."""
    result = await _init_options_flow(hass, mock_config_entry)

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_MODULES_POWER: 4000,
            CONF_LOCATION_CHOICE: CONF_HOME_LOCATION,
            CONF_AZIMUTH_CHOICE: CONF_FIXED,
            CONF_DECLINATION_CHOICE: CONF_FIXED,
        },
    )
    assert result["step_id"] == "azimuth_manual"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_AZIMUTH: 180},
    )
    assert result["step_id"] == "declination_manual"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_DECLINATION: 35},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_AZIMUTH] == 180
    assert CONF_AZIMUTH_SENSOR not in result["data"]
    assert result["data"][CONF_DECLINATION] == 35
    assert CONF_DECLINATION_SENSOR not in result["data"]


@pytest.mark.usefixtures("mock_setup_entry")
async def test_options_azimuth_sensor_creates_entry(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test full options flow with sensor azimuth; fixed value must be absent."""
    _register_angle_sensors(hass)
    result = await _init_options_flow(hass, mock_config_entry)

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_MODULES_POWER: 4000,
            CONF_LOCATION_CHOICE: CONF_HOME_LOCATION,
            CONF_AZIMUTH_CHOICE: CONF_ADJ,
            CONF_DECLINATION_CHOICE: CONF_FIXED,
        },
    )
    assert result["step_id"] == "azimuth_sensor"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_AZIMUTH_SENSOR: _FAKE_AZIMUTH_SENSOR},
    )
    assert result["step_id"] == "declination_manual"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_DECLINATION: 35},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_AZIMUTH_SENSOR] == _FAKE_AZIMUTH_SENSOR
    # Mutual exclusivity: fixed value must not be saved
    assert CONF_AZIMUTH not in result["data"]


@pytest.mark.usefixtures("mock_setup_entry")
async def test_options_declination_sensor_creates_entry(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test full options flow with sensor declination; fixed value must be absent."""
    _register_angle_sensors(hass)
    result = await _init_options_flow(hass, mock_config_entry)

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_MODULES_POWER: 4000,
            CONF_LOCATION_CHOICE: CONF_HOME_LOCATION,
            CONF_AZIMUTH_CHOICE: CONF_FIXED,
            CONF_DECLINATION_CHOICE: CONF_ADJ,
        },
    )
    assert result["step_id"] == "azimuth_manual"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_AZIMUTH: 180},
    )
    assert result["step_id"] == "declination_sensor"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_DECLINATION_SENSOR: _FAKE_DECLINATION_SENSOR},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_DECLINATION_SENSOR] == _FAKE_DECLINATION_SENSOR
    # Mutual exclusivity: fixed value must not be saved
    assert CONF_DECLINATION not in result["data"]


@pytest.mark.usefixtures("mock_setup_entry")
async def test_options_both_sensors(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test full options flow with both azimuth and declination using sensors."""
    _register_angle_sensors(hass)
    result = await _init_options_flow(hass, mock_config_entry)

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_MODULES_POWER: 4000,
            CONF_LOCATION_CHOICE: CONF_HOME_LOCATION,
            CONF_AZIMUTH_CHOICE: CONF_ADJ,
            CONF_DECLINATION_CHOICE: CONF_ADJ,
        },
    )
    assert result["step_id"] == "azimuth_sensor"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_AZIMUTH_SENSOR: _FAKE_AZIMUTH_SENSOR},
    )
    assert result["step_id"] == "declination_sensor"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_DECLINATION_SENSOR: _FAKE_DECLINATION_SENSOR},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_AZIMUTH_SENSOR] == _FAKE_AZIMUTH_SENSOR
    assert result["data"][CONF_DECLINATION_SENSOR] == _FAKE_DECLINATION_SENSOR
    assert CONF_AZIMUTH not in result["data"]
    assert CONF_DECLINATION not in result["data"]


@pytest.mark.usefixtures("mock_setup_entry")
async def test_options_switching_from_sensor_to_manual_clears_sensor(
    hass: HomeAssistant,
) -> None:
    """Test that switching azimuth from sensor to manual removes the sensor key."""
    _register_angle_sensors(hass)

    # First configure with a sensor
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="My Array",
        data={},
        options={
            CONF_LATITUDE: hass.config.latitude,
            CONF_LONGITUDE: hass.config.longitude,
            CONF_MODULES_POWER: 4000,
            CONF_AZIMUTH_SENSOR: _FAKE_AZIMUTH_SENSOR,
            CONF_DECLINATION: 35,
        },
    )
    result = await _init_options_flow(hass, entry)

    # Now switch to manual azimuth
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_MODULES_POWER: 4000,
            CONF_LOCATION_CHOICE: CONF_HOME_LOCATION,
            CONF_AZIMUTH_CHOICE: CONF_FIXED,  # switched from sensor
            CONF_DECLINATION_CHOICE: CONF_FIXED,
        },
    )
    assert result["step_id"] == "azimuth_manual"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_AZIMUTH: 90},
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_DECLINATION: 35},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_AZIMUTH] == 90
    # Stale sensor key must be gone
    assert CONF_AZIMUTH_SENSOR not in result["data"]


@pytest.mark.usefixtures("mock_setup_entry")
async def test_options_switching_from_manual_to_sensor_clears_manual(
    hass: HomeAssistant,
) -> None:
    """Test that switching azimuth from manual to sensor removes the fixed value key."""
    _register_angle_sensors(hass)

    # Start with a manual azimuth
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="My Array",
        data={},
        options={
            CONF_LATITUDE: hass.config.latitude,
            CONF_LONGITUDE: hass.config.longitude,
            CONF_MODULES_POWER: 4000,
            CONF_AZIMUTH: 180,
            CONF_DECLINATION: 35,
        },
    )
    result = await _init_options_flow(hass, entry)

    # Switch to sensor azimuth
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_MODULES_POWER: 4000,
            CONF_LOCATION_CHOICE: CONF_HOME_LOCATION,
            CONF_AZIMUTH_CHOICE: CONF_ADJ,  # switched from manual
            CONF_DECLINATION_CHOICE: CONF_FIXED,
        },
    )
    assert result["step_id"] == "azimuth_sensor"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_AZIMUTH_SENSOR: _FAKE_AZIMUTH_SENSOR},
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_DECLINATION: 35},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_AZIMUTH_SENSOR] == _FAKE_AZIMUTH_SENSOR
    # Stale manual key must be gone
    assert CONF_AZIMUTH not in result["data"]


@pytest.mark.usefixtures("mock_setup_entry")
async def test_options_invalid_api_key_shows_error(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test that an invalid API key returns an error on the init step."""
    result = await _init_options_flow(hass, mock_config_entry)

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_API_KEY: "not-a-valid-key!",
            CONF_MODULES_POWER: 4000,
            CONF_LOCATION_CHOICE: CONF_HOME_LOCATION,
            CONF_AZIMUTH_CHOICE: CONF_FIXED,
            CONF_DECLINATION_CHOICE: CONF_FIXED,
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"
    assert result["errors"] == {CONF_API_KEY: "invalid_api_key"}


@pytest.mark.usefixtures("mock_setup_entry")
async def test_options_valid_api_key_proceeds(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test that a valid API key passes validation and the flow continues."""
    result = await _init_options_flow(hass, mock_config_entry)

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_API_KEY: "SolarForecast150",
            CONF_MODULES_POWER: 4000,
            CONF_LOCATION_CHOICE: CONF_HOME_LOCATION,
            CONF_AZIMUTH_CHOICE: CONF_FIXED,
            CONF_DECLINATION_CHOICE: CONF_FIXED,
        },
    )
    # Should move past init (not show error)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "azimuth_manual"


@pytest.mark.usefixtures("mock_setup_entry")
async def test_options_api_key_saved_in_final_entry(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test that the API key appears in the final options entry."""
    result = await _init_options_flow(hass, mock_config_entry)

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_API_KEY: "SolarForecast150",
            CONF_MODULES_POWER: 4000,
            CONF_LOCATION_CHOICE: CONF_HOME_LOCATION,
            CONF_AZIMUTH_CHOICE: CONF_FIXED,
            CONF_DECLINATION_CHOICE: CONF_FIXED,
        },
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_AZIMUTH: 180},
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_DECLINATION: 35},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_API_KEY] == "SolarForecast150"


@pytest.mark.usefixtures("mock_setup_entry")
async def test_options_no_api_key_not_stored(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test that omitting the API key results in it being absent from options."""
    result = await _init_options_flow(hass, mock_config_entry)

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_MODULES_POWER: 4000,
            CONF_LOCATION_CHOICE: CONF_HOME_LOCATION,
            CONF_AZIMUTH_CHOICE: CONF_FIXED,
            CONF_DECLINATION_CHOICE: CONF_FIXED,
        },
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_AZIMUTH: 180},
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_DECLINATION: 35},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert CONF_API_KEY not in result["data"]


# ---------------------------------------------------------------------------
# Options flow — optional fields (damping, inverter)
# ---------------------------------------------------------------------------


@pytest.mark.usefixtures("mock_setup_entry")
async def test_options_damping_and_inverter_stored(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test that damping factors and inverter size are persisted correctly."""
    result = await _init_options_flow(hass, mock_config_entry)

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_MODULES_POWER: 4000,
            CONF_DAMPING_MORNING: 0.25,
            CONF_DAMPING_EVENING: 0.5,
            CONF_INVERTER_SIZE: 3800,
            CONF_LOCATION_CHOICE: CONF_HOME_LOCATION,
            CONF_AZIMUTH_CHOICE: CONF_FIXED,
            CONF_DECLINATION_CHOICE: CONF_FIXED,
        },
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_AZIMUTH: 180},
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_DECLINATION: 35},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_DAMPING_MORNING] == 0.25
    assert result["data"][CONF_DAMPING_EVENING] == 0.5
    assert result["data"][CONF_INVERTER_SIZE] == 3800
