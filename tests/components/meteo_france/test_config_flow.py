"""Tests for the Meteo-France config flow."""

from unittest.mock import patch

from meteofrance_api.model import Place
import pytest

from homeassistant.components.meteo_france.const import CONF_CITY, DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

CITY_1_POSTAL = "74220"
CITY_1_NAME = "La Clusaz"
CITY_1_LAT = 45.90417
CITY_1_LON = 6.42306
CITY_1_COUNTRY = "FR"
CITY_1_ADMIN = "Rhône-Alpes"
CITY_1_ADMIN2 = "74"
CITY_1 = Place(
    {
        "name": CITY_1_NAME,
        "lat": CITY_1_LAT,
        "lon": CITY_1_LON,
        "country": CITY_1_COUNTRY,
        "admin": CITY_1_ADMIN,
        "admin2": CITY_1_ADMIN2,
    }
)

CITY_2_NAME = "Auch"
CITY_2_LAT = 43.64528
CITY_2_LON = 0.58861
CITY_2_COUNTRY = "FR"
CITY_2_ADMIN = "Midi-Pyrénées"
CITY_2_ADMIN2 = "32"
CITY_2 = Place(
    {
        "name": CITY_2_NAME,
        "lat": CITY_2_LAT,
        "lon": CITY_2_LON,
        "country": CITY_2_COUNTRY,
        "admin": CITY_2_ADMIN,
        "admin2": CITY_2_ADMIN2,
    }
)

CITY_3_NAME = "Auchel"
CITY_3_LAT = 50.50833
CITY_3_LON = 2.47361
CITY_3_COUNTRY = "FR"
CITY_3_ADMIN = "Nord-Pas-de-Calais"
CITY_3_ADMIN2 = "62"
CITY_3 = Place(
    {
        "name": CITY_3_NAME,
        "lat": CITY_3_LAT,
        "lon": CITY_3_LON,
        "country": CITY_3_COUNTRY,
        "admin": CITY_3_ADMIN,
        "admin2": CITY_3_ADMIN2,
    }
)


@pytest.fixture(name="client_single")
def mock_controller_client_single():
    """Mock a successful client."""
    with patch(
        "homeassistant.components.meteo_france.config_flow.MeteoFranceClient",
        update=False,
    ) as service_mock:
        service_mock.return_value.search_places.return_value = [CITY_1]
        yield service_mock


@pytest.fixture(autouse=True)
def mock_setup():
    """Prevent setup."""
    with patch(
        "homeassistant.components.meteo_france.async_setup_entry",
        return_value=True,
    ):
        yield


@pytest.fixture(name="client_multiple")
def mock_controller_client_multiple():
    """Mock a successful client."""
    with patch(
        "homeassistant.components.meteo_france.config_flow.MeteoFranceClient",
        update=False,
    ) as service_mock:
        service_mock.return_value.search_places.return_value = [CITY_2, CITY_3]
        yield service_mock


@pytest.fixture(name="client_empty")
def mock_controller_client_empty():
    """Mock a successful client."""
    with patch(
        "homeassistant.components.meteo_france.config_flow.MeteoFranceClient",
        update=False,
    ) as service_mock:
        service_mock.return_value.search_places.return_value = []
        yield service_mock


async def test_user(hass: HomeAssistant, client_single) -> None:
    """Test user config."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    # test with all provided with search returning only 1 place
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={CONF_CITY: CITY_1_POSTAL},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == f"{CITY_1_LAT}, {CITY_1_LON}"
    assert result["title"] == f"{CITY_1}"
    assert result["data"][CONF_LATITUDE] == str(CITY_1_LAT)
    assert result["data"][CONF_LONGITUDE] == str(CITY_1_LON)


async def test_user_list(hass: HomeAssistant, client_multiple) -> None:
    """Test user config."""

    # test with all provided with search returning more than 1 place
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={CONF_CITY: CITY_2_NAME},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "cities"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_CITY: f"{CITY_3};{CITY_3_LAT};{CITY_3_LON}"},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == f"{CITY_3_LAT}, {CITY_3_LON}"
    assert result["title"] == f"{CITY_3}"
    assert result["data"][CONF_LATITUDE] == str(CITY_3_LAT)
    assert result["data"][CONF_LONGITUDE] == str(CITY_3_LON)


async def test_search_failed(hass: HomeAssistant, client_empty) -> None:
    """Test error displayed if no result in search."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={CONF_CITY: CITY_1_POSTAL},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_CITY: "empty"}


async def test_abort_if_already_setup(hass: HomeAssistant, client_single) -> None:
    """Test we abort if already setup."""
    MockConfigEntry(
        domain=DOMAIN,
        data={CONF_LATITUDE: CITY_1_LAT, CONF_LONGITUDE: CITY_1_LON},
        unique_id=f"{CITY_1_LAT}, {CITY_1_LON}",
    ).add_to_hass(hass)

    # Should fail, same CITY same postal code (flow)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={CONF_CITY: CITY_1_POSTAL},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
