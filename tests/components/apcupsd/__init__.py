"""Tests for the APCUPSd component."""
from collections import OrderedDict
from typing import Final
from unittest.mock import patch

from homeassistant.components.apcupsd import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

CONF_DATA: Final = {CONF_HOST: "test", CONF_PORT: 1234}

MOCK_STATUS: Final = OrderedDict(
    [
        ("APC", "001,038,0985"),
        ("DATE", "1970-01-01 00:00:00 0000"),
        ("VERSION", "3.14.14 (31 May 2016) unknown"),
        ("CABLE", "USB Cable"),
        ("DRIVER", "USB UPS Driver"),
        ("UPSMODE", "Stand Alone"),
        ("UPSNAME", "MyUPS"),
        ("MODEL", "Back-UPS ES 600"),
        ("STATUS", "ONLINE"),
        ("LINEV", "124.0 Volts"),
        ("LOADPCT", "14.0 Percent"),
        ("BCHARGE", "100.0 Percent"),
        ("TIMELEFT", "51.0 Minutes"),
        ("NOMAPNT", "60.0 VA"),
        ("ITEMP", "34.6 C Internal"),
        ("MBATTCHG", "5 Percent"),
        ("MINTIMEL", "3 Minutes"),
        ("MAXTIME", "0 Seconds"),
        ("SENSE", "Medium"),
        ("LOTRANS", "92.0 Volts"),
        ("HITRANS", "139.0 Volts"),
        ("ALARMDEL", "30 Seconds"),
        ("BATTV", "13.7 Volts"),
        ("OUTCURNT", "0.88 Amps"),
        ("LASTXFER", "Automatic or explicit self test"),
        ("NUMXFERS", "1"),
        ("XONBATT", "1970-01-01 00:00:00 0000"),
        ("TONBATT", "0 Seconds"),
        ("CUMONBATT", "8 Seconds"),
        ("XOFFBATT", "1970-01-01 00:00:00 0000"),
        ("LASTSTEST", "1970-01-01 00:00:00 0000"),
        ("SELFTEST", "NO"),
        ("STESTI", "7 days"),
        ("STATFLAG", "0x05000008"),
        ("SERIALNO", "XXXXXXXXXXXX"),
        ("BATTDATE", "1970-01-01"),
        ("NOMINV", "120 Volts"),
        ("NOMBATTV", "12.0 Volts"),
        ("NOMPOWER", "330 Watts"),
        ("FIRMWARE", "928.a8 .D USB FW:a8"),
        ("END APC", "1970-01-01 00:00:00 0000"),
    ]
)

# Minimal status adapted from http://www.apcupsd.org/manual/manual.html#apcaccess-test.
# Most importantly, the "MODEL" and "SERIALNO" fields are removed to test the ability
# of the integration to handle such cases.
MOCK_MINIMAL_STATUS: Final = OrderedDict(
    [
        ("APC", "001,012,0319"),
        ("DATE", "1970-01-01 00:00:00 0000"),
        ("RELEASE", "3.8.5"),
        ("CABLE", "APC Cable 940-0128A"),
        ("UPSMODE", "Stand Alone"),
        ("STARTTIME", "1970-01-01 00:00:00 0000"),
        ("LINEFAIL", "OK"),
        ("BATTSTAT", "OK"),
        ("STATFLAG", "0x008"),
        ("END APC", "1970-01-01 00:00:00 0000"),
    ]
)


async def async_init_integration(
    hass: HomeAssistant, host: str = "test", status=None
) -> MockConfigEntry:
    """Set up the APC UPS Daemon integration in HomeAssistant."""
    if status is None:
        status = MOCK_STATUS

    entry = MockConfigEntry(
        version=1,
        domain=DOMAIN,
        title="APCUPSd",
        data=CONF_DATA | {CONF_HOST: host},
        unique_id=status.get("SERIALNO", None),
        source=SOURCE_USER,
    )

    entry.add_to_hass(hass)

    with patch("aioapcaccess.request_status", return_value=status):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    return entry
