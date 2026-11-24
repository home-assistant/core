"""Test the ADS actions."""

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import probatio
import pyads
import pytest

from homeassistant.components.ads import services
from homeassistant.components.ads.const import DOMAIN, AdsType
from homeassistant.core import HomeAssistant
from homeassistant.util.yaml import load_yaml_dict

SERVICE_WRITE_DATA_BY_NAME = "write_data_by_name"
ADS_VAR = "GVL.setpoint"


@pytest.mark.usefixtures("setup_ads")
@pytest.mark.parametrize(
    ("adstype", "value", "written", "plc_datatype"),
    [
        pytest.param("int", 42, 42, pyads.PLCTYPE_INT, id="int"),
        pytest.param("int", "42", 42, pyads.PLCTYPE_INT, id="int_from_text"),
        pytest.param("udint", 70000, 70000, pyads.PLCTYPE_UDINT, id="udint"),
        pytest.param("time", "1500", 1500, pyads.PLCTYPE_TIME, id="time"),
        pytest.param("bool", 1, True, pyads.PLCTYPE_BOOL, id="bool_as_int"),
        pytest.param("bool", "off", False, pyads.PLCTYPE_BOOL, id="bool_from_text"),
        pytest.param("real", 21, 21.0, pyads.PLCTYPE_REAL, id="real_as_int"),
        pytest.param("real", "21.5", 21.5, pyads.PLCTYPE_REAL, id="real_from_text"),
        pytest.param("lreal", 0.125, 0.125, pyads.PLCTYPE_LREAL, id="lreal"),
        pytest.param("string", "hello", "hello", pyads.PLCTYPE_STRING, id="string"),
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
    """Test the write action writes the value as the type the ADS type needs."""
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
            {"adsvar": ADS_VAR, "adstype": "int", "value": "21.5"},
            id="fractional_int",
        ),
        pytest.param(
            {"adsvar": ADS_VAR, "adstype": "int", "value": "hello"},
            id="text_int",
        ),
        pytest.param(
            {"adsvar": ADS_VAR, "adstype": "bool", "value": "maybe"},
            id="text_bool",
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
    """Test the action rejects a value its ADS type cannot hold."""
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


def test_selector_lists_every_ads_type() -> None:
    """Test the action selector offers exactly the types the action accepts."""
    description = load_yaml_dict(str(Path(services.__file__).parent / "services.yaml"))
    options = description["write_data_by_name"]["fields"]["adstype"]["selector"][
        "select"
    ]["options"]

    assert sorted(options) == sorted(AdsType)
