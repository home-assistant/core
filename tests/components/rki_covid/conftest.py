"""global fixtures for tests."""
from unittest.mock import AsyncMock, MagicMock, Mock

import pytest
from rki_covid_parser.model.country import Country

from homeassistant.components.rki_covid.const import DOMAIN
from homeassistant.core import HomeAssistant

from . import MOCK_DISTRICTS

from tests.common import MockConfigEntry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        title="SK Amberg", domain=DOMAIN, data=MOCK_DISTRICTS, unique_id=""
    )


@pytest.fixture(autouse=True)
def mock_covid_parser(hass: HomeAssistant):
    """Mock for rki-covid-parser."""
    mock_district = Mock(
        id="1",
        name="SK Amberg",
        county="Deutschland",
        state="Foo",
        population=1,
        cases=2,
        deaths=3,
        casesPerWeek=4,
        deathsPerWeek=5,
        recovered=6,
        newCases=7,
        newDeaths=8,
        newRecovered=9,
        lastUpdate="a",
    )

    mock_district.weekIncidence = Mock()

    mock = MagicMock(spec=())
    mock.load_data = AsyncMock()
    mock._accumulate_country = AsyncMock()
    mock.districts = {1: mock_district}
    mock.states = {}
    mock.country = Country()

    return mock
