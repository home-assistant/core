"""Test the Forecast.Solar config flow."""

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.forecast_solar import async_setup_entry
from homeassistant.components.forecast_solar.const import (
    CONF_AZIMUTH,
    CONF_AZIMUTH_SENSOR,
    CONF_DAMPING_EVENING,
    CONF_DAMPING_MORNING,
    CONF_DECLINATION,
    CONF_DECLINATION_SENSOR,
    CONF_INVERTER_SIZE,
    CONF_MODULES_POWER,
    DOMAIN,
    SUBENTRY_TYPE_PLANE,
)
from homeassistant.config_entries import (
    SOURCE_RECONFIGURE,
    SOURCE_USER,
    ConfigFlowResult,
    ConfigSubentryData,
)
from homeassistant.const import CONF_API_KEY, CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

DEGREES = {"unit_of_measurement": "°"}


def _suggested(result: ConfigFlowResult, key: str) -> Any:
    """Return the suggested value a re-shown form offers for a field."""
    return next(
        schema_key.description["suggested_value"]
        for schema_key in result["data_schema"].schema
        if schema_key == key
    )


async def test_user_flow_fixed_location(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test the full user flow with fixed coordinates and fixed angles."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"location": "fixed", "declination_source": "fixed", "azimuth_source": "fixed"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "plane"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_LATITUDE: 52.42,
            CONF_LONGITUDE: 4.42,
            CONF_AZIMUTH: 142,
            CONF_DECLINATION: 42,
            CONF_MODULES_POWER: 4242,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY

    config_entry = result["result"]
    assert config_entry.title == ""
    assert config_entry.unique_id is None
    assert config_entry.data == {
        CONF_LATITUDE: 52.42,
        CONF_LONGITUDE: 4.42,
    }
    assert config_entry.options == {}

    # Verify a plane subentry was created
    plane_subentries = config_entry.get_subentries_of_type(SUBENTRY_TYPE_PLANE)
    assert len(plane_subentries) == 1
    subentry = plane_subentries[0]
    assert subentry.subentry_type == SUBENTRY_TYPE_PLANE
    assert subentry.data == {
        CONF_DECLINATION: 42,
        CONF_AZIMUTH: 142,
        CONF_MODULES_POWER: 4242,
    }
    assert subentry.title == "42° / 142° / 4242W"

    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.usefixtures("mock_setup_entry")
async def test_user_flow_home_location(hass: HomeAssistant) -> None:
    """Test following the Home Assistant location stores no coordinates."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"location": "home", "declination_source": "fixed", "azimuth_source": "fixed"},
    )

    # The coordinates are not asked for at all, so they cannot be silently dropped.
    schema_keys = {str(key) for key in result["data_schema"].schema}
    assert CONF_LATITUDE not in schema_keys
    assert CONF_LONGITUDE not in schema_keys

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_AZIMUTH: 142,
            CONF_DECLINATION: 42,
            CONF_MODULES_POWER: 4242,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].data == {}


@pytest.mark.parametrize(
    ("sources", "plane_data", "title"),
    [
        pytest.param(
            {"declination_source": "fixed", "azimuth_source": "fixed"},
            {CONF_DECLINATION: 42, CONF_AZIMUTH: 142, CONF_MODULES_POWER: 4242},
            "42° / 142° / 4242W",
            id="fixed_angles",
        ),
        pytest.param(
            {"declination_source": "sensor", "azimuth_source": "fixed"},
            {
                CONF_DECLINATION_SENSOR: "sensor.roof_declination",
                CONF_AZIMUTH: 142,
                CONF_MODULES_POWER: 4242,
            },
            "roof declination (sensor) / 142° / 4242W",
            id="declination_sensor",
        ),
        pytest.param(
            {"declination_source": "fixed", "azimuth_source": "sensor"},
            {
                CONF_DECLINATION: 42,
                CONF_AZIMUTH_SENSOR: "sensor.roof_azimuth",
                CONF_MODULES_POWER: 4242,
            },
            "42° / roof azimuth (sensor) / 4242W",
            id="azimuth_sensor",
        ),
        pytest.param(
            {"declination_source": "sensor", "azimuth_source": "sensor"},
            {
                CONF_DECLINATION_SENSOR: "sensor.roof_declination",
                CONF_AZIMUTH_SENSOR: "sensor.roof_azimuth",
                CONF_MODULES_POWER: 4242,
            },
            "roof declination (sensor) / roof azimuth (sensor) / 4242W",
            id="both_sensors",
        ),
    ],
)
@pytest.mark.usefixtures("mock_setup_entry")
async def test_user_flow_plane_fields_follow_sources(
    hass: HomeAssistant,
    sources: dict[str, str],
    plane_data: dict[str, Any],
    title: str,
) -> None:
    """Test the plane step asks for, and stores, only what each angle's source needs."""
    hass.states.async_set("sensor.roof_declination", "30", DEGREES)
    hass.states.async_set("sensor.roof_azimuth", "190", DEGREES)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"location": "home"} | sources
    )

    assert {str(key) for key in result["data_schema"].schema} == set(plane_data)

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], plane_data
    )

    subentry = result["result"].get_subentries_of_type(SUBENTRY_TYPE_PLANE)[0]
    assert subentry.data == plane_data
    assert subentry.title == title


@pytest.mark.usefixtures("mock_setup_entry")
async def test_reconfigure_flow_switch_to_fixed_location(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test switching an existing entry from home tracking to fixed coordinates."""
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(mock_config_entry, data={})
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    result = await mock_config_entry.start_reconfigure_flow(hass)

    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "reconfigure"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "reconfigure_fixed_location"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure_fixed_location"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_LATITUDE: 12.34, CONF_LONGITUDE: 56.78},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_config_entry.data == {
        CONF_LATITUDE: 12.34,
        CONF_LONGITUDE: 56.78,
    }


@pytest.mark.usefixtures("mock_setup_entry")
async def test_reconfigure_flow_suggests_stored_coordinates(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the reconfigure form offers the entry's current coordinates."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    result = await mock_config_entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "reconfigure_fixed_location"}
    )

    assert _suggested(result, CONF_LATITUDE) == 52.42
    assert _suggested(result, CONF_LONGITUDE) == 4.42


@pytest.mark.usefixtures("mock_forecast_solar")
async def test_reconfigure_flow_reloads_entry_once(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the entry's update listener performs the reload, without doubling it."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.forecast_solar.async_setup_entry",
        wraps=async_setup_entry,
    ) as mock_async_setup_entry:
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
        assert len(mock_async_setup_entry.mock_calls) == 1

        result = await mock_config_entry.start_reconfigure_flow(hass)
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"next_step_id": "reconfigure_home_location"}
        )
        await hass.async_block_till_done()

        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "reconfigure_successful"
        assert mock_config_entry.data == {}
        # The update listener reloads; the flow must not schedule a second reload.
        assert len(mock_async_setup_entry.mock_calls) == 2


@pytest.mark.usefixtures("mock_setup_entry")
async def test_options_flow_invalid_api(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test options config flow when API key is invalid."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_API_KEY: "solarPOWER!",
            CONF_DAMPING_MORNING: 0.25,
            CONF_DAMPING_EVENING: 0.25,
            CONF_INVERTER_SIZE: 2000,
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_API_KEY: "invalid_api_key"}

    # Ensure we can recover from this error
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_API_KEY: "SolarForecast150",
            CONF_DAMPING_MORNING: 0.25,
            CONF_DAMPING_EVENING: 0.25,
            CONF_INVERTER_SIZE: 2000,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_API_KEY: "SolarForecast150",
        CONF_DAMPING_MORNING: 0.25,
        CONF_DAMPING_EVENING: 0.25,
        CONF_INVERTER_SIZE: 2000,
    }


@pytest.mark.usefixtures("mock_setup_entry")
async def test_options_flow(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test config flow options."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    # With the API key
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_API_KEY: "SolarForecast150",
            CONF_DAMPING_MORNING: 0.25,
            CONF_DAMPING_EVENING: 0.25,
            CONF_INVERTER_SIZE: 2000,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_API_KEY: "SolarForecast150",
        CONF_DAMPING_MORNING: 0.25,
        CONF_DAMPING_EVENING: 0.25,
        CONF_INVERTER_SIZE: 2000,
    }


@pytest.mark.usefixtures("mock_setup_entry")
async def test_options_flow_without_key(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test config flow options."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    # Without the API key
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_DAMPING_MORNING: 0.25,
            CONF_DAMPING_EVENING: 0.25,
            CONF_INVERTER_SIZE: 2000,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_API_KEY: None,
        CONF_DAMPING_MORNING: 0.25,
        CONF_DAMPING_EVENING: 0.25,
        CONF_INVERTER_SIZE: 2000,
    }


@pytest.mark.usefixtures("mock_setup_entry")
async def test_options_flow_required_api_key(
    hass: HomeAssistant,
) -> None:
    """Test config flow options requires API key when multiple planes are present."""
    mock_config_entry = MockConfigEntry(
        title="Green House",
        unique_id="unique",
        version=3,
        domain=DOMAIN,
        data={
            CONF_LATITUDE: 52.42,
            CONF_LONGITUDE: 4.42,
        },
        options={
            CONF_DAMPING_MORNING: 0.5,
            CONF_DAMPING_EVENING: 0.5,
            CONF_INVERTER_SIZE: 2000,
            CONF_API_KEY: "abcdef1234567890",
        },
        subentries_data=[
            ConfigSubentryData(
                data={
                    CONF_DECLINATION: 30,
                    CONF_AZIMUTH: 190,
                    CONF_MODULES_POWER: 5100,
                },
                subentry_id="mock_plane_id",
                subentry_type=SUBENTRY_TYPE_PLANE,
                title="30° / 190° / 5100W",
                unique_id=None,
            ),
            ConfigSubentryData(
                data={
                    CONF_DECLINATION: 45,
                    CONF_AZIMUTH: 270,
                    CONF_MODULES_POWER: 3000,
                },
                subentry_id="second_plane_id",
                subentry_type=SUBENTRY_TYPE_PLANE,
                title="45° / 270° / 3000W",
                unique_id=None,
            ),
        ],
    )

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    # Try to save with an empty API key
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_API_KEY: "",
            CONF_DAMPING_MORNING: 0.25,
            CONF_DAMPING_EVENING: 0.25,
            CONF_INVERTER_SIZE: 2000,
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_API_KEY: "api_key_required"}

    # Now provide an API key
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_API_KEY: "SolarForecast150",
            CONF_DAMPING_MORNING: 0.25,
            CONF_DAMPING_EVENING: 0.25,
            CONF_INVERTER_SIZE: 2000,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_API_KEY: "SolarForecast150",
        CONF_DAMPING_MORNING: 0.25,
        CONF_DAMPING_EVENING: 0.25,
        CONF_INVERTER_SIZE: 2000,
    }


@pytest.mark.usefixtures("mock_setup_entry")
async def test_subentry_flow_add_plane(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test adding a plane via subentry flow."""
    hass.states.async_set("sensor.roof_azimuth", "270", DEGREES)
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry.entry_id, SUBENTRY_TYPE_PLANE),
        context={"source": SOURCE_USER},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {"declination_source": "fixed", "azimuth_source": "sensor"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "plane"

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        user_input={
            CONF_DECLINATION: 45,
            CONF_AZIMUTH_SENSOR: "sensor.roof_azimuth",
            CONF_MODULES_POWER: 3000,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "45° / roof azimuth (sensor) / 3000W"
    assert result["data"] == {
        CONF_DECLINATION: 45,
        CONF_AZIMUTH_SENSOR: "sensor.roof_azimuth",
        CONF_MODULES_POWER: 3000,
    }

    assert len(mock_config_entry.get_subentries_of_type(SUBENTRY_TYPE_PLANE)) == 2


@pytest.mark.usefixtures("mock_forecast_solar")
async def test_subentry_flow_reconfigure_plane(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test reconfiguring a plane from a fixed azimuth to an azimuth sensor."""
    hass.states.async_set("sensor.roof_azimuth", "200", DEGREES)
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    subentry_id = mock_config_entry.get_subentries_of_type(SUBENTRY_TYPE_PLANE)[
        0
    ].subentry_id

    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry.entry_id, SUBENTRY_TYPE_PLANE),
        context={"source": SOURCE_RECONFIGURE, "subentry_id": subentry_id},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"
    assert _suggested(result, "declination_source") == "fixed"
    assert _suggested(result, "azimuth_source") == "fixed"

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {"declination_source": "fixed", "azimuth_source": "sensor"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure_plane"
    assert _suggested(result, CONF_DECLINATION) == 30
    assert _suggested(result, CONF_MODULES_POWER) == 5100

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        user_input={
            CONF_DECLINATION: 50,
            CONF_AZIMUTH_SENSOR: "sensor.roof_azimuth",
            CONF_MODULES_POWER: 6000,
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"

    plane_subentries = mock_config_entry.get_subentries_of_type(SUBENTRY_TYPE_PLANE)
    assert len(plane_subentries) == 1
    subentry = plane_subentries[0]
    assert subentry.data == {
        CONF_DECLINATION: 50,
        CONF_AZIMUTH_SENSOR: "sensor.roof_azimuth",
        CONF_MODULES_POWER: 6000,
    }
    assert subentry.title == "50° / roof azimuth (sensor) / 6000W"


@pytest.mark.parametrize("api_key_present", [False])
@pytest.mark.usefixtures("mock_setup_entry")
async def test_subentry_flow_no_api_key(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that adding more than one plane without API key is not allowed."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry.entry_id, SUBENTRY_TYPE_PLANE),
        context={"source": SOURCE_USER},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "api_key_required"


@pytest.mark.usefixtures("mock_setup_entry")
async def test_subentry_flow_max_planes(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that adding more than 4 planes is not allowed."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # mock_config_entry already has 1 plane subentry; add 3 more to reach the limit
    for i in range(3):
        result = await hass.config_entries.subentries.async_init(
            (mock_config_entry.entry_id, SUBENTRY_TYPE_PLANE),
            context={"source": SOURCE_USER},
        )
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"],
            {"declination_source": "fixed", "azimuth_source": "fixed"},
        )
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"],
            user_input={
                CONF_DECLINATION: 10 * (i + 1),
                CONF_AZIMUTH: 90 * (i + 1),
                CONF_MODULES_POWER: 1000 * (i + 1),
            },
        )
        assert result["type"] is FlowResultType.CREATE_ENTRY

    assert len(mock_config_entry.get_subentries_of_type(SUBENTRY_TYPE_PLANE)) == 4

    # Attempt to add a 5th plane should be aborted
    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry.entry_id, SUBENTRY_TYPE_PLANE),
        context={"source": SOURCE_USER},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "max_planes"


async def test_subentry_flow_reconfigure_plane_not_loaded(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test reconfiguring a plane via subentry flow when entry is not loaded."""
    mock_config_entry.add_to_hass(hass)
    # Entry is not loaded, so it has no update listeners

    subentry_id = mock_config_entry.get_subentries_of_type(SUBENTRY_TYPE_PLANE)[
        0
    ].subentry_id

    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry.entry_id, SUBENTRY_TYPE_PLANE),
        context={"source": SOURCE_RECONFIGURE, "subentry_id": subentry_id},
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {"declination_source": "fixed", "azimuth_source": "fixed"},
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        user_input={
            CONF_DECLINATION: 50,
            CONF_AZIMUTH: 200,
            CONF_MODULES_POWER: 6000,
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"

    plane_subentries = mock_config_entry.get_subentries_of_type(SUBENTRY_TYPE_PLANE)
    assert len(plane_subentries) == 1
    subentry = plane_subentries[0]
    assert subentry.data == {
        CONF_DECLINATION: 50,
        CONF_AZIMUTH: 200,
        CONF_MODULES_POWER: 6000,
    }
    assert subentry.title == "50° / 200° / 6000W"


@pytest.mark.parametrize(
    ("state", "attributes"),
    [
        pytest.param("north", {"unit_of_measurement": "°"}, id="not_a_number"),
        pytest.param("400", {"unit_of_measurement": "°"}, id="out_of_range"),
    ],
)
@pytest.mark.usefixtures("mock_setup_entry")
async def test_subentry_flow_rejects_unusable_sensor(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    state: str,
    attributes: dict[str, Any],
) -> None:
    """Test a sensor that can't be read as an angle is refused by the form."""
    hass.states.async_set("sensor.roof_azimuth", state, attributes)
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry.entry_id, SUBENTRY_TYPE_PLANE),
        context={"source": SOURCE_USER},
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {"declination_source": "fixed", "azimuth_source": "sensor"},
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        user_input={
            CONF_DECLINATION: 30,
            CONF_AZIMUTH_SENSOR: "sensor.roof_azimuth",
            CONF_MODULES_POWER: 5100,
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_AZIMUTH_SENSOR: "sensor_unusable"}
    # The submitted values are offered again, so only the sensor needs fixing.
    assert _suggested(result, CONF_MODULES_POWER) == 5100

    hass.states.async_set("sensor.roof_azimuth", "200", {"unit_of_measurement": "°"})
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        user_input={
            CONF_DECLINATION: 30,
            CONF_AZIMUTH_SENSOR: "sensor.roof_azimuth",
            CONF_MODULES_POWER: 5100,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.usefixtures("mock_setup_entry")
async def test_subentry_flow_reconfigure_keeps_sensor_without_state(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test a configured sensor survives reconfigure while it has no state."""
    mock_config_entry.add_to_hass(hass)
    subentry_id = mock_config_entry.get_subentries_of_type(SUBENTRY_TYPE_PLANE)[
        0
    ].subentry_id
    hass.config_entries.async_update_subentry(
        mock_config_entry,
        mock_config_entry.subentries[subentry_id],
        data={
            CONF_DECLINATION: 30,
            CONF_AZIMUTH_SENSOR: "sensor.roof_azimuth",
            CONF_MODULES_POWER: 5100,
        },
    )

    # The sensor is never added to the state machine.
    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry.entry_id, SUBENTRY_TYPE_PLANE),
        context={"source": SOURCE_RECONFIGURE, "subentry_id": subentry_id},
    )

    assert _suggested(result, "azimuth_source") == "sensor"

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {"declination_source": "fixed", "azimuth_source": "sensor"},
    )

    assert _suggested(result, CONF_AZIMUTH_SENSOR) == "sensor.roof_azimuth"

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        user_input={
            CONF_DECLINATION: 30,
            CONF_AZIMUTH_SENSOR: "sensor.roof_azimuth",
            CONF_MODULES_POWER: 5100,
        },
    )

    assert result["type"] is FlowResultType.ABORT
    subentry = mock_config_entry.get_subentries_of_type(SUBENTRY_TYPE_PLANE)[0]
    assert subentry.data[CONF_AZIMUTH_SENSOR] == "sensor.roof_azimuth"
    # Without a state there is no friendly name, so the title uses the entity ID.
    assert subentry.title == "30° / sensor.roof_azimuth (sensor) / 5100W"
