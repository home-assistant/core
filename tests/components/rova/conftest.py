"""Common fixtures for Rova tests."""

from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components.rova.const import (
    CONF_HOUSE_NUMBER,
    CONF_HOUSE_NUMBER_SUFFIX,
    CONF_ZIP_CODE,
    DOMAIN,
)

from tests.common import MockConfigEntry, load_json_array_fixture


@pytest.fixture
def mock_rova():
    """Mock a successful Rova API."""
    api = MagicMock()

    with (
        patch(
            "homeassistant.components.rova.config_flow.Rova",
            return_value=api,
        ) as api,
        patch("homeassistant.components.rova.Rova", return_value=api),
    ):
        api.is_rova_area.return_value = True
        api.get_calendar_items.return_value = load_json_array_fixture(
            "calendar_items.json", DOMAIN
        )
        yield api


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id="8381BE13",
        title="8381BE 13",
        data={
            CONF_ZIP_CODE: "8381BE",
            CONF_HOUSE_NUMBER: "13",
            CONF_HOUSE_NUMBER_SUFFIX: "",
        },
    )
