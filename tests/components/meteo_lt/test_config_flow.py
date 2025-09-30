"""Test the Meteo.lt config flow."""

from unittest.mock import AsyncMock

from meteo_lt import Place

from homeassistant.components.meteo_lt.const import CONF_PLACE_CODE, DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

VILNIUS_PLACE = Place(
    code="vilnius",
    name="Vilnius",
    administrative_division="Vilniaus miesto savivaldybė",
    country="Lietuva",
    coordinates={"latitude": 54.68705, "longitude": 25.28291},
)

KAUNAS_PLACE = Place(
    code="kaunas",
    name="Kaunas",
    administrative_division="Kauno miesto savivaldybė",
    country="Lietuva",
    coordinates={"latitude": 54.89685, "longitude": 23.89234},
)


async def test_user_flow_success(
    hass: HomeAssistant, mock_meteo_lt_api: AsyncMock
) -> None:
    """Test user flow directly shows manual form."""
    mock_meteo_lt_api.fetch_places.return_value = None
    mock_meteo_lt_api.places = [VILNIUS_PLACE, KAUNAS_PLACE]

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "manual"
    assert result["errors"] == {}


async def test_manual_flow_success(
    hass: HomeAssistant, mock_meteo_lt_api: AsyncMock
) -> None:
    """Test successful manual flow."""
    mock_meteo_lt_api.fetch_places.return_value = None
    mock_meteo_lt_api.places = [VILNIUS_PLACE, KAUNAS_PLACE]

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
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

    mock_meteo_lt_api.fetch_places.return_value = None
    mock_meteo_lt_api.places = [VILNIUS_PLACE, KAUNAS_PLACE]

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_PLACE_CODE: "vilnius"}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
