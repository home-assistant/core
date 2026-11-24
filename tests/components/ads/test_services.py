"""Test the ADS actions."""

from typing import Any
from unittest.mock import MagicMock

import probatio
import pyads
import pytest

from homeassistant.components.ads.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.setup import async_setup_component

SERVICE_WRITE_DATA_BY_NAME = "write_data_by_name"
ADS_VAR = "GVL.setpoint"


@pytest.mark.usefixtures("setup_ads")
@pytest.mark.parametrize(
    ("adstype", "value", "written", "plc_datatype"),
    [
        pytest.param("int", 42, 42, pyads.PLCTYPE_INT, id="int"),
        pytest.param("int", "42", 42, pyads.PLCTYPE_INT, id="int_from_text"),
        pytest.param("udint", 70000, 70000, pyads.PLCTYPE_UDINT, id="udint"),
        pytest.param("bool", 1, 1, pyads.PLCTYPE_BOOL, id="bool_as_int"),
        pytest.param("real", 21, 21, pyads.PLCTYPE_REAL, id="real_as_int"),
    ],
)
async def test_write_data_by_name(
    hass: HomeAssistant,
    mock_pyads_connection: MagicMock,
    adstype: str,
    value: Any,
    written: Any,
    plc_datatype: type,
) -> None:
    """Test the write action writes the value to the PLC as an integer."""
    await hass.services.async_call(
        DOMAIN,
        SERVICE_WRITE_DATA_BY_NAME,
        {"adsvar": ADS_VAR, "adstype": adstype, "value": value},
        blocking=True,
    )

    mock_pyads_connection.return_value.write_by_name.assert_called_once_with(
        ADS_VAR, written, plc_datatype
    )


@pytest.mark.usefixtures("setup_ads")
@pytest.mark.parametrize(
    "data",
    [
        pytest.param(
            {"adsvar": ADS_VAR, "adstype": "real", "value": "21.5"},
            id="fractional_value",
        ),
        pytest.param(
            {"adsvar": ADS_VAR, "adstype": "string", "value": "hello"},
            id="text_value",
        ),
        pytest.param(
            {"adsvar": ADS_VAR, "adstype": "float", "value": 1},
            id="unknown_adstype",
        ),
        pytest.param({"adstype": "int", "value": 1}, id="missing_adsvar"),
    ],
)
async def test_write_data_by_name_invalid(
    hass: HomeAssistant, mock_pyads_connection: MagicMock, data: dict[str, Any]
) -> None:
    """Test the action rejects data it cannot write as an integer."""
    with pytest.raises(probatio.Invalid):
        await hass.services.async_call(
            DOMAIN, SERVICE_WRITE_DATA_BY_NAME, data, blocking=True
        )

    mock_pyads_connection.return_value.write_by_name.assert_not_called()


@pytest.mark.usefixtures("setup_ads")
async def test_write_data_by_name_error(
    hass: HomeAssistant,
    mock_pyads_connection: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a failing write is logged instead of raised at the caller."""
    mock_pyads_connection.return_value.write_by_name.side_effect = pyads.ADSError(
        err_code=1861
    )

    await hass.services.async_call(
        DOMAIN,
        SERVICE_WRITE_DATA_BY_NAME,
        {"adsvar": ADS_VAR, "adstype": "int", "value": 42},
        blocking=True,
    )

    assert f"Error writing {ADS_VAR}" in caplog.text


async def test_write_data_by_name_not_loaded(hass: HomeAssistant) -> None:
    """Test the write action is refused while no connection is set up."""
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_WRITE_DATA_BY_NAME,
            {"adsvar": ADS_VAR, "adstype": "int", "value": 42},
            blocking=True,
        )

    assert exc_info.value.translation_key == "not_loaded"
