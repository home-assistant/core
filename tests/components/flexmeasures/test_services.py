"""Test FlexMeasures integration services."""

from datetime import datetime
from unittest.mock import patch

import isodate

from homeassistant.components.flexmeasures.const import (
    DOMAIN,
    RESOLUTION,
    SERVICE_CHANGE_CONTROL_TYPE,
)
from homeassistant.components.flexmeasures.services import time_ceil
from homeassistant.core import HomeAssistant
import homeassistant.util.dt as dt_util


async def test_change_control_type_service(
    hass: HomeAssistant, setup_fm_integration
) -> None:
    """Test that the method activate_control_type is called when calling the service active_control_type."""
    await hass.services.async_call(
        DOMAIN,
        SERVICE_CHANGE_CONTROL_TYPE,
        service_data={"control_type": "NO_SELECTION"},
        blocking=True,
    )


async def test_trigger_and_get_schedule(
    hass: HomeAssistant, setup_fm_integration
) -> None:
    """Test that the method trigger_and_get_schedule is awaited when calling the service trigger_and_get_schedule."""
    with patch(
        "flexmeasures_client.client.FlexMeasuresClient.trigger_and_get_schedule",
        return_value={"values": [0.5, 0.41492, -0.0, -0.0], "unit": "MW"},
    ) as mocked_FlexmeasuresClient:
        await hass.services.async_call(
            DOMAIN,
            "trigger_and_get_schedule",
            service_data={"soc_at_start": 10},
            blocking=True,
        )
        tzinfo = dt_util.get_time_zone(hass.config.time_zone)
        mocked_FlexmeasuresClient.assert_awaited_with(
            sensor_id=1,
            start=time_ceil(
                datetime.now(tz=tzinfo), isodate.parse_duration(RESOLUTION)
            ),
            duration="PT24H",
            flex_model={
                "soc-unit": "kWh",
                "soc-at-start": 10,
                "soc-max": 0.001,
                "soc-min": 0.0,
            },
            flex_context={"consumption-price-sensor": 2, "production-price-sensor": 2},
        )


async def test_post_measurements(hass: HomeAssistant, setup_fm_integration) -> None:
    """Test that the method post measurements is called when calling the service post_measurements."""

    with patch(
        "flexmeasures_client.client.FlexMeasuresClient.post_measurements",
        return_value=None,
    ) as mocked_FlexmeasuresClient:
        await hass.services.async_call(
            DOMAIN,
            "post_measurements",
            service_data={
                "sensor_id": 1,
                "start": None,
                "duration": "PT24H",
                "values": [1, 1, 1, 3],
                "unit": "kWh",
                "prior": None,
            },
            blocking=True,
        )
        mocked_FlexmeasuresClient.assert_called_with(
            sensor_id=1,
            start=None,
            duration="PT24H",
            values=[1, 1, 1, 3],
            unit="kWh",
            prior=None,
        )
