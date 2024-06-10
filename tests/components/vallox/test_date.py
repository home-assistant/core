"""Tests for Vallox date platform."""

from datetime import date

from vallox_websocket_api import MetricData

from homeassistant.components.date.const import DOMAIN as DATE_DOMAIN, SERVICE_SET_VALUE
from homeassistant.const import ATTR_DATE, ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant

from .conftest import patch_set_filter_change_date

from tests.common import MockConfigEntry


async def test_set_filter_change_date(
    mock_entry: MockConfigEntry,
    hass: HomeAssistant,
    setup_fetch_metric_data_mock,
) -> None:
    """Test set filter change date."""

    entity_id = "date.vallox_filter_change_date"

    class MockMetricData(MetricData):
        @property
        def filter_change_date(self):
            return date(2024, 1, 1)

    setup_fetch_metric_data_mock(metric_data_class=MockMetricData)

    with patch_set_filter_change_date() as set_filter_change_date:
        await hass.config_entries.async_setup(mock_entry.entry_id)
        await hass.async_block_till_done()

        state = hass.states.get(entity_id)
        assert state

        assert state.state == "2024-01-01"

        await hass.services.async_call(
            DATE_DOMAIN,
            SERVICE_SET_VALUE,
            service_data={
                ATTR_ENTITY_ID: entity_id,
                ATTR_DATE: "2024-02-25",
            },
        )
        await hass.async_block_till_done()
        set_filter_change_date.assert_called_once_with(date(2024, 2, 25))
