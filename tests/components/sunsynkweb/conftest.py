"""Common fixtures for the Sunsynk Inverter Web tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, Mock, patch

from pysunsynkweb.model import Installation, Plant
import pytest

from homeassistant import config_entries
from homeassistant.components.sunsynkweb.const import DOMAIN
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock, None, None]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.sunsynkweb.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def basicdata():
    """Return the normal start of coordinator minimal api required from the api."""
    return [
        {"msg": "Success", "data": {"access_token": "12345"}},
        {
            "msg": "Success",
            "data": {
                "infos": [
                    {"name": "plant1", "id": 1, "masterId": 1, "status": 0},
                    {"name": "plant2", "id": 2, "masterId": 1, "status": 0},
                ]
            },
        },
        # enrich inverters
        {"msg": "Success", "data": {"infos": [{"sn": 123}]}},
        {"msg": "Success", "data": {"infos": [{"sn": 345}]}},
        # inst data
        {
            "code": 200,
            "msg": "Success",
            "data": {
                "battPower": 1,
                "toBat": True,
                "soc": 2,
                "loadOrEpsPower": 3,
                "gridOrMeterPower": 4,
                "toGrid": True,
                "pvPower": 5,
            },
        },
        # PV total
        {
            "data": {
                "infos": [
                    {
                        "records": [
                            {"year": 2024, "value": 1},
                            {"year": 2023, "value": 2},
                        ]
                    }
                ]
            }
        },
        # total grid
        {"data": {"etotalTo": 2, "etotalFrom": 3}},
        # totalbattery
        {"data": {"etotalChg": 3, "etotalDischg": 4}},
        # total load
        {"data": {"totalUsed": 6}},
        # inst data inv2
        {
            "code": 200,
            "msg": "Success",
            "data": {
                "battPower": 1,
                "toBat": True,
                "soc": 2,
                "loadOrEpsPower": 3,
                "gridOrMeterPower": 4,
                "toGrid": True,
                "pvPower": 5,
            },
        },
        # PV total
        {
            "data": {
                "infos": [
                    {
                        "records": [
                            {"year": 2024, "value": 1},
                            {"year": 2023, "value": 2},
                        ]
                    }
                ]
            }
        },
        # total grid
        {"data": {"etotalTo": 2, "etotalFrom": 3}},
        # totalbattery
        {"data": {"etotalChg": 3, "etotalDischg": 4}},
        # total load
        {"data": {"totalUsed": 6}},
    ]


@pytest.fixture
def sessiongetter():
    """Get a mocked session for controlling the data into initialisation."""
    with patch(
        "homeassistant.components.sunsynkweb.config_flow.async_get_clientsession",
        return_value=Mock(),
    ) as sessiongetter:
        session = AsyncMock()
        sessiongetter.return_value = session
        mockedjson_return = AsyncMock()
        mockedjson_return.name = "mocked_json_return"
        session.get.return_value = mockedjson_return
        session.post.return_value = mockedjson_return
        yield mockedjson_return


@pytest.fixture
async def basic_flow(hass):
    """Get a stub config flow."""
    return await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        title="sunsynkwebmocked",
        domain=DOMAIN,
        data={"username": "username", "password": "password"},
        unique_id="0000-0000",
        version=1,
        minor_version=2,
    )


@pytest.fixture
async def init_integration(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, basicdata
) -> MockConfigEntry:
    """Set up the integration for testing."""
    with patch(
        "homeassistant.components.sunsynkweb.coordinator.get_plants"
    ) as mockedplants:
        patchedplant = Plant(1, 2, "plant1", 1)
        patchedplant.update = AsyncMock()
        mockedplants.return_value = Installation([patchedplant])
        patchedplant.update.side_effect = basicdata
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        patchedplant.update.assert_called_once()
        coordinator = mock_config_entry.runtime_data
        await coordinator._async_update_data()
        await hass.async_block_till_done()
        yield mock_config_entry
