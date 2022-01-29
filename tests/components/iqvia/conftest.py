"""Define test fixtures for IQVIA."""
import json
from unittest.mock import patch

import pytest

from homeassistant.components.iqvia.const import CONF_ZIP_CODE, DOMAIN
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry, load_fixture


@pytest.fixture(name="config_entry")
def config_entry_fixture(hass, config, unique_id):
    """Define a config entry fixture."""
    entry = MockConfigEntry(domain=DOMAIN, unique_id=unique_id, data=config)
    entry.add_to_hass(hass)
    return entry


@pytest.fixture(name="config")
def config_fixture(hass):
    """Define a config entry data fixture."""
    return {
        CONF_ZIP_CODE: "12345",
    }


@pytest.fixture(name="data_allergy_forecast", scope="session")
def data_allergy_forecast_fixture():
    """Define allergy forecast data."""
    return json.loads(load_fixture("allergy_forecast_data.json", "iqvia"))


@pytest.fixture(name="data_allergy_index", scope="session")
def data_allergy_index_fixture():
    """Define allergy index data."""
    return json.loads(load_fixture("allergy_index_data.json", "iqvia"))


@pytest.fixture(name="data_allergy_outlook", scope="session")
def data_allergy_outlook_fixture():
    """Define allergy outlook data."""
    return json.loads(load_fixture("allergy_outlook_data.json", "iqvia"))


@pytest.fixture(name="data_asthma_forecast", scope="session")
def data_asthma_forecast_fixture():
    """Define asthma forecast data."""
    return json.loads(load_fixture("asthma_forecast_data.json", "iqvia"))


@pytest.fixture(name="data_asthma_index", scope="session")
def data_asthma_index_fixture():
    """Define asthma index data."""
    return json.loads(load_fixture("asthma_index_data.json", "iqvia"))


@pytest.fixture(name="data_disease_forecast", scope="session")
def data_disease_forecast_fixture():
    """Define disease forecast data."""
    return json.loads(load_fixture("disease_forecast_data.json", "iqvia"))


@pytest.fixture(name="data_disease_index", scope="session")
def data_disease_index_fixture():
    """Define disease index data."""
    return json.loads(load_fixture("disease_index_data.json", "iqvia"))


@pytest.fixture(name="setup_iqvia")
async def setup_iqvia_fixture(
    hass,
    config,
    data_allergy_forecast,
    data_allergy_index,
    data_allergy_outlook,
    data_asthma_forecast,
    data_asthma_index,
    data_disease_forecast,
    data_disease_index,
):
    """Define a fixture to set up IQVIA."""
    with patch(
        "pyiqvia.allergens.Allergens.extended", return_value=data_allergy_forecast
    ), patch(
        "pyiqvia.allergens.Allergens.current", return_value=data_allergy_index
    ), patch(
        "pyiqvia.allergens.Allergens.outlook", return_value=data_allergy_outlook
    ), patch(
        "pyiqvia.asthma.Asthma.extended", return_value=data_asthma_forecast
    ), patch(
        "pyiqvia.asthma.Asthma.current", return_value=data_asthma_index
    ), patch(
        "pyiqvia.disease.Disease.extended", return_value=data_disease_forecast
    ), patch(
        "pyiqvia.disease.Disease.current", return_value=data_disease_index
    ), patch(
        "homeassistant.components.iqvia.PLATFORMS", []
    ):
        assert await async_setup_component(hass, DOMAIN, config)
        await hass.async_block_till_done()
        yield


@pytest.fixture(name="unique_id")
def unique_id_fixture(hass):
    """Define a config entry unique ID fixture."""
    return "12345"
