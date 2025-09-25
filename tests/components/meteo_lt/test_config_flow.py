"""Test the Meteo.lt config flow."""

from unittest.mock import AsyncMock

from meteo_lt import Place

from homeassistant.components.meteo_lt.const import CONF_PLACE_CODE, DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

VILNIUS_LAT = 54.68705
VILNIUS_LON = 25.28291

VILNIUS_PLACE = Place(
    code="vilnius",
    name="Vilnius",
    administrative_division="Vilniaus miesto savivaldybė",
    country="Lietuva",
    coordinates={"latitude": VILNIUS_LAT, "longitude": VILNIUS_LON},
)


async def test_user_flow(hass: HomeAssistant) -> None:
    """Test user flow shows menu."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "user"
    assert result["menu_options"] == ["coordinates", "manual"]


async def test_coordinates_flow(
    hass: HomeAssistant, mock_meteo_lt_api: AsyncMock
) -> None:
    """Test coordinates flow success."""
    mock_meteo_lt_api.get_nearest_place.return_value = VILNIUS_PLACE

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={"next_step_id": "coordinates"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "coordinates"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_LATITUDE: VILNIUS_LAT, CONF_LONGITUDE: VILNIUS_LON},
    )

    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "location_from_coordinates"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={"next_step_id": "use_location"}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Vilnius"
    assert result["data"] == {CONF_PLACE_CODE: "vilnius"}


async def test_manual_flow(hass: HomeAssistant, mock_meteo_lt_api: AsyncMock) -> None:
    """Test manual flow success."""
    mock_meteo_lt_api.fetch_places.return_value = None
    mock_meteo_lt_api.places = [VILNIUS_PLACE]

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={"next_step_id": "manual"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "manual"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_PLACE_CODE: "vilnius"}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Vilnius"
    assert result["data"] == {CONF_PLACE_CODE: "vilnius"}


async def test_duplicate_entry(
    hass: HomeAssistant, mock_meteo_lt_api: AsyncMock
) -> None:
    """Test duplicate entry prevention."""
    existing_entry = MockConfigEntry(
        domain=DOMAIN,
        title="Vilnius",
        data={CONF_PLACE_CODE: "vilnius"},
        unique_id="vilnius",
    )
    existing_entry.add_to_hass(hass)

    mock_meteo_lt_api.get_nearest_place.return_value = VILNIUS_PLACE

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={"next_step_id": "coordinates"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_LATITUDE: VILNIUS_LAT, CONF_LONGITUDE: VILNIUS_LON},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={"next_step_id": "use_location"}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
