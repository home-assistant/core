"""Tests for the Nightscout integration."""

import json
from unittest.mock import patch

from aiohttp import ClientConnectionError
from py_nightscout.models import SGV, ServerStatus

from homeassistant.components.nightscout.const import DOMAIN
from homeassistant.const import CONF_URL

from tests.common import MockConfigEntry

GLUCOSE_READINGS = [
    SGV.new_from_json_dict(
        json.loads(
            '{"_id":"5f2b01f5c3d0ac7c4090e223","device":"xDrip-LimiTTer","date":1596654066533,"dateString":"2020-08-05T19:01:06.533Z","sgv":169,"delta":-5.257,"direction":"FortyFiveDown","type":"sgv","filtered":182823.5157,"unfiltered":182823.5157,"rssi":100,"noise":1,"sysTime":"2020-08-05T19:01:06.533Z","utcOffset":-180}'
        )
    )
]
SERVER_STATUS = ServerStatus.new_from_json_dict(
    json.loads(
        '{"status":"ok","name":"nightscout","version":"13.0.1","serverTime":"2020-08-05T18:14:02.032Z","serverTimeEpoch":1596651242032,"apiEnabled":true,"careportalEnabled":true,"boluscalcEnabled":true,"settings":{},"extendedSettings":{},"authorized":null}'
    )
)
SERVER_STATUS_STATUS_ONLY = ServerStatus.new_from_json_dict(
    json.loads(
        '{"status":"ok","name":"nightscout","version":"14.0.4","serverTime":"2020-09-25T21:03:59.315Z","serverTimeEpoch":1601067839315,"apiEnabled":true,"careportalEnabled":true,"boluscalcEnabled":true,"settings":{"units":"mg/dl","timeFormat":12,"nightMode":false,"editMode":true,"showRawbg":"never","customTitle":"Nightscout","theme":"default","alarmUrgentHigh":true,"alarmUrgentHighMins":[30,60,90,120],"alarmHigh":true,"alarmHighMins":[30,60,90,120],"alarmLow":true,"alarmLowMins":[15,30,45,60],"alarmUrgentLow":true,"alarmUrgentLowMins":[15,30,45],"alarmUrgentMins":[30,60,90,120],"alarmWarnMins":[30,60,90,120],"alarmTimeagoWarn":true,"alarmTimeagoWarnMins":15,"alarmTimeagoUrgent":true,"alarmTimeagoUrgentMins":30,"alarmPumpBatteryLow":false,"language":"en","scaleY":"log","showPlugins":"dbsize delta direction upbat","showForecast":"ar2","focusHours":3,"heartbeat":60,"baseURL":"","authDefaultRoles":"status-only","thresholds":{"bgHigh":260,"bgTargetTop":180,"bgTargetBottom":80,"bgLow":55},"insecureUseHttp":true,"secureHstsHeader":false,"secureHstsHeaderIncludeSubdomains":false,"secureHstsHeaderPreload":false,"secureCsp":false,"deNormalizeDates":false,"showClockDelta":false,"showClockLastTime":false,"bolusRenderOver":1,"frameUrl1":"","frameUrl2":"","frameUrl3":"","frameUrl4":"","frameUrl5":"","frameUrl6":"","frameUrl7":"","frameUrl8":"","frameName1":"","frameName2":"","frameName3":"","frameName4":"","frameName5":"","frameName6":"","frameName7":"","frameName8":"","DEFAULT_FEATURES":["bgnow","delta","direction","timeago","devicestatus","upbat","errorcodes","profile","dbsize"],"alarmTypes":["predict"],"enable":["careportal","boluscalc","food","bwp","cage","sage","iage","iob","cob","basal","ar2","rawbg","pushover","bgi","pump","openaps","treatmentnotify","bgnow","delta","direction","timeago","devicestatus","upbat","errorcodes","profile","dbsize","ar2"]},"extendedSettings":{"devicestatus":{"advanced":true,"days":1}},"authorized":null}'
    )
)


async def init_integration(hass) -> MockConfigEntry:
    """Set up the Nightscout integration in Home Assistant."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_URL: "https://some.url:1234"},
    )
    with (
        patch(
            "homeassistant.components.nightscout.NightscoutAPI.get_sgvs",
            return_value=GLUCOSE_READINGS,
        ),
        patch(
            "homeassistant.components.nightscout.NightscoutAPI.get_server_status",
            return_value=SERVER_STATUS,
        ),
    ):
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    return entry


async def init_integration_unavailable(hass) -> MockConfigEntry:
    """Set up the Nightscout integration in Home Assistant."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_URL: "https://some.url:1234"},
    )
    with (
        patch(
            "homeassistant.components.nightscout.NightscoutAPI.get_sgvs",
            side_effect=ClientConnectionError(),
        ),
        patch(
            "homeassistant.components.nightscout.NightscoutAPI.get_server_status",
            return_value=SERVER_STATUS,
        ),
    ):
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    return entry


async def init_integration_empty_response(hass) -> MockConfigEntry:
    """Set up the Nightscout integration in Home Assistant."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_URL: "https://some.url:1234"},
    )
    with (
        patch(
            "homeassistant.components.nightscout.NightscoutAPI.get_sgvs",
            return_value=[],
        ),
        patch(
            "homeassistant.components.nightscout.NightscoutAPI.get_server_status",
            return_value=SERVER_STATUS,
        ),
    ):
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    return entry
