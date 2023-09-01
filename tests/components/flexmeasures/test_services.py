# pytest ./tests/components/flexmeasures/ --cov=homeassistant.components.flexmeasures --cov-report term-missing -vv

from unittest.mock import patch

from flexmeasures_client.s2.python_s2_protocol.common.schemas import ControlType

from homeassistant.components.flexmeasures.const import (
    DOMAIN,
    SERVICE_CHANGE_CONTROL_TYPE,
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
