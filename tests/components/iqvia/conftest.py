"""Define test fixtures for IQVIA."""

from collections.abc import AsyncGenerator
from typing import Any
from unittest.mock import patch

import pytest

from homeassistant.components.iqvia.const import CONF_ZIP_CODE, DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from homeassistant.util.json import JsonObjectType

from tests.common import MockConfigEntry, load_json_object_fixture


@pytest.fixture(name="config_entry")
def config_entry_fixture(
    hass: HomeAssistant, config: dict[str, Any]
) -> MockConfigEntry:
    """Define a config entry fixture."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=config[CONF_ZIP_CODE],
        data=config,
        entry_id="690ac4b7e99855fc5ee7b987a758d5cb",
    )
    entry.add_to_hass(hass)
    return entry


@pytest.fixture(name="config")
def config_fixture() -> dict[str, Any]:
    """Define a config entry data fixture."""
    return {
        CONF_ZIP_CODE: "12345",
    }


@pytest.fixture(name="data_allergy_forecast", scope="package")
def data_allergy_forecast_fixture() -> JsonObjectType:
    """Define allergy forecast data."""
    return load_json_object_fixture("allergy_forecast_data.json", "iqvia")


@pytest.fixture(name="data_allergy_index", scope="package")
def data_allergy_index_fixture() -> JsonObjectType:
    """Define allergy index data."""
    return load_json_object_fixture("allergy_index_data.json", "iqvia")


@pytest.fixture(name="data_allergy_outlook", scope="package")
def data_allergy_outlook_fixture() -> JsonObjectType:
    """Define allergy outlook data."""
    return load_json_object_fixture("allergy_outlook_data.json", "iqvia")


@pytest.fixture(name="data_asthma_forecast", scope="package")
def data_asthma_forecast_fixture() -> JsonObjectType:
    """Define asthma forecast data."""
    return load_json_object_fixture("asthma_forecast_data.json", "iqvia")


@pytest.fixture(name="data_asthma_index", scope="package")
def data_asthma_index_fixture() -> JsonObjectType:
    """Define asthma index data."""
    return load_json_object_fixture("asthma_index_data.json", "iqvia")


@pytest.fixture(name="data_disease_forecast", scope="package")
def data_disease_forecast_fixture() -> JsonObjectType:
    """Define disease forecast data."""
    return load_json_object_fixture("disease_forecast_data.json", "iqvia")


@pytest.fixture(name="data_disease_index", scope="package")
def data_disease_index_fixture() -> JsonObjectType:
    """Define disease index data."""
    return load_json_object_fixture("disease_index_data.json", "iqvia")


@pytest.fixture(name="setup_iqvia")
async def setup_iqvia_fixture(
    hass: HomeAssistant,
    config: dict[str, Any],
    data_allergy_forecast: JsonObjectType,
    data_allergy_index: JsonObjectType,
    data_allergy_outlook: JsonObjectType,
    data_asthma_forecast: JsonObjectType,
    data_asthma_index: JsonObjectType,
    data_disease_forecast: JsonObjectType,
    data_disease_index: JsonObjectType,
) -> AsyncGenerator[None]:
    """Define a fixture to set up IQVIA."""
    with (
        patch(
            "pyiqvia.allergens.Allergens.extended", return_value=data_allergy_forecast
        ),
        patch("pyiqvia.allergens.Allergens.current", return_value=data_allergy_index),
        patch("pyiqvia.allergens.Allergens.outlook", return_value=data_allergy_outlook),
        patch("pyiqvia.asthma.Asthma.extended", return_value=data_asthma_forecast),
        patch("pyiqvia.asthma.Asthma.current", return_value=data_asthma_index),
        patch("pyiqvia.disease.Disease.extended", return_value=data_disease_forecast),
        patch("pyiqvia.disease.Disease.current", return_value=data_disease_index),
        patch("homeassistant.components.iqvia.PLATFORMS", []),
    ):
        assert await async_setup_component(hass, DOMAIN, config)
        await hass.async_block_till_done()
        yield
