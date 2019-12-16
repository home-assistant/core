"""Vera tests."""
from unittest.mock import MagicMock

import pyvera as pv
from requests.exceptions import RequestException

from homeassistant.components.vera import CONF_CONTROLLER, DOMAIN
from homeassistant.components.vera.common import ControllerData
from homeassistant.components.vera.config_flow import VeraFlowHandler
from homeassistant.core import HomeAssistant


async def test_async_step_import_error(hass: HomeAssistant) -> None:
    """Test function."""
    controller = MagicMock(spec=pv.VeraController)  # type: pv.VeraController
    controller.refresh_data.side_effect = RequestException()

    hass.data[DOMAIN] = ControllerData(controller=controller, devices={}, scenes=())

    handler = VeraFlowHandler()
    handler.hass = hass
    handler.async_create_entry = MagicMock(
        side_effect=Exception("Should not have been called.")
    )

    result = await handler.async_step_import({CONF_CONTROLLER: "http://127.0.0.1/"})

    assert result.get("type") == "abort"
    assert result.get("reason") == "cannot-connect"
    assert result.get("description_placeholders") == {"base_url": "http://127.0.0.1/"}
