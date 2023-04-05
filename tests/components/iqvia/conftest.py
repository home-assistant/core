"""Define test fixtures for IQVIA."""
import json
from unittest.mock import AsyncMock, Mock, patch

import pytest

from homeassistant.components.iqvia.const import CONF_ZIP_CODE, DOMAIN

from tests.common import MockConfigEntry, load_fixture

TEST_ZIP_CODE = "12345"


@pytest.fixture(name="client")
def client_fixture(
    data_allergy_forecast,
    data_allergy_index,
    data_allergy_outlook,
    data_asthma_forecast,
    data_asthma_index,
    data_disease_forecast,
    data_disease_index,
):
    """Define a mock Client object."""
    return Mock(
        allergens=Mock(
            current=AsyncMock(return_value=data_allergy_index),
            extended=AsyncMock(return_value=data_allergy_forecast),
            outlook=AsyncMock(return_value=data_allergy_outlook),
        ),
        asthma=Mock(
            current=AsyncMock(return_value=data_asthma_index),
            extended=AsyncMock(return_value=data_asthma_forecast),
        ),
        disease=Mock(
            current=AsyncMock(return_value=data_disease_index),
            extended=AsyncMock(return_value=data_disease_forecast),
        ),
    )


@pytest.fixture(name="config_entry")
def config_entry_fixture(hass, config):
    """Define a config entry fixture."""
    entry = MockConfigEntry(domain=DOMAIN, unique_id=config[CONF_ZIP_CODE], data=config)
    entry.add_to_hass(hass)
    return entry


@pytest.fixture(name="config")
def config_fixture():
    """Define a config entry data fixture."""
    return {
        CONF_ZIP_CODE: TEST_ZIP_CODE,
    }


@pytest.fixture(name="data_allergy_forecast", scope="package")
def data_allergy_forecast_fixture():
    """Define allergy forecast data."""
    return json.loads(load_fixture("allergy_forecast_data.json", "iqvia"))


@pytest.fixture(name="data_allergy_index", scope="package")
def data_allergy_index_fixture():
    """Define allergy index data."""
    return json.loads(load_fixture("allergy_index_data.json", "iqvia"))


@pytest.fixture(name="data_allergy_outlook", scope="package")
def data_allergy_outlook_fixture():
    """Define allergy outlook data."""
    return json.loads(load_fixture("allergy_outlook_data.json", "iqvia"))


@pytest.fixture(name="data_asthma_forecast", scope="package")
def data_asthma_forecast_fixture():
    """Define asthma forecast data."""
    return json.loads(load_fixture("asthma_forecast_data.json", "iqvia"))


@pytest.fixture(name="data_asthma_index", scope="package")
def data_asthma_index_fixture():
    """Define asthma index data."""
    return json.loads(load_fixture("asthma_index_data.json", "iqvia"))


@pytest.fixture(name="data_disease_forecast", scope="package")
def data_disease_forecast_fixture():
    """Define disease forecast data."""
    return json.loads(load_fixture("disease_forecast_data.json", "iqvia"))


@pytest.fixture(name="data_disease_index", scope="package")
def data_disease_index_fixture():
    """Define disease index data."""
    return json.loads(load_fixture("disease_index_data.json", "iqvia"))


@pytest.fixture(name="mock_pyiqvia")
async def mock_pyiqvia_fixture(client):
    """Define a fixture to patch pyiqvia."""
    with patch("homeassistant.components.iqvia.Client", return_value=client), patch(
        "homeassistant.components.iqvia.config_flow.Client", return_value=client
    ):
        yield


@pytest.fixture(name="setup_config_entry")
async def setup_config_entry_fixture(hass, config_entry, mock_pyiqvia):
    """Define a fixture to set up iqvia."""
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    return
