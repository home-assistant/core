"""Tests for the IRM KMI config flow."""

from unittest.mock import AsyncMock

from irm_kmi_api import IrmKmiApiError
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_load_json_object_fixture

from homeassistant.components.irm_kmi.const import CONF_LANGUAGE_OVERRIDE, DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import (
    CONF_LATITUDE,
    CONF_LOCATION,
    CONF_LONGITUDE,
    CONF_UNIQUE_ID,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import entity_registry as er


@pytest.mark.usefixtures("mock_setup_entry", "mock_config_flow_forecast")
async def test_full_user_flow(hass: HomeAssistant) -> None:
    """Test the full user configuration flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_LOCATION: {CONF_LATITUDE: 50.123, CONF_LONGITUDE: 4.456}},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Brussels"
    assert result["data"] == {
        CONF_LOCATION: {CONF_LATITUDE: 50.123, CONF_LONGITUDE: 4.456},
        CONF_UNIQUE_ID: "brussels be",
    }
    assert result["result"].unique_id == "brussels be"


@pytest.mark.usefixtures("mock_setup_entry")
async def test_config_flow_location_out_benelux(
    hass: HomeAssistant, mock_config_flow_forecast: AsyncMock
) -> None:
    """Test configuration flow with a location outside of Benelux."""
    mock_config_flow_forecast.side_effect = [
        await async_load_json_object_fixture(
            hass, "forecast_out_of_benelux.json", DOMAIN
        ),
        mock_config_flow_forecast.return_value,
    ]
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_LOCATION: {CONF_LATITUDE: 0.123, CONF_LONGITUDE: 0.456}},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {CONF_LOCATION: "out_of_benelux"}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_LOCATION: {CONF_LATITUDE: 50.123, CONF_LONGITUDE: 4.456}},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Brussels"


@pytest.mark.usefixtures("mock_setup_entry")
async def test_config_flow_with_api_error(
    hass: HomeAssistant, mock_config_flow_forecast: AsyncMock
) -> None:
    """Test the flow recovers from an API error."""
    mock_config_flow_forecast.side_effect = IrmKmiApiError
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_LOCATION: {CONF_LATITUDE: 50.123, CONF_LONGITUDE: 4.456}},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    mock_config_flow_forecast.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_LOCATION: {CONF_LATITUDE: 50.123, CONF_LONGITUDE: 4.456}},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.usefixtures("mock_setup_entry", "mock_config_flow_forecast")
async def test_flow_already_configured(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test the flow aborts when the location is already configured."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_LOCATION: {CONF_LATITUDE: 50.123, CONF_LONGITUDE: 4.456}},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_option_flow(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test when the user changes options with the option flow."""
    mock_config_entry.add_to_hass(hass)

    assert not mock_config_entry.options

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {CONF_LANGUAGE_OVERRIDE: "none"}


@pytest.mark.usefixtures("mock_setup_entry", "mock_config_flow_forecast")
async def test_reconfigure_flow(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test moving the location within the same municipality."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reconfigure_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"
    assert (
        result["data_schema"]({})[CONF_LOCATION]
        == mock_config_entry.data[CONF_LOCATION]
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_LOCATION: {CONF_LATITUDE: 50.85, CONF_LONGITUDE: 4.36}},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_config_entry.data[CONF_LOCATION] == {
        CONF_LATITUDE: 50.85,
        CONF_LONGITUDE: 4.36,
    }


@pytest.mark.usefixtures("mock_setup_entry")
@pytest.mark.parametrize(
    ("title", "expected_title"),
    [
        pytest.param("Brussels", "Ghent", id="default_title"),
        pytest.param("Home", "Home", id="renamed_title"),
    ],
)
async def test_reconfigure_flow_other_municipality(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_flow_forecast: AsyncMock,
    title: str,
    expected_title: str,
) -> None:
    """Test moving the location to another municipality keeps the entities."""
    mock_config_flow_forecast.return_value = {"cityName": "Ghent", "country": "BE"}
    entry = MockConfigEntry(
        title=title,
        domain=DOMAIN,
        data={
            CONF_LOCATION: {CONF_LATITUDE: 50.84, CONF_LONGITUDE: 4.35},
            CONF_UNIQUE_ID: "brussels be",
        },
        unique_id="brussels be",
    )
    entry.add_to_hass(hass)
    weather = entity_registry.async_get_or_create(
        "weather", DOMAIN, "brussels be", config_entry=entry
    )
    sensor = entity_registry.async_get_or_create(
        "sensor", DOMAIN, "brussels be-temperature", config_entry=entry
    )

    result = await entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_LOCATION: {CONF_LATITUDE: 51.05, CONF_LONGITUDE: 3.72}},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.unique_id == "ghent be"
    assert entry.title == expected_title
    assert entry.data == {
        CONF_LOCATION: {CONF_LATITUDE: 51.05, CONF_LONGITUDE: 3.72},
        CONF_UNIQUE_ID: "ghent be",
    }
    assert entity_registry.async_get(weather.entity_id).unique_id == "ghent be"
    assert (
        entity_registry.async_get(sensor.entity_id).unique_id == "ghent be-temperature"
    )


@pytest.mark.usefixtures("mock_setup_entry")
@pytest.mark.parametrize(
    ("side_effect", "errors"),
    [
        pytest.param(IrmKmiApiError, {"base": "cannot_connect"}, id="cannot_connect"),
        pytest.param(
            [{"cityName": "Outside the Benelux (Brussels)", "country": "BE"}],
            {CONF_LOCATION: "out_of_benelux"},
            id="out_of_benelux",
        ),
    ],
)
async def test_reconfigure_flow_errors(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    mock_config_flow_forecast: AsyncMock,
    side_effect: type[Exception] | list[dict[str, str]],
    errors: dict[str, str],
) -> None:
    """Test the reconfigure flow leaves the entry untouched on errors and recovers."""
    mock_config_entry.add_to_hass(hass)
    sensor = entity_registry.async_get_or_create(
        "sensor", DOMAIN, "brussels be-temperature", config_entry=mock_config_entry
    )
    data = dict(mock_config_entry.data)
    mock_config_flow_forecast.side_effect = side_effect

    result = await mock_config_entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_LOCATION: {CONF_LATITUDE: 51.05, CONF_LONGITUDE: 3.72}},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"
    assert result["errors"] == errors
    assert mock_config_entry.data == data
    assert mock_config_entry.title == "Brussels"
    assert mock_config_entry.unique_id == "brussels be"
    assert (
        entity_registry.async_get(sensor.entity_id).unique_id
        == "brussels be-temperature"
    )

    mock_config_flow_forecast.side_effect = None
    mock_config_flow_forecast.return_value = {"cityName": "Ghent", "country": "BE"}
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_LOCATION: {CONF_LATITUDE: 51.05, CONF_LONGITUDE: 3.72}},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_config_entry.unique_id == "ghent be"
    assert mock_config_entry.title == "Ghent"
    assert mock_config_entry.data == {
        CONF_LOCATION: {CONF_LATITUDE: 51.05, CONF_LONGITUDE: 3.72},
        CONF_UNIQUE_ID: "ghent be",
    }
    assert (
        entity_registry.async_get(sensor.entity_id).unique_id == "ghent be-temperature"
    )


@pytest.mark.usefixtures("mock_setup_entry")
async def test_reconfigure_flow_already_configured(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_config_flow_forecast: AsyncMock,
) -> None:
    """Test moving the location to a municipality that is already configured."""
    mock_config_flow_forecast.return_value = {"cityName": "Ghent", "country": "BE"}
    mock_config_entry.add_to_hass(hass)
    MockConfigEntry(domain=DOMAIN, unique_id="ghent be").add_to_hass(hass)

    result = await mock_config_entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_LOCATION: {CONF_LATITUDE: 51.05, CONF_LONGITUDE: 3.72}},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert mock_config_entry.unique_id == "brussels be"
    assert mock_config_entry.data[CONF_LOCATION] == {
        CONF_LATITUDE: 50.84,
        CONF_LONGITUDE: 4.35,
    }
