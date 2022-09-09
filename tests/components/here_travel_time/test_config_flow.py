"""Test the HERE Travel Time config flow."""
from unittest.mock import patch

from herepy import HEREError
from herepy.routing_api import InvalidCredentialsError
import pytest

from homeassistant import config_entries, data_entry_flow
from homeassistant.components.here_travel_time.const import (
    CONF_ARRIVAL,
    CONF_ARRIVAL_TIME,
    CONF_DEPARTURE,
    CONF_DEPARTURE_TIME,
    CONF_ROUTE_MODE,
    CONF_TRAFFIC_MODE,
    DOMAIN,
    ROUTE_MODE_FASTEST,
    TRAFFIC_MODE_ENABLED,
    TRAVEL_MODE_CAR,
    TRAVEL_MODE_PUBLIC_TIME_TABLE,
)
from homeassistant.components.here_travel_time.sensor import (
    CONF_DESTINATION_ENTITY_ID,
    CONF_DESTINATION_LATITUDE,
    CONF_DESTINATION_LONGITUDE,
    CONF_ORIGIN_ENTITY_ID,
    CONF_ORIGIN_LATITUDE,
    CONF_ORIGIN_LONGITUDE,
)
from homeassistant.const import (
    CONF_API_KEY,
    CONF_ENTITY_NAMESPACE,
    CONF_MODE,
    CONF_NAME,
    CONF_SCAN_INTERVAL,
    CONF_UNIT_SYSTEM,
    CONF_UNIT_SYSTEM_IMPERIAL,
    CONF_UNIT_SYSTEM_METRIC,
)
from homeassistant.core import HomeAssistant

from .const import (
    API_KEY,
    CAR_DESTINATION_LATITUDE,
    CAR_DESTINATION_LONGITUDE,
    CAR_ORIGIN_LATITUDE,
    CAR_ORIGIN_LONGITUDE,
)

from tests.common import MockConfigEntry


@pytest.fixture(autouse=True)
def bypass_setup_fixture():
    """Prevent setup."""
    with patch(
        "homeassistant.components.here_travel_time.async_setup_entry",
        return_value=True,
    ):
        yield


@pytest.fixture(name="user_step_result")
async def user_step_result_fixture(hass: HomeAssistant) -> data_entry_flow.FlowResult:
    """Provide the result of a completed user step."""
    init_result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    user_step_result = await hass.config_entries.flow.async_configure(
        init_result["flow_id"],
        {
            CONF_API_KEY: API_KEY,
            CONF_MODE: TRAVEL_MODE_CAR,
            CONF_NAME: "test",
        },
    )
    await hass.async_block_till_done()
    return user_step_result


@pytest.fixture(name="option_init_result")
async def option_init_result_fixture(hass: HomeAssistant) -> data_entry_flow.FlowResult:
    """Provide the result of a completed options init step."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="0123456789",
        data={
            CONF_ORIGIN_LATITUDE: float(CAR_ORIGIN_LATITUDE),
            CONF_ORIGIN_LONGITUDE: float(CAR_ORIGIN_LONGITUDE),
            CONF_DESTINATION_LATITUDE: float(CAR_DESTINATION_LATITUDE),
            CONF_DESTINATION_LONGITUDE: float(CAR_DESTINATION_LONGITUDE),
            CONF_API_KEY: API_KEY,
            CONF_MODE: TRAVEL_MODE_PUBLIC_TIME_TABLE,
            CONF_NAME: "test",
        },
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    flow = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        flow["flow_id"],
        user_input={
            CONF_TRAFFIC_MODE: TRAFFIC_MODE_ENABLED,
            CONF_ROUTE_MODE: ROUTE_MODE_FASTEST,
            CONF_UNIT_SYSTEM: CONF_UNIT_SYSTEM_METRIC,
        },
    )
    return result


@pytest.fixture(name="origin_step_result")
async def origin_step_result_fixture(
    hass: HomeAssistant, user_step_result: data_entry_flow.FlowResult
) -> data_entry_flow.FlowResult:
    """Provide the result of a completed origin by coordinates step."""
    origin_menu_result = await hass.config_entries.flow.async_configure(
        user_step_result["flow_id"], {"next_step_id": "origin_coordinates"}
    )

    location_selector_result = await hass.config_entries.flow.async_configure(
        origin_menu_result["flow_id"],
        {
            "origin": {
                "latitude": float(CAR_ORIGIN_LATITUDE),
                "longitude": float(CAR_ORIGIN_LONGITUDE),
                "radius": 3.0,
            }
        },
    )
    return location_selector_result


@pytest.mark.parametrize(
    "menu_options",
    (["origin_coordinates", "origin_entity"],),
)
@pytest.mark.usefixtures("valid_response")
async def test_step_user(hass: HomeAssistant, menu_options) -> None:
    """Test the user step."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["errors"] == {}

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_API_KEY: API_KEY,
            CONF_MODE: TRAVEL_MODE_CAR,
            CONF_NAME: "test",
        },
    )
    await hass.async_block_till_done()

    assert result2["type"] == data_entry_flow.FlowResultType.MENU
    assert result2["menu_options"] == menu_options


@pytest.mark.usefixtures("valid_response")
async def test_step_origin_coordinates(
    hass: HomeAssistant, user_step_result: data_entry_flow.FlowResult
) -> None:
    """Test the origin coordinates step."""
    menu_result = await hass.config_entries.flow.async_configure(
        user_step_result["flow_id"], {"next_step_id": "origin_coordinates"}
    )
    assert menu_result["type"] == data_entry_flow.FlowResultType.FORM

    location_selector_result = await hass.config_entries.flow.async_configure(
        menu_result["flow_id"],
        {
            "origin": {
                "latitude": float(CAR_ORIGIN_LATITUDE),
                "longitude": float(CAR_ORIGIN_LONGITUDE),
                "radius": 3.0,
            }
        },
    )
    assert location_selector_result["type"] == data_entry_flow.FlowResultType.MENU


@pytest.mark.usefixtures("valid_response")
async def test_step_origin_entity(
    hass: HomeAssistant, user_step_result: data_entry_flow.FlowResult
) -> None:
    """Test the origin coordinates step."""
    menu_result = await hass.config_entries.flow.async_configure(
        user_step_result["flow_id"], {"next_step_id": "origin_entity"}
    )
    assert menu_result["type"] == data_entry_flow.FlowResultType.FORM

    entity_selector_result = await hass.config_entries.flow.async_configure(
        menu_result["flow_id"],
        {"origin_entity_id": "zone.home"},
    )
    assert entity_selector_result["type"] == data_entry_flow.FlowResultType.MENU


@pytest.mark.usefixtures("valid_response")
async def test_step_destination_coordinates(
    hass: HomeAssistant, origin_step_result: data_entry_flow.FlowResult
) -> None:
    """Test the origin coordinates step."""
    menu_result = await hass.config_entries.flow.async_configure(
        origin_step_result["flow_id"], {"next_step_id": "destination_coordinates"}
    )
    assert menu_result["type"] == data_entry_flow.FlowResultType.FORM

    location_selector_result = await hass.config_entries.flow.async_configure(
        menu_result["flow_id"],
        {
            "destination": {
                "latitude": float(CAR_DESTINATION_LATITUDE),
                "longitude": float(CAR_DESTINATION_LONGITUDE),
                "radius": 3.0,
            }
        },
    )
    assert (
        location_selector_result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    )
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert entry.data == {
        CONF_NAME: "test",
        CONF_API_KEY: API_KEY,
        CONF_ORIGIN_LATITUDE: float(CAR_ORIGIN_LATITUDE),
        CONF_ORIGIN_LONGITUDE: float(CAR_ORIGIN_LONGITUDE),
        CONF_DESTINATION_LATITUDE: float(CAR_DESTINATION_LATITUDE),
        CONF_DESTINATION_LONGITUDE: float(CAR_DESTINATION_LONGITUDE),
        CONF_MODE: TRAVEL_MODE_CAR,
    }


@pytest.mark.usefixtures("valid_response")
async def test_step_destination_entity(
    hass: HomeAssistant, origin_step_result: data_entry_flow.FlowResult
) -> None:
    """Test the origin coordinates step."""
    menu_result = await hass.config_entries.flow.async_configure(
        origin_step_result["flow_id"], {"next_step_id": "destination_entity"}
    )
    assert menu_result["type"] == data_entry_flow.FlowResultType.FORM

    entity_selector_result = await hass.config_entries.flow.async_configure(
        menu_result["flow_id"],
        {"destination_entity_id": "zone.home"},
    )
    assert entity_selector_result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert entry.data == {
        CONF_NAME: "test",
        CONF_API_KEY: API_KEY,
        CONF_ORIGIN_LATITUDE: float(CAR_ORIGIN_LATITUDE),
        CONF_ORIGIN_LONGITUDE: float(CAR_ORIGIN_LONGITUDE),
        CONF_DESTINATION_ENTITY_ID: "zone.home",
        CONF_MODE: TRAVEL_MODE_CAR,
    }


async def test_form_invalid_auth(hass: HomeAssistant) -> None:
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "herepy.RoutingApi.public_transport_timetable",
        side_effect=InvalidCredentialsError,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_API_KEY: API_KEY,
                CONF_MODE: TRAVEL_MODE_CAR,
                CONF_NAME: "test",
            },
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "invalid_auth"}


async def test_form_unknown_error(hass: HomeAssistant) -> None:
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "herepy.RoutingApi.public_transport_timetable",
        side_effect=HEREError,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_API_KEY: API_KEY,
                CONF_MODE: TRAVEL_MODE_CAR,
                CONF_NAME: "test",
            },
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "unknown"}


@pytest.mark.usefixtures("valid_response")
async def test_options_flow(hass: HomeAssistant) -> None:
    """Test the options flow."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="0123456789",
        data={
            CONF_ORIGIN_LATITUDE: float(CAR_ORIGIN_LATITUDE),
            CONF_ORIGIN_LONGITUDE: float(CAR_ORIGIN_LONGITUDE),
            CONF_DESTINATION_LATITUDE: float(CAR_DESTINATION_LATITUDE),
            CONF_DESTINATION_LONGITUDE: float(CAR_DESTINATION_LONGITUDE),
            CONF_API_KEY: API_KEY,
            CONF_MODE: TRAVEL_MODE_CAR,
            CONF_NAME: "test",
        },
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)

    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(entry.entry_id)

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_TRAFFIC_MODE: TRAFFIC_MODE_ENABLED,
            CONF_ROUTE_MODE: ROUTE_MODE_FASTEST,
            CONF_UNIT_SYSTEM: CONF_UNIT_SYSTEM_IMPERIAL,
        },
    )

    assert result["type"] == data_entry_flow.FlowResultType.MENU


@pytest.mark.usefixtures("valid_response")
async def test_options_flow_arrival_time_step(
    hass: HomeAssistant, option_init_result: data_entry_flow.FlowResult
) -> None:
    """Test the options flow arrival time type."""
    menu_result = await hass.config_entries.options.async_configure(
        option_init_result["flow_id"], {"next_step_id": "arrival_time"}
    )
    assert menu_result["type"] == data_entry_flow.FlowResultType.FORM
    time_selector_result = await hass.config_entries.options.async_configure(
        option_init_result["flow_id"],
        user_input={
            "arrival_time": "08:00:00",
        },
    )

    assert time_selector_result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert entry.options == {
        CONF_UNIT_SYSTEM: CONF_UNIT_SYSTEM_METRIC,
        CONF_ROUTE_MODE: ROUTE_MODE_FASTEST,
        CONF_TRAFFIC_MODE: TRAFFIC_MODE_ENABLED,
        CONF_ARRIVAL_TIME: "08:00:00",
    }


@pytest.mark.usefixtures("valid_response")
async def test_options_flow_departure_time_step(
    hass: HomeAssistant, option_init_result: data_entry_flow.FlowResult
) -> None:
    """Test the options flow departure time type."""
    menu_result = await hass.config_entries.options.async_configure(
        option_init_result["flow_id"], {"next_step_id": "departure_time"}
    )
    assert menu_result["type"] == data_entry_flow.FlowResultType.FORM
    time_selector_result = await hass.config_entries.options.async_configure(
        option_init_result["flow_id"],
        user_input={
            "departure_time": "08:00:00",
        },
    )

    assert time_selector_result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert entry.options == {
        CONF_UNIT_SYSTEM: CONF_UNIT_SYSTEM_METRIC,
        CONF_ROUTE_MODE: ROUTE_MODE_FASTEST,
        CONF_TRAFFIC_MODE: TRAFFIC_MODE_ENABLED,
        CONF_DEPARTURE_TIME: "08:00:00",
    }


@pytest.mark.usefixtures("valid_response")
async def test_options_flow_no_time_step(
    hass: HomeAssistant, option_init_result: data_entry_flow.FlowResult
) -> None:
    """Test the options flow arrival time type."""
    menu_result = await hass.config_entries.options.async_configure(
        option_init_result["flow_id"], {"next_step_id": "no_time"}
    )

    assert menu_result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert entry.options == {
        CONF_UNIT_SYSTEM: CONF_UNIT_SYSTEM_METRIC,
        CONF_ROUTE_MODE: ROUTE_MODE_FASTEST,
        CONF_TRAFFIC_MODE: TRAFFIC_MODE_ENABLED,
    }


@pytest.mark.usefixtures("valid_response")
async def test_import_flow_entity_id(hass: HomeAssistant) -> None:
    """Test import_flow with entity ids."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_IMPORT},
        data={
            CONF_API_KEY: CONF_API_KEY,
            CONF_ORIGIN_ENTITY_ID: "sensor.origin",
            CONF_DESTINATION_ENTITY_ID: "sensor.destination",
            CONF_NAME: "test_name",
            CONF_MODE: TRAVEL_MODE_CAR,
            CONF_DEPARTURE: "08:00:00",
            CONF_ROUTE_MODE: ROUTE_MODE_FASTEST,
            CONF_UNIT_SYSTEM: CONF_UNIT_SYSTEM_IMPERIAL,
            CONF_TRAFFIC_MODE: TRAFFIC_MODE_ENABLED,
            CONF_ENTITY_NAMESPACE: "namespace",
            CONF_SCAN_INTERVAL: 2678400,
        },
    )
    await hass.async_block_till_done()

    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["title"] == "namespace test_name"

    entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert entry.data == {
        CONF_NAME: "namespace test_name",
        CONF_API_KEY: CONF_API_KEY,
        CONF_ORIGIN_ENTITY_ID: "sensor.origin",
        CONF_DESTINATION_ENTITY_ID: "sensor.destination",
        CONF_MODE: TRAVEL_MODE_CAR,
    }
    assert entry.options == {
        CONF_UNIT_SYSTEM: CONF_UNIT_SYSTEM_IMPERIAL,
        CONF_ROUTE_MODE: ROUTE_MODE_FASTEST,
        CONF_TRAFFIC_MODE: TRAFFIC_MODE_ENABLED,
        CONF_DEPARTURE_TIME: "08:00:00",
        CONF_ARRIVAL_TIME: None,
    }


@pytest.mark.usefixtures("valid_response")
async def test_import_flow_coordinates(hass: HomeAssistant) -> None:
    """Test import_flow with coordinates."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_IMPORT},
        data={
            CONF_API_KEY: CONF_API_KEY,
            CONF_ORIGIN_LATITUDE: CAR_ORIGIN_LATITUDE,
            CONF_ORIGIN_LONGITUDE: CAR_ORIGIN_LONGITUDE,
            CONF_DESTINATION_LATITUDE: CAR_DESTINATION_LATITUDE,
            CONF_DESTINATION_LONGITUDE: CAR_DESTINATION_LONGITUDE,
            CONF_NAME: "test_name",
            CONF_MODE: TRAVEL_MODE_CAR,
            CONF_ARRIVAL: "08:00:00",
            CONF_ROUTE_MODE: ROUTE_MODE_FASTEST,
            CONF_UNIT_SYSTEM: CONF_UNIT_SYSTEM_METRIC,
            CONF_TRAFFIC_MODE: TRAFFIC_MODE_ENABLED,
        },
    )
    await hass.async_block_till_done()

    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["title"] == "test_name"

    entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert entry.data == {
        CONF_NAME: "test_name",
        CONF_API_KEY: CONF_API_KEY,
        CONF_ORIGIN_LATITUDE: CAR_ORIGIN_LATITUDE,
        CONF_ORIGIN_LONGITUDE: CAR_ORIGIN_LONGITUDE,
        CONF_DESTINATION_LATITUDE: CAR_DESTINATION_LATITUDE,
        CONF_DESTINATION_LONGITUDE: CAR_DESTINATION_LONGITUDE,
        CONF_MODE: TRAVEL_MODE_CAR,
    }
    assert entry.options == {
        CONF_UNIT_SYSTEM: CONF_UNIT_SYSTEM_METRIC,
        CONF_ROUTE_MODE: ROUTE_MODE_FASTEST,
        CONF_TRAFFIC_MODE: TRAFFIC_MODE_ENABLED,
        CONF_DEPARTURE_TIME: None,
        CONF_ARRIVAL_TIME: "08:00:00",
        CONF_UNIT_SYSTEM: CONF_UNIT_SYSTEM_METRIC,
    }


@pytest.mark.usefixtures("valid_response")
async def test_dupe_import(hass: HomeAssistant) -> None:
    """Test duplicate import."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_IMPORT},
        data={
            CONF_API_KEY: CONF_API_KEY,
            CONF_ORIGIN_LATITUDE: CAR_ORIGIN_LATITUDE,
            CONF_ORIGIN_LONGITUDE: CAR_ORIGIN_LONGITUDE,
            CONF_DESTINATION_LATITUDE: CAR_DESTINATION_LATITUDE,
            CONF_DESTINATION_LONGITUDE: CAR_DESTINATION_LONGITUDE,
            CONF_NAME: "test_name",
            CONF_MODE: TRAVEL_MODE_CAR,
            CONF_ARRIVAL: "08:00:00",
            CONF_ROUTE_MODE: ROUTE_MODE_FASTEST,
            CONF_UNIT_SYSTEM: CONF_UNIT_SYSTEM_METRIC,
            CONF_TRAFFIC_MODE: TRAFFIC_MODE_ENABLED,
        },
    )
    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_IMPORT},
        data={
            CONF_API_KEY: CONF_API_KEY,
            CONF_ORIGIN_LATITUDE: CAR_ORIGIN_LATITUDE,
            CONF_ORIGIN_LONGITUDE: CAR_ORIGIN_LONGITUDE,
            CONF_DESTINATION_LATITUDE: CAR_DESTINATION_LATITUDE,
            CONF_DESTINATION_LONGITUDE: CAR_DESTINATION_LONGITUDE,
            CONF_NAME: "test_name2",
            CONF_MODE: TRAVEL_MODE_CAR,
            CONF_ARRIVAL: "08:00:00",
            CONF_ROUTE_MODE: ROUTE_MODE_FASTEST,
            CONF_UNIT_SYSTEM: CONF_UNIT_SYSTEM_METRIC,
            CONF_TRAFFIC_MODE: TRAFFIC_MODE_ENABLED,
        },
    )
    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_IMPORT},
        data={
            CONF_API_KEY: CONF_API_KEY,
            CONF_ORIGIN_LATITUDE: CAR_ORIGIN_LATITUDE,
            CONF_ORIGIN_LONGITUDE: CAR_ORIGIN_LONGITUDE,
            CONF_DESTINATION_LATITUDE: CAR_DESTINATION_LATITUDE,
            CONF_DESTINATION_LONGITUDE: CAR_DESTINATION_LONGITUDE,
            CONF_NAME: "test_name",
            CONF_MODE: TRAVEL_MODE_CAR,
            CONF_ARRIVAL: "08:00:01",
            CONF_ROUTE_MODE: ROUTE_MODE_FASTEST,
            CONF_UNIT_SYSTEM: CONF_UNIT_SYSTEM_METRIC,
            CONF_TRAFFIC_MODE: TRAFFIC_MODE_ENABLED,
        },
    )
    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_IMPORT},
        data={
            CONF_API_KEY: CONF_API_KEY,
            CONF_ORIGIN_LATITUDE: CAR_ORIGIN_LATITUDE,
            CONF_ORIGIN_LONGITUDE: CAR_ORIGIN_LONGITUDE,
            CONF_DESTINATION_LATITUDE: "40.0",
            CONF_DESTINATION_LONGITUDE: CAR_DESTINATION_LONGITUDE,
            CONF_NAME: "test_name",
            CONF_MODE: TRAVEL_MODE_CAR,
            CONF_ARRIVAL: "08:00:01",
            CONF_ROUTE_MODE: ROUTE_MODE_FASTEST,
            CONF_UNIT_SYSTEM: CONF_UNIT_SYSTEM_METRIC,
            CONF_TRAFFIC_MODE: TRAFFIC_MODE_ENABLED,
        },
    )
    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_IMPORT},
        data={
            CONF_API_KEY: CONF_API_KEY,
            CONF_ORIGIN_LATITUDE: CAR_ORIGIN_LATITUDE,
            CONF_ORIGIN_LONGITUDE: CAR_ORIGIN_LONGITUDE,
            CONF_DESTINATION_LATITUDE: CAR_DESTINATION_LATITUDE,
            CONF_DESTINATION_LONGITUDE: CAR_DESTINATION_LONGITUDE,
            CONF_NAME: "test_name",
            CONF_MODE: TRAVEL_MODE_CAR,
            CONF_ARRIVAL: "08:00:00",
            CONF_ROUTE_MODE: ROUTE_MODE_FASTEST,
            CONF_UNIT_SYSTEM: CONF_UNIT_SYSTEM_METRIC,
            CONF_TRAFFIC_MODE: TRAFFIC_MODE_ENABLED,
        },
    )
    assert result["type"] == data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "already_configured"
