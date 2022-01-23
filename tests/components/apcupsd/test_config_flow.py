"""Test APCUPSd setup process."""

from collections import OrderedDict
from typing import Final

from homeassistant import config_entries, data_entry_flow
from homeassistant.components.apcupsd import DOMAIN
from homeassistant.const import CONF_HOST, CONF_PORT

MOCK_DATA: Final = {
    CONF_HOST: "localhost",
    CONF_PORT: 3551,
}

MOCK_STATUS: Final = OrderedDict(
    [
        ("APC", "001,038,0985"),
        ("DATE", "2022-01-22 23:07:19 -0500"),
        ("VERSION", "3.14.14 (31 May 2016) unknown"),
        ("CABLE", "USB Cable"),
        ("DRIVER", "USB UPS Driver"),
        ("UPSMODE", "Stand Alone"),
        ("MODEL", "Back-UPS ES 600"),
        ("STATUS", "ONLINE"),
        ("LINEV", "124.0 Volts"),
        ("LOADPCT", "14.0 Percent"),
        ("BCHARGE", "100.0 Percent"),
        ("TIMELEFT", "51.0 Minutes"),
        ("MBATTCHG", "5 Percent"),
        ("MINTIMEL", "3 Minutes"),
        ("MAXTIME", "0 Seconds"),
        ("SENSE", "Medium"),
        ("LOTRANS", "92.0 Volts"),
        ("HITRANS", "139.0 Volts"),
        ("ALARMDEL", "30 Seconds"),
        ("BATTV", "13.7 Volts"),
        ("LASTXFER", "Automatic or explicit self test"),
        ("NUMXFERS", "1"),
        ("XONBATT", "2022-01-22 17:12:34 -0500"),
        ("TONBATT", "0 Seconds"),
        ("CUMONBATT", "8 Seconds"),
        ("XOFFBATT", "2022-01-22 17:12:42 -0500"),
        ("LASTSTEST", "2022-01-22 17:12:34 -0500"),
        ("SELFTEST", "NO"),
        ("STATFLAG", "0x05000008"),
        ("SERIALNO", "XXXXXXXXXXXX"),
        ("BATTDATE", "1970-01-01"),
        ("NOMINV", "120 Volts"),
        ("NOMBATTV", "12.0 Volts"),
        ("NOMPOWER", "330 Watts"),
        ("FIRMWARE", "928.a8 .D USB FW:a8"),
        ("END APC", "2022-01-22 23:08:16 -050"),
    ]
)


async def test_flow_works(hass):
    """Test config flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"
    assert result["data_schema"]({CONF_HOST: "", CONF_PORT: ""}) == {
        CONF_HOST: "localhost",
        CONF_PORT: 3551,
    }

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_HOST: "localhost", CONF_PORT: 3551},
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert "UPS" in result["title"]
    assert result["description"] == "APCUPSd"
    assert result["data"] == {CONF_HOST: "localhost", CONF_PORT: 3551}
