"""Common fixtures for the Data Grand Lyon tests."""

from collections.abc import Generator
from datetime import datetime
from unittest.mock import AsyncMock, patch

from data_grand_lyon_ha import TclPassage, TclPassageType
import pytest

from homeassistant.components.data_grandlyon.const import (
    CONF_LINE,
    CONF_STOP_ID,
    DOMAIN,
    SUBENTRY_TYPE_STOP,
)
from homeassistant.config_entries import ConfigSubentryData
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME

from tests.common import MockConfigEntry

MOCK_PASSAGES = [
    TclPassage(
        id=100,
        ligne="C3",
        direction="Gare Part-Dieu",
        delai_passage="3 min",
        type=TclPassageType.ESTIMATED,
        heure_passage=datetime(2026, 4, 10, 14, 3),
        id_tarret_destination=0,
        course_theorique="A",
    ),
    TclPassage(
        id=100,
        ligne="C3",
        direction="Gare St-Paul",
        delai_passage="8 min",
        type=TclPassageType.THEORETICAL,
        heure_passage=datetime(2026, 4, 10, 14, 8),
        id_tarret_destination=0,
        course_theorique="B",
    ),
]


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.data_grandlyon.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_subentries() -> list[ConfigSubentryData]:
    """Mock subentries."""
    return [
        ConfigSubentryData(
            data={CONF_LINE: "C3", CONF_STOP_ID: 100},
            subentry_id="stop_1",
            subentry_type=SUBENTRY_TYPE_STOP,
            title="C3 - Stop 100",
            unique_id="C3_100",
        )
    ]


@pytest.fixture
def mock_config_entry(
    mock_subentries: list[ConfigSubentryData],
) -> MockConfigEntry:
    """Create a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Data Grand Lyon",
        data={CONF_USERNAME: "user", CONF_PASSWORD: "pass"},
        subentries_data=mock_subentries,
    )


@pytest.fixture
def mock_tcl_client() -> Generator[AsyncMock]:
    """Mock DataGrandLyonClient for coordinator."""
    with patch(
        "homeassistant.components.data_grandlyon.DataGrandLyonClient", autospec=True
    ) as mock_cls:
        client = mock_cls.return_value
        client.get_tcl_passages.return_value = MOCK_PASSAGES
        yield client
