# pytest ./tests/components/flexmeasures/ --cov=homeassistant.components.flexmeasures --cov-report term-missing -vv

from unittest.mock import patch

from datetime import datetime, timedelta
import pytz

from flexmeasures_client.s2.python_s2_protocol.common.schemas import ControlType
from flexmeasures_client import FlexMeasuresClient

from homeassistant.components.flexmeasures.helpers import time_ceil
from homeassistant.components.flexmeasures.const import (
    DOMAIN,
    SERVICE_CHANGE_CONTROL_TYPE,
    RESOLUTION,
)
from homeassistant.core import HomeAssistant


async def test_change_control_type_service(hass: HomeAssistant, setup_fm_integration):
    """Test that the method activate_control_type is called when calling the service active_control_type."""

    with patch(
        "flexmeasures_client.s2.cem.CEM.activate_control_type", return_value=None
    ) as mocked_CEM:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_CHANGE_CONTROL_TYPE,
            service_data={"control_type": "NO_SELECTION"},
            blocking=True,
        )
        mocked_CEM.assert_called_with(control_type=ControlType.NO_SELECTION)


async def test_trigger_and_get_schedule(hass: HomeAssistant, setup_fm_integration):
    """Test that the method activate_control_type is called when calling the service active_control_type."""

    with patch(
        "flexmeasures_client.client.FlexMeasuresClient.trigger_and_get_schedule",
        return_value=None,
    ) as mocked_FlexmeasuresClient:
        await hass.services.async_call(
            DOMAIN,
            "trigger_and_get_schedule",
            service_data={"soc_at_start": 10},
            blocking=True,
        )
        mocked_FlexmeasuresClient.assert_called_with(
            sensor_id=1,
            start=time_ceil(datetime.now(tz=pytz.utc), timedelta(minutes=RESOLUTION)),
            duration="PT24H",
            soc_unit="kWh",
            soc_min=0.0,
            soc_max=0.001,
            consumption_price_sensor=2,
            production_price_sensor=2,
            soc_at_start=10,
        )


async def test_post_measurements(hass: HomeAssistant, setup_fm_integration):
    """Test that the method activate_control_type is called when calling the service active_control_type."""

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
