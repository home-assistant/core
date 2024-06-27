"""Mealie tests configuration."""

from unittest.mock import patch

from aiomealie import Mealplan, MealplanResponse
from mashumaro.codecs.orjson import ORJSONDecoder
import pytest
from typing_extensions import Generator

from homeassistant.components.mealie.const import DOMAIN
from homeassistant.const import CONF_API_TOKEN, CONF_HOST

from tests.common import MockConfigEntry, load_fixture
from tests.components.smhi.common import AsyncMock


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.mealie.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_mealie_client() -> Generator[AsyncMock]:
    """Mock a Mealie client."""
    with (
        patch(
            "homeassistant.components.mealie.coordinator.MealieClient",
            autospec=True,
        ) as mock_client,
        patch(
            "homeassistant.components.mealie.config_flow.MealieClient",
            new=mock_client,
        ),
    ):
        client = mock_client.return_value
        client.get_mealplans.return_value = MealplanResponse.from_json(
            load_fixture("get_mealplans.json", DOMAIN)
        )
        client.get_mealplan_today.return_value = ORJSONDecoder(list[Mealplan]).decode(
            load_fixture("get_mealplan_today.json", DOMAIN)
        )
        yield client


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Mock a config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Mealie",
        data={CONF_HOST: "demo.mealie.io", CONF_API_TOKEN: "token"},
        entry_id="01J0BC4QM2YBRP6H5G933CETT7",
    )
