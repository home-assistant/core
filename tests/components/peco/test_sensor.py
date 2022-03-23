"""Test the PECO Outage Counter sensors."""
import asyncio

from homeassistant.components.peco.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker

MOCK_ENTRY_DATA = {"county": "TOTAL"}
COUNTY_ENTRY_DATA = {"county": "BUCKS"}
INVALID_COUNTY_DATA = {"county": "INVALID"}


async def test_sensor_available(
    aioclient_mock: AiohttpClientMocker, hass: HomeAssistant
) -> None:
    """Test that the sensors are working."""
    # Totals Test
    aioclient_mock.get(
        "https://kubra.io/stormcenter/api/v1/stormcenters/39e6d9f3-fdea-4539-848f-b8631945da6f/views/74de8a50-3f45-4f6a-9483-fd618bb9165d/currentState?preview=false",
        json={"data": {"interval_generation_data": "data/TEST"}},
    )
    aioclient_mock.get(
        "https://kubra.io/data/TEST/public/reports/a36a6292-1c55-44de-a6a9-44fedf9482ee_report.json",
        json={
            "file_data": {
                "totals": {
                    "cust_a": {
                        "val": 123,
                    },
                    "percent_cust_a": {
                        "val": 1.23,
                    },
                    "n_out": 456,
                    "cust_s": 789,
                }
            }
        },
    )

    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_ENTRY_DATA)
    config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert hass.data[DOMAIN]

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert config_entry.state == ConfigEntryState.LOADED

    sensors_to_get = [
        "total_customers_out",
        "total_percent_customers_out",
        "total_outage_count",
        "total_customers_served",
    ]

    for sensor in sensors_to_get:
        sensor_entity = hass.states.get(f"sensor.{sensor}")
        assert sensor_entity is not None
        assert sensor_entity.state != "unavailable"

        if sensor == "total_customers_out":
            assert sensor_entity.state == "123"
        elif sensor == "total_percent_customers_out":
            assert sensor_entity.state == "15.589"
        elif sensor == "total_outage_count":
            assert sensor_entity.state == "456"
        elif sensor == "total_customers_served":
            assert sensor_entity.state == "789"

    # County Test
    aioclient_mock.clear_requests()
    aioclient_mock.get(
        "https://kubra.io/stormcenter/api/v1/stormcenters/39e6d9f3-fdea-4539-848f-b8631945da6f/views/74de8a50-3f45-4f6a-9483-fd618bb9165d/currentState?preview=false",
        json={"data": {"interval_generation_data": "data/TEST"}},
    )
    aioclient_mock.get(
        "https://kubra.io/data/TEST/public/reports/a36a6292-1c55-44de-a6a9-44fedf9482ee_report.json",
        json={
            "file_data": {
                "areas": [
                    {
                        "name": "BUCKS",
                        "cust_a": {
                            "val": 123,
                        },
                        "percent_cust_a": {
                            "val": 1.23,
                        },
                        "n_out": 456,
                        "cust_s": 789,
                    }
                ]
            }
        },
    )

    config_entry = MockConfigEntry(domain=DOMAIN, data=COUNTY_ENTRY_DATA)
    config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert hass.data[DOMAIN]

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 2
    assert config_entry.state == ConfigEntryState.LOADED

    sensors_to_get = [
        "bucks_customers_out",
        "bucks_percent_customers_out",
        "bucks_outage_count",
        "bucks_customers_served",
    ]

    for sensor in sensors_to_get:
        sensor_entity = hass.states.get(f"sensor.{sensor}")
        assert sensor_entity is not None
        assert sensor_entity.state != "unavailable"

        if sensor == "bucks_customers_out":
            assert sensor_entity.state == "123"
        elif sensor == "bucks_percent_customers_out":
            assert sensor_entity.state == "15.589"
        elif sensor == "bucks_outage_count":
            assert sensor_entity.state == "456"
        elif sensor == "bucks_customers_served":
            assert sensor_entity.state == "789"


async def test_http_error(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, caplog
):
    """Test if it raises an error when there is an HTTP error."""
    aioclient_mock.get(
        "https://kubra.io/stormcenter/api/v1/stormcenters/39e6d9f3-fdea-4539-848f-b8631945da6f/views/74de8a50-3f45-4f6a-9483-fd618bb9165d/currentState?preview=false",
        json={"data": {"interval_generation_data": "data/TEST"}},
    )
    aioclient_mock.get(
        "https://kubra.io/data/TEST/public/reports/a36a6292-1c55-44de-a6a9-44fedf9482ee_report.json",
        status=500,
        json={"error": "Internal Server Error"},
    )

    config_entry = MockConfigEntry(domain=DOMAIN, data=COUNTY_ENTRY_DATA)
    config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert hass.data[DOMAIN]

    assert "Error getting PECO outage counter data" in caplog.text


async def test_bad_json(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, caplog
):
    """Test if it raises an error when there is bad JSON."""
    aioclient_mock.get(
        "https://kubra.io/stormcenter/api/v1/stormcenters/39e6d9f3-fdea-4539-848f-b8631945da6f/views/74de8a50-3f45-4f6a-9483-fd618bb9165d/currentState?preview=false",
        json={"data": {}},
    )

    config_entry = MockConfigEntry(domain=DOMAIN, data=COUNTY_ENTRY_DATA)
    config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert hass.data[DOMAIN]

    assert "ConfigEntryNotReady" in caplog.text


async def test_total_http_error(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, caplog
):
    """Test if it raises an error when there is an HTTP error."""
    aioclient_mock.get(
        "https://kubra.io/stormcenter/api/v1/stormcenters/39e6d9f3-fdea-4539-848f-b8631945da6f/views/74de8a50-3f45-4f6a-9483-fd618bb9165d/currentState?preview=false",
        json={"data": {"interval_generation_data": "data/TEST"}},
    )
    aioclient_mock.get(
        "https://kubra.io/data/TEST/public/reports/a36a6292-1c55-44de-a6a9-44fedf9482ee_report.json",
        status=500,
        json={"error": "Internal Server Error"},
    )

    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_ENTRY_DATA)
    config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert hass.data[DOMAIN]

    assert "Error getting PECO outage counter data" in caplog.text


async def test_total_bad_json(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, caplog
):
    """Test if it raises an error when there is bad JSON."""
    aioclient_mock.get(
        "https://kubra.io/stormcenter/api/v1/stormcenters/39e6d9f3-fdea-4539-848f-b8631945da6f/views/74de8a50-3f45-4f6a-9483-fd618bb9165d/currentState?preview=false",
        json={"data": {}},
    )

    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_ENTRY_DATA)
    config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert hass.data[DOMAIN]

    assert "ConfigEntryNotReady" in caplog.text


async def test_update_timeout(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, caplog
):
    """Test if it raises an error when there is a timeout."""
    aioclient_mock.get(
        "https://kubra.io/stormcenter/api/v1/stormcenters/39e6d9f3-fdea-4539-848f-b8631945da6f/views/74de8a50-3f45-4f6a-9483-fd618bb9165d/currentState?preview=false",
        exc=asyncio.TimeoutError(),
    )

    config_entry = MockConfigEntry(domain=DOMAIN, data=COUNTY_ENTRY_DATA)
    config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert hass.data[DOMAIN]

    assert "Timeout fetching data" in caplog.text


async def test_total_update_timeout(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, caplog
):
    """Test if it raises an error when there is a timeout."""
    aioclient_mock.get(
        "https://kubra.io/stormcenter/api/v1/stormcenters/39e6d9f3-fdea-4539-848f-b8631945da6f/views/74de8a50-3f45-4f6a-9483-fd618bb9165d/currentState?preview=false",
        exc=asyncio.TimeoutError(),
    )

    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_ENTRY_DATA)
    config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert hass.data[DOMAIN]

    assert "Timeout fetching data" in caplog.text
