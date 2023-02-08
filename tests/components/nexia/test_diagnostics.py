"""Test august diagnostics."""
from homeassistant.core import HomeAssistant

from .util import async_init_integration

from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


async def test_diagnostics(
    hass: HomeAssistant, hass_client: ClientSessionGenerator
) -> None:
    """Test generating diagnostics for a config entry."""
    entry = await async_init_integration(hass)

    diag = await get_diagnostics_for_config_entry(hass, hass_client, entry)
    assert diag == {
        "automations": [
            {
                "_links": {
                    "edit": {
                        "href": (
                            "https://www.mynexia.com/mobile"
                            "/automation_edit_buffers?automation_id=3467876"
                        ),
                        "method": "POST",
                    },
                    "filter_events": {
                        "href": (
                            "https://www.mynexia.com/mobile/houses/123456/events"
                            "/collection?sys_guid=472ae0d2-5d7c-4a1c-9e47-4d9035fdace5"
                        )
                    },
                    "nexia:history": {
                        "href": (
                            "https://www.mynexia.com/mobile/houses/123456/events"
                            "?automation_id=3467876"
                        )
                    },
                    "self": {
                        "href": "https://www.mynexia.com/mobile/automations/3467876"
                    },
                },
                "description": (
                    "When IFTTT activates the automation Upstairs "
                    "West Wing will permanently hold the heat to "
                    "62.0 and cool to 83.0 AND Downstairs East "
                    "Wing will permanently hold the heat to 62.0 "
                    "and cool to 83.0 AND Downstairs West Wing "
                    "will permanently hold the heat to 62.0 and "
                    "cool to 83.0 AND Activate the mode named "
                    "'Away 12' AND Master Suite will permanently "
                    "hold the heat to 62.0 and cool to 83.0"
                ),
                "enabled": True,
                "icon": [
                    {"modifiers": [], "name": "gears"},
                    {"modifiers": [], "name": "climate"},
                    {"modifiers": [], "name": "climate"},
                    {"modifiers": [], "name": "climate"},
                    {"modifiers": [], "name": "plane"},
                    {"modifiers": [], "name": "climate"},
                ],
                "id": 3467876,
                "name": "Away for 12 Hours",
                "settings": [],
                "triggers": [],
            },
            {
                "_links": {
                    "edit": {
                        "href": (
                            "https://www.mynexia.com/mobile"
                            "/automation_edit_buffers?automation_id=3467870"
                        ),
                        "method": "POST",
                    },
                    "filter_events": {
                        "href": (
                            "https://www.mynexia.com/mobile/houses/123456/events"
                            "/collection?sys_guid=f63ee20c-3146-49a1-87c5-47429a063d15"
                        )
                    },
                    "nexia:history": {
                        "href": (
                            "https://www.mynexia.com/mobile/houses/123456"
                            "/events?automation_id=3467870"
                        )
                    },
                    "self": {
                        "href": "https://www.mynexia.com/mobile/automations/3467870"
                    },
                },
                "description": (
                    "When IFTTT activates the automation Upstairs "
                    "West Wing will permanently hold the heat to "
                    "60.0 and cool to 85.0 AND Downstairs East "
                    "Wing will permanently hold the heat to 60.0 "
                    "and cool to 85.0 AND Downstairs West Wing "
                    "will permanently hold the heat to 60.0 and "
                    "cool to 85.0 AND Activate the mode named "
                    "'Away 24' AND Master Suite will permanently "
                    "hold the heat to 60.0 and cool to 85.0"
                ),
                "enabled": True,
                "icon": [
                    {"modifiers": [], "name": "gears"},
                    {"modifiers": [], "name": "climate"},
                    {"modifiers": [], "name": "climate"},
                    {"modifiers": [], "name": "climate"},
                    {"modifiers": [], "name": "plane"},
                    {"modifiers": [], "name": "climate"},
                ],
                "id": 3467870,
                "name": "Away For 24 Hours",
                "settings": [],
                "triggers": [],
            },
            {
                "_links": {
                    "edit": {
                        "href": (
                            "https://www.mynexia.com/mobile"
                            "/automation_edit_buffers?automation_id=3452469"
                        ),
                        "method": "POST",
                    },
                    "filter_events": {
                        "href": (
                            "https://www.mynexia.com/mobile/houses/123456/events"
                            "/collection?sys_guid=e5c59b93-efca-4937-9499-3f4c896ab17c"
                        ),
                    },
                    "nexia:history": {
                        "href": (
                            "https://www.mynexia.com/mobile/houses/123456"
                            "/events?automation_id=3452469"
                        )
                    },
                    "self": {
                        "href": "https://www.mynexia.com/mobile/automations/3452469"
                    },
                },
                "description": (
                    "When IFTTT activates the automation Upstairs "
                    "West Wing will permanently hold the heat to "
                    "63.0 and cool to 80.0 AND Downstairs East "
                    "Wing will permanently hold the heat to 63.0 "
                    "and cool to 79.0 AND Downstairs West Wing "
                    "will permanently hold the heat to 63.0 and "
                    "cool to 79.0 AND Upstairs West Wing will "
                    "permanently hold the heat to 63.0 and cool "
                    "to 81.0 AND Upstairs West Wing will change "
                    "Fan Mode to Auto AND Downstairs East Wing "
                    "will change Fan Mode to Auto AND Downstairs "
                    "West Wing will change Fan Mode to Auto AND "
                    "Activate the mode named 'Away Short' AND "
                    "Master Suite will permanently hold the heat "
                    "to 63.0 and cool to 79.0 AND Master Suite "
                    "will change Fan Mode to Auto"
                ),
                "enabled": False,
                "icon": [
                    {"modifiers": [], "name": "gears"},
                    {"modifiers": [], "name": "climate"},
                    {"modifiers": [], "name": "climate"},
                    {"modifiers": [], "name": "climate"},
                    {"modifiers": [], "name": "climate"},
                    {"modifiers": [], "name": "settings"},
                    {"modifiers": [], "name": "settings"},
                    {"modifiers": [], "name": "settings"},
                    {"modifiers": [], "name": "key"},
                    {"modifiers": [], "name": "climate"},
                    {"modifiers": [], "name": "settings"},
                ],
                "id": 3452469,
                "name": "Away Short",
                "settings": [],
                "triggers": [],
            },
            {
                "_links": {
                    "edit": {
                        "href": (
                            "https://www.mynexia.com/mobile"
                            "/automation_edit_buffers?automation_id=3452472"
                        ),
                        "method": "POST",
                    },
                    "filter_events": {
                        "href": (
                            "https://www.mynexia.com/mobile/houses/123456/events"
                            "/collection?sys_guid=861b9fec-d259-4492-a798-5712251666c4"
                        ),
                    },
                    "nexia:history": {
                        "href": (
                            "https://www.mynexia.com/mobile/houses/123456"
                            "/events?automation_id=3452472"
                        ),
                    },
                    "self": {
                        "href": "https://www.mynexia.com/mobile/automations/3452472"
                    },
                },
                "description": (
                    "When IFTTT activates the automation Upstairs "
                    "West Wing will Run Schedule AND Downstairs "
                    "East Wing will Run Schedule AND Downstairs "
                    "West Wing will Run Schedule AND Activate the "
                    "mode named 'Home' AND Master Suite will Run "
                    "Schedule"
                ),
                "enabled": True,
                "icon": [
                    {"modifiers": [], "name": "gears"},
                    {"modifiers": [], "name": "settings"},
                    {"modifiers": [], "name": "settings"},
                    {"modifiers": [], "name": "settings"},
                    {"modifiers": [], "name": "at_home"},
                    {"modifiers": [], "name": "settings"},
                ],
                "id": 3452472,
                "name": "Home",
                "settings": [],
                "triggers": [],
            },
            {
                "_links": {
                    "edit": {
                        "href": (
                            "https://www.mynexia.com/mobile"
                            "/automation_edit_buffers?automation_id=3454776"
                        ),
                        "method": "POST",
                    },
                    "filter_events": {
                        "href": (
                            "https://www.mynexia.com/mobile/houses/123456/events"
                            "/collection?sys_guid=96c71d37-66aa-4cbb-84ff-a90412fd366a"
                        )
                    },
                    "nexia:history": {
                        "href": (
                            "https://www.mynexia.com/mobile/houses/123456"
                            "/events?automation_id=3454776"
                        )
                    },
                    "self": {
                        "href": "https://www.mynexia.com/mobile/automations/3454776"
                    },
                },
                "description": (
                    "When IFTTT activates the automation Upstairs "
                    "West Wing will permanently hold the heat to "
                    "60.0 and cool to 85.0 AND Downstairs East "
                    "Wing will permanently hold the heat to 60.0 "
                    "and cool to 85.0 AND Downstairs West Wing "
                    "will permanently hold the heat to 60.0 and "
                    "cool to 85.0 AND Upstairs West Wing will "
                    "change Fan Mode to Auto AND Downstairs East "
                    "Wing will change Fan Mode to Auto AND "
                    "Downstairs West Wing will change Fan Mode to "
                    "Auto AND Master Suite will permanently hold "
                    "the heat to 60.0 and cool to 85.0 AND Master "
                    "Suite will change Fan Mode to Auto"
                ),
                "enabled": True,
                "icon": [
                    {"modifiers": [], "name": "gears"},
                    {"modifiers": [], "name": "climate"},
                    {"modifiers": [], "name": "climate"},
                    {"modifiers": [], "name": "climate"},
                    {"modifiers": [], "name": "settings"},
                    {"modifiers": [], "name": "settings"},
                    {"modifiers": [], "name": "settings"},
                    {"modifiers": [], "name": "climate"},
                    {"modifiers": [], "name": "settings"},
                ],
                "id": 3454776,
                "name": "IFTTT Power Spike",
                "settings": [],
                "triggers": [],
            },
            {
                "_links": {
                    "edit": {
                        "href": (
                            "https://www.mynexia.com/mobile"
                            "/automation_edit_buffers?automation_id=3454774"
                        ),
                        "method": "POST",
                    },
                    "filter_events": {
                        "href": (
                            "https://www.mynexia.com/mobile/houses/123456/events"
                            "/collection?sys_guid=880c5287-d92c-4368-8494-e10975e92733"
                        ),
                    },
                    "nexia:history": {
                        "href": (
                            "https://www.mynexia.com/mobile/houses/123456"
                            "/events?automation_id=3454774"
                        )
                    },
                    "self": {
                        "href": "https://www.mynexia.com/mobile/automations/3454774"
                    },
                },
                "description": (
                    "When IFTTT activates the automation Upstairs "
                    "West Wing will Run Schedule AND Downstairs "
                    "East Wing will Run Schedule AND Downstairs "
                    "West Wing will Run Schedule AND Master Suite "
                    "will Run Schedule"
                ),
                "enabled": False,
                "icon": [
                    {"modifiers": [], "name": "gears"},
                    {"modifiers": [], "name": "settings"},
                    {"modifiers": [], "name": "settings"},
                    {"modifiers": [], "name": "settings"},
                    {"modifiers": [], "name": "settings"},
                ],
                "id": 3454774,
                "name": "IFTTT return to schedule",
                "settings": [],
                "triggers": [],
            },
            {
                "_links": {
                    "edit": {
                        "href": (
                            "https://www.mynexia.com/mobile"
                            "/automation_edit_buffers?automation_id=3486078"
                        ),
                        "method": "POST",
                    },
                    "filter_events": {
                        "href": (
                            "https://www.mynexia.com/mobile/houses/123456/events"
                            "/collection?sys_guid=d33c013b-2357-47a9-8c66-d2c3693173b0"
                        )
                    },
                    "nexia:history": {
                        "href": (
                            "https://www.mynexia.com/mobile/houses/123456"
                            "/events?automation_id=3486078"
                        )
                    },
                    "self": {
                        "href": "https://www.mynexia.com/mobile/automations/3486078"
                    },
                },
                "description": (
                    "When IFTTT activates the automation Upstairs "
                    "West Wing will permanently hold the heat to "
                    "55.0 and cool to 90.0 AND Downstairs East "
                    "Wing will permanently hold the heat to 55.0 "
                    "and cool to 90.0 AND Downstairs West Wing "
                    "will permanently hold the heat to 55.0 and "
                    "cool to 90.0 AND Activate the mode named "
                    "'Power Outage'"
                ),
                "enabled": True,
                "icon": [
                    {"modifiers": [], "name": "gears"},
                    {"modifiers": [], "name": "climate"},
                    {"modifiers": [], "name": "climate"},
                    {"modifiers": [], "name": "climate"},
                    {"modifiers": [], "name": "bell"},
                ],
                "id": 3486078,
                "name": "Power Outage",
                "settings": [],
                "triggers": [],
            },
            {
                "_links": {
                    "edit": {
                        "href": (
                            "https://www.mynexia.com/mobile"
                            "/automation_edit_buffers?automation_id=3486091"
                        ),
                        "method": "POST",
                    },
                    "filter_events": {
                        "href": (
                            "https://www.mynexia.com/mobile/houses/123456/events"
                            "/collection?sys_guid=b9141df8-2e5e-4524-b8ef-efcbf48d775a"
                        )
                    },
                    "nexia:history": {
                        "href": (
                            "https://www.mynexia.com/mobile/houses/123456"
                            "/events?automation_id=3486091"
                        )
                    },
                    "self": {
                        "href": "https://www.mynexia.com/mobile/automations/3486091"
                    },
                },
                "description": (
                    "When IFTTT activates the automation Upstairs "
                    "West Wing will Run Schedule AND Downstairs "
                    "East Wing will Run Schedule AND Downstairs "
                    "West Wing will Run Schedule AND Activate the "
                    "mode named 'Home'"
                ),
                "enabled": True,
                "icon": [
                    {"modifiers": [], "name": "gears"},
                    {"modifiers": [], "name": "settings"},
                    {"modifiers": [], "name": "settings"},
                    {"modifiers": [], "name": "settings"},
                    {"modifiers": [], "name": "at_home"},
                ],
                "id": 3486091,
                "name": "Power Restored",
                "settings": [],
                "triggers": [],
            },
        ],
        "devices": [
            {
                "_links": {
                    "filter_events": {
                        "href": (
                            "https://www.mynexia.com/mobile/houses/123456/events"
                            "/collection?sys_guid=cd9a70e8-fd0d-4b58-b071-05a202fd8953"
                        )
                    },
                    "nexia:history": {
                        "href": (
                            "https://www.mynexia.com/mobile/houses/123456"
                            "/events?device_id=2059661"
                        )
                    },
                    "pending_request": {
                        "polling_path": (
                            "https://www.mynexia.com/backstage/announcements"
                            "/be6d8ede5cac02fe8be18c334b04d539c9200fa9230eef63"
                        )
                    },
                    "self": {
                        "href": "https://www.mynexia.com/mobile/xxl_thermostats/2059661"
                    },
                },
                "connected": True,
                "delta": 3,
                "features": [
                    {
                        "items": [
                            {
                                "label": "Model",
                                "type": "label_value",
                                "value": "XL1050",
                            },
                            {"label": "AUID", "type": "label_value", "value": "000000"},
                            {
                                "label": "Firmware Build Number",
                                "type": "label_value",
                                "value": "1581321824",
                            },
                            {
                                "label": "Firmware Build Date",
                                "type": "label_value",
                                "value": "2020-02-10 08:03:44 UTC",
                            },
                            {
                                "label": "Firmware Version",
                                "type": "label_value",
                                "value": "5.9.1",
                            },
                            {
                                "label": "Zoning Enabled",
                                "type": "label_value",
                                "value": "yes",
                            },
                        ],
                        "name": "advanced_info",
                    },
                    {
                        "actions": {},
                        "name": "thermostat",
                        "scale": "f",
                        "setpoint_cool_max": 99,
                        "setpoint_cool_min": 60,
                        "setpoint_delta": 3,
                        "setpoint_heat_max": 90,
                        "setpoint_heat_min": 55,
                        "setpoint_increment": 1.0,
                        "status": "System Idle",
                        "status_icon": None,
                        "temperature": 71,
                    },
                    {
                        "is_connected": True,
                        "name": "connection",
                        "signal_strength": "unknown",
                    },
                    {
                        "members": [
                            {
                                "_links": {
                                    "self": {
                                        "href": (
                                            "https://www.mynexia.com/mobile/xxl_zones/83261002"
                                        )
                                    }
                                },
                                "cooling_setpoint": 79,
                                "current_zone_mode": "AUTO",
                                "features": [
                                    {
                                        "actions": {
                                            "set_cool_setpoint": {
                                                "href": (
                                                    "https://www.mynexia.com/mobile/xxl_zones/83261002/setpoints"
                                                )
                                            },
                                            "set_heat_setpoint": {
                                                "href": (
                                                    "https://www.mynexia.com/mobile/xxl_zones/83261002/setpoints"
                                                )
                                            },
                                        },
                                        "name": "thermostat",
                                        "scale": "f",
                                        "setpoint_cool": 79,
                                        "setpoint_cool_max": 99,
                                        "setpoint_cool_min": 60,
                                        "setpoint_delta": 3,
                                        "setpoint_heat": 63,
                                        "setpoint_heat_max": 90,
                                        "setpoint_heat_min": 55,
                                        "setpoint_increment": 1.0,
                                        "status": "",
                                        "status_icon": None,
                                        "system_status": "System Idle",
                                        "temperature": 71,
                                    },
                                    {
                                        "is_connected": True,
                                        "name": "connection",
                                        "signal_strength": "unknown",
                                    },
                                    {
                                        "actions": {
                                            "update_thermostat_mode": {
                                                "href": (
                                                    "https://www.mynexia.com/mobile"
                                                    "/xxl_zones/83261002/zone_mode"
                                                ),
                                                "method": "POST",
                                            }
                                        },
                                        "display_value": "Auto",
                                        "label": "Zone Mode",
                                        "name": "thermostat_mode",
                                        "options": [
                                            {
                                                "header": True,
                                                "id": "thermostat_mode",
                                                "label": "Zone Mode",
                                                "value": "thermostat_mode",
                                            },
                                            {"label": "Auto", "value": "AUTO"},
                                            {"label": "Cooling", "value": "COOL"},
                                            {"label": "Heating", "value": "HEAT"},
                                            {"label": "Off", "value": "OFF"},
                                        ],
                                        "value": "AUTO",
                                    },
                                    {
                                        "actions": {
                                            "update_thermostat_run_mode": {
                                                "href": (
                                                    "https://www.mynexia.com/mobile"
                                                    "/xxl_zones/83261002/run_mode"
                                                ),
                                                "method": "POST",
                                            }
                                        },
                                        "display_value": "Hold",
                                        "label": "Run Mode",
                                        "name": "thermostat_run_mode",
                                        "options": [
                                            {
                                                "header": True,
                                                "id": "thermostat_run_mode",
                                                "label": "Run Mode",
                                                "value": "thermostat_run_mode",
                                            },
                                            {
                                                "id": "info_text",
                                                "info": True,
                                                "label": (
                                                    "Follow or override the schedule."
                                                ),
                                                "value": "info_text",
                                            },
                                            {
                                                "label": "Permanent Hold",
                                                "value": "permanent_hold",
                                            },
                                            {
                                                "label": "Run Schedule",
                                                "value": "run_schedule",
                                            },
                                        ],
                                        "value": "permanent_hold",
                                    },
                                    {
                                        "actions": {
                                            "enable_scheduling": {
                                                "data": {"value": True},
                                                "href": (
                                                    "https://www.mynexia.com/mobile/xxl_zones"
                                                    "/83261002/scheduling_enabled"
                                                ),
                                                "method": "POST",
                                            },
                                            "get_active_schedule": {
                                                "href": (
                                                    "https://www.mynexia.com/mobile"
                                                    "/thermostat_schedules"
                                                    "/get_active_schedule"
                                                    "?device_identifier"
                                                    "=XxlZone-83261002"
                                                ),
                                                "method": "POST",
                                            },
                                            "get_default_schedule": {
                                                "href": (
                                                    "https://www.mynexia.com/mobile"
                                                    "/thermostat_schedules"
                                                    "/get_default_schedule"
                                                    "?device_identifier"
                                                    "=XxlZone-83261002"
                                                ),
                                                "method": "GET",
                                            },
                                            "set_active_schedule": {
                                                "href": (
                                                    "https://www.mynexia.com/mobile"
                                                    "/thermostat_schedules"
                                                    "/set_active_schedule"
                                                    "?device_identifier"
                                                    "=XxlZone-83261002"
                                                ),
                                                "method": "POST",
                                            },
                                        },
                                        "can_add_remove_periods": True,
                                        "collection_url": (
                                            "https://www.mynexia.com/mobile"
                                            "/schedules"
                                            "?device_identifier=XxlZone-83261002"
                                            "&house_id=123456"
                                        ),
                                        "enabled": True,
                                        "max_period_name_length": 10,
                                        "max_periods_per_day": 4,
                                        "name": "schedule",
                                        "setpoint_increment": 1,
                                    },
                                ],
                                "heating_setpoint": 63,
                                "icon": {
                                    "modifiers": ["temperature-71"],
                                    "name": "thermostat",
                                },
                                "id": 83261002,
                                "name": "Living East",
                                "operating_state": "",
                                "setpoints": {"cool": 79, "heat": 63},
                                "settings": [
                                    {
                                        "_links": {
                                            "self": {
                                                "href": (
                                                    "https://www.mynexia.com/mobile"
                                                    "/xxl_zones/83261002"
                                                    "/preset_selected"
                                                )
                                            }
                                        },
                                        "current_value": 0,
                                        "labels": ["None", "Home", "Away", "Sleep"],
                                        "options": [
                                            {"label": "None", "value": 0},
                                            {"label": "Home", "value": 1},
                                            {"label": "Away", "value": 2},
                                            {"label": "Sleep", "value": 3},
                                        ],
                                        "title": "Preset",
                                        "type": "preset_selected",
                                        "values": [0, 1, 2, 3],
                                    },
                                    {
                                        "_links": {
                                            "self": {
                                                "href": (
                                                    "https://www.mynexia.com/mobile"
                                                    "/xxl_zones/83261002/zone_mode"
                                                )
                                            }
                                        },
                                        "current_value": "AUTO",
                                        "labels": ["Auto", "Cooling", "Heating", "Off"],
                                        "options": [
                                            {"label": "Auto", "value": "AUTO"},
                                            {"label": "Cooling", "value": "COOL"},
                                            {"label": "Heating", "value": "HEAT"},
                                            {"label": "Off", "value": "OFF"},
                                        ],
                                        "title": "Zone Mode",
                                        "type": "zone_mode",
                                        "values": ["AUTO", "COOL", "HEAT", "OFF"],
                                    },
                                    {
                                        "_links": {
                                            "self": {
                                                "href": (
                                                    "https://www.mynexia.com/mobile"
                                                    "/xxl_zones/83261002/run_mode"
                                                )
                                            }
                                        },
                                        "current_value": "permanent_hold",
                                        "labels": [
                                            "Permanent Hold",
                                            "Run Schedule",
                                        ],
                                        "options": [
                                            {
                                                "label": "Permanent Hold",
                                                "value": "permanent_hold",
                                            },
                                            {
                                                "label": "Run Schedule",
                                                "value": "run_schedule",
                                            },
                                        ],
                                        "title": "Run Mode",
                                        "type": "run_mode",
                                        "values": ["permanent_hold", "run_schedule"],
                                    },
                                    {
                                        "_links": {
                                            "self": {
                                                "href": (
                                                    "https://www.mynexia.com/mobile"
                                                    "/xxl_zones/83261002"
                                                    "/scheduling_enabled"
                                                )
                                            }
                                        },
                                        "current_value": True,
                                        "labels": ["ON", "OFF"],
                                        "options": [
                                            {"label": "ON", "value": True},
                                            {"label": "OFF", "value": False},
                                        ],
                                        "title": "Scheduling",
                                        "type": "scheduling_enabled",
                                        "values": [True, False],
                                    },
                                ],
                                "temperature": 71,
                                "type": "xxl_zone",
                                "zone_status": "",
                            },
                            {
                                "_links": {
                                    "self": {
                                        "href": (
                                            "https://www.mynexia.com/mobile"
                                            "/xxl_zones/83261005"
                                        )
                                    }
                                },
                                "cooling_setpoint": 79,
                                "current_zone_mode": "AUTO",
                                "features": [
                                    {
                                        "actions": {
                                            "set_cool_setpoint": {
                                                "href": (
                                                    "https://www.mynexia.com/mobile"
                                                    "/xxl_zones/83261005/setpoints"
                                                )
                                            },
                                            "set_heat_setpoint": {
                                                "href": (
                                                    "https://www.mynexia.com/mobile"
                                                    "/xxl_zones/83261005/setpoints"
                                                )
                                            },
                                        },
                                        "name": "thermostat",
                                        "scale": "f",
                                        "setpoint_cool": 79,
                                        "setpoint_cool_max": 99,
                                        "setpoint_cool_min": 60,
                                        "setpoint_delta": 3,
                                        "setpoint_heat": 63,
                                        "setpoint_heat_max": 90,
                                        "setpoint_heat_min": 55,
                                        "setpoint_increment": 1.0,
                                        "status": "",
                                        "status_icon": None,
                                        "system_status": "System Idle",
                                        "temperature": 77,
                                    },
                                    {
                                        "is_connected": True,
                                        "name": "connection",
                                        "signal_strength": "unknown",
                                    },
                                    {
                                        "actions": {
                                            "update_thermostat_mode": {
                                                "href": (
                                                    "https://www.mynexia.com/mobile"
                                                    "/xxl_zones/83261005/zone_mode"
                                                ),
                                                "method": "POST",
                                            }
                                        },
                                        "display_value": "Auto",
                                        "label": "Zone Mode",
                                        "name": "thermostat_mode",
                                        "options": [
                                            {
                                                "header": True,
                                                "id": "thermostat_mode",
                                                "label": "Zone Mode",
                                                "value": "thermostat_mode",
                                            },
                                            {"label": "Auto", "value": "AUTO"},
                                            {"label": "Cooling", "value": "COOL"},
                                            {"label": "Heating", "value": "HEAT"},
                                            {"label": "Off", "value": "OFF"},
                                        ],
                                        "value": "AUTO",
                                    },
                                    {
                                        "actions": {
                                            "update_thermostat_run_mode": {
                                                "href": (
                                                    "https://www.mynexia.com/mobile"
                                                    "/xxl_zones/83261005/run_mode"
                                                ),
                                                "method": "POST",
                                            }
                                        },
                                        "display_value": "Hold",
                                        "label": "Run Mode",
                                        "name": "thermostat_run_mode",
                                        "options": [
                                            {
                                                "header": True,
                                                "id": "thermostat_run_mode",
                                                "label": "Run Mode",
                                                "value": "thermostat_run_mode",
                                            },
                                            {
                                                "id": "info_text",
                                                "info": True,
                                                "label": (
                                                    "Follow or override the schedule."
                                                ),
                                                "value": "info_text",
                                            },
                                            {
                                                "label": "Permanent Hold",
                                                "value": "permanent_hold",
                                            },
                                            {
                                                "label": "Run Schedule",
                                                "value": "run_schedule",
                                            },
                                        ],
                                        "value": "permanent_hold",
                                    },
                                    {
                                        "actions": {
                                            "enable_scheduling": {
                                                "data": {"value": True},
                                                "href": (
                                                    "https://www.mynexia.com/mobile"
                                                    "/xxl_zones/83261005"
                                                    "/scheduling_enabled"
                                                ),
                                                "method": "POST",
                                            },
                                            "get_active_schedule": {
                                                "href": (
                                                    "https://www.mynexia.com/mobile"
                                                    "/thermostat_schedules"
                                                    "/get_active_schedule"
                                                    "?device_identifier"
                                                    "=XxlZone-83261005"
                                                ),
                                                "method": "POST",
                                            },
                                            "get_default_schedule": {
                                                "href": (
                                                    "https://www.mynexia.com/mobile"
                                                    "/thermostat_schedules"
                                                    "/get_default_schedule"
                                                    "?device_identifier"
                                                    "=XxlZone-83261005"
                                                ),
                                                "method": "GET",
                                            },
                                            "set_active_schedule": {
                                                "href": (
                                                    "https://www.mynexia.com/mobile"
                                                    "/thermostat_schedules"
                                                    "/set_active_schedule"
                                                    "?device_identifier"
                                                    "=XxlZone-83261005"
                                                ),
                                                "method": "POST",
                                            },
                                        },
                                        "can_add_remove_periods": True,
                                        "collection_url": (
                                            "https://www.mynexia.com/mobile/schedules"
                                            "?device_identifier=XxlZone-83261005"
                                            "&house_id=123456"
                                        ),
                                        "enabled": True,
                                        "max_period_name_length": 10,
                                        "max_periods_per_day": 4,
                                        "name": "schedule",
                                        "setpoint_increment": 1,
                                    },
                                ],
                                "heating_setpoint": 63,
                                "icon": {
                                    "modifiers": ["temperature-77"],
                                    "name": "thermostat",
                                },
                                "id": 83261005,
                                "name": "Kitchen",
                                "operating_state": "",
                                "setpoints": {"cool": 79, "heat": 63},
                                "settings": [
                                    {
                                        "_links": {
                                            "self": {
                                                "href": (
                                                    "https://www.mynexia.com/mobile"
                                                    "/xxl_zones/83261005"
                                                    "/preset_selected"
                                                )
                                            }
                                        },
                                        "current_value": 0,
                                        "labels": ["None", "Home", "Away", "Sleep"],
                                        "options": [
                                            {"label": "None", "value": 0},
                                            {"label": "Home", "value": 1},
                                            {"label": "Away", "value": 2},
                                            {"label": "Sleep", "value": 3},
                                        ],
                                        "title": "Preset",
                                        "type": "preset_selected",
                                        "values": [0, 1, 2, 3],
                                    },
                                    {
                                        "_links": {
                                            "self": {
                                                "href": (
                                                    "https://www.mynexia.com/mobile"
                                                    "/xxl_zones/83261005/zone_mode"
                                                )
                                            }
                                        },
                                        "current_value": "AUTO",
                                        "labels": ["Auto", "Cooling", "Heating", "Off"],
                                        "options": [
                                            {"label": "Auto", "value": "AUTO"},
                                            {"label": "Cooling", "value": "COOL"},
                                            {"label": "Heating", "value": "HEAT"},
                                            {"label": "Off", "value": "OFF"},
                                        ],
                                        "title": "Zone Mode",
                                        "type": "zone_mode",
                                        "values": ["AUTO", "COOL", "HEAT", "OFF"],
                                    },
                                    {
                                        "_links": {
                                            "self": {
                                                "href": (
                                                    "https://www.mynexia.com/mobile"
                                                    "/xxl_zones/83261005/run_mode"
                                                )
                                            }
                                        },
                                        "current_value": "permanent_hold",
                                        "labels": [
                                            "Permanent Hold",
                                            "Run Schedule",
                                        ],
                                        "options": [
                                            {
                                                "label": "Permanent Hold",
                                                "value": "permanent_hold",
                                            },
                                            {
                                                "label": "Run Schedule",
                                                "value": "run_schedule",
                                            },
                                        ],
                                        "title": "Run Mode",
                                        "type": "run_mode",
                                        "values": ["permanent_hold", "run_schedule"],
                                    },
                                    {
                                        "_links": {
                                            "self": {
                                                "href": (
                                                    "https://www.mynexia.com/mobile"
                                                    "/xxl_zones/83261005"
                                                    "/scheduling_enabled"
                                                )
                                            }
                                        },
                                        "current_value": True,
                                        "labels": ["ON", "OFF"],
                                        "options": [
                                            {"label": "ON", "value": True},
                                            {"label": "OFF", "value": False},
                                        ],
                                        "title": "Scheduling",
                                        "type": "scheduling_enabled",
                                        "values": [True, False],
                                    },
                                ],
                                "temperature": 77,
                                "type": "xxl_zone",
                                "zone_status": "",
                            },
                            {
                                "_links": {
                                    "self": {
                                        "href": (
                                            "https://www.mynexia.com/mobile"
                                            "/xxl_zones/83261008"
                                        )
                                    }
                                },
                                "cooling_setpoint": 79,
                                "current_zone_mode": "AUTO",
                                "features": [
                                    {
                                        "actions": {
                                            "set_cool_setpoint": {
                                                "href": (
                                                    "https://www.mynexia.com/mobile"
                                                    "/xxl_zones/83261008/setpoints"
                                                )
                                            },
                                            "set_heat_setpoint": {
                                                "href": (
                                                    "https://www.mynexia.com/mobile"
                                                    "/xxl_zones/83261008/setpoints"
                                                )
                                            },
                                        },
                                        "name": "thermostat",
                                        "scale": "f",
                                        "setpoint_cool": 79,
                                        "setpoint_cool_max": 99,
                                        "setpoint_cool_min": 60,
                                        "setpoint_delta": 3,
                                        "setpoint_heat": 63,
                                        "setpoint_heat_max": 90,
                                        "setpoint_heat_min": 55,
                                        "setpoint_increment": 1.0,
                                        "status": "",
                                        "status_icon": None,
                                        "system_status": "System Idle",
                                        "temperature": 72,
                                    },
                                    {
                                        "is_connected": True,
                                        "name": "connection",
                                        "signal_strength": "unknown",
                                    },
                                    {
                                        "actions": {
                                            "update_thermostat_mode": {
                                                "href": (
                                                    "https://www.mynexia.com/mobile"
                                                    "/xxl_zones/83261008/zone_mode"
                                                ),
                                                "method": "POST",
                                            }
                                        },
                                        "display_value": "Auto",
                                        "label": "Zone Mode",
                                        "name": "thermostat_mode",
                                        "options": [
                                            {
                                                "header": True,
                                                "id": "thermostat_mode",
                                                "label": "Zone Mode",
                                                "value": "thermostat_mode",
                                            },
                                            {"label": "Auto", "value": "AUTO"},
                                            {"label": "Cooling", "value": "COOL"},
                                            {"label": "Heating", "value": "HEAT"},
                                            {"label": "Off", "value": "OFF"},
                                        ],
                                        "value": "AUTO",
                                    },
                                    {
                                        "actions": {
                                            "update_thermostat_run_mode": {
                                                "href": (
                                                    "https://www.mynexia.com/mobile"
                                                    "/xxl_zones/83261008/run_mode"
                                                ),
                                                "method": "POST",
                                            }
                                        },
                                        "display_value": "Hold",
                                        "label": "Run Mode",
                                        "name": "thermostat_run_mode",
                                        "options": [
                                            {
                                                "header": True,
                                                "id": "thermostat_run_mode",
                                                "label": "Run Mode",
                                                "value": "thermostat_run_mode",
                                            },
                                            {
                                                "id": "info_text",
                                                "info": True,
                                                "label": (
                                                    "Follow or override the schedule."
                                                ),
                                                "value": "info_text",
                                            },
                                            {
                                                "label": "Permanent Hold",
                                                "value": "permanent_hold",
                                            },
                                            {
                                                "label": "Run Schedule",
                                                "value": "run_schedule",
                                            },
                                        ],
                                        "value": "permanent_hold",
                                    },
                                    {
                                        "actions": {
                                            "enable_scheduling": {
                                                "data": {"value": True},
                                                "href": (
                                                    "https://www.mynexia.com/mobile"
                                                    "/xxl_zones/83261008"
                                                    "/scheduling_enabled"
                                                ),
                                                "method": "POST",
                                            },
                                            "get_active_schedule": {
                                                "href": (
                                                    "https://www.mynexia.com/mobile"
                                                    "/thermostat_schedules"
                                                    "/get_active_schedule"
                                                    "?device_identifier"
                                                    "=XxlZone-83261008"
                                                ),
                                                "method": "POST",
                                            },
                                            "get_default_schedule": {
                                                "href": (
                                                    "https://www.mynexia.com/mobile"
                                                    "/thermostat_schedules"
                                                    "/get_default_schedule"
                                                    "?device_identifier"
                                                    "=XxlZone-83261008"
                                                ),
                                                "method": "GET",
                                            },
                                            "set_active_schedule": {
                                                "href": (
                                                    "https://www.mynexia.com/mobile"
                                                    "/thermostat_schedules"
                                                    "/set_active_schedule"
                                                    "?device_identifier"
                                                    "=XxlZone-83261008"
                                                ),
                                                "method": "POST",
                                            },
                                        },
                                        "can_add_remove_periods": True,
                                        "collection_url": (
                                            "https://www.mynexia.com/mobile/schedules"
                                            "?device_identifier=XxlZone-83261008"
                                            "&house_id=123456"
                                        ),
                                        "enabled": True,
                                        "max_period_name_length": 10,
                                        "max_periods_per_day": 4,
                                        "name": "schedule",
                                        "setpoint_increment": 1,
                                    },
                                ],
                                "heating_setpoint": 63,
                                "icon": {
                                    "modifiers": ["temperature-72"],
                                    "name": "thermostat",
                                },
                                "id": 83261008,
                                "name": "Down Bedroom",
                                "operating_state": "",
                                "setpoints": {"cool": 79, "heat": 63},
                                "settings": [
                                    {
                                        "_links": {
                                            "self": {
                                                "href": (
                                                    "https://www.mynexia.com/mobile"
                                                    "/xxl_zones/83261008"
                                                    "/preset_selected"
                                                )
                                            }
                                        },
                                        "current_value": 0,
                                        "labels": ["None", "Home", "Away", "Sleep"],
                                        "options": [
                                            {"label": "None", "value": 0},
                                            {"label": "Home", "value": 1},
                                            {"label": "Away", "value": 2},
                                            {"label": "Sleep", "value": 3},
                                        ],
                                        "title": "Preset",
                                        "type": "preset_selected",
                                        "values": [0, 1, 2, 3],
                                    },
                                    {
                                        "_links": {
                                            "self": {
                                                "href": (
                                                    "https://www.mynexia.com/mobile"
                                                    "/xxl_zones/83261008/zone_mode"
                                                )
                                            }
                                        },
                                        "current_value": "AUTO",
                                        "labels": ["Auto", "Cooling", "Heating", "Off"],
                                        "options": [
                                            {"label": "Auto", "value": "AUTO"},
                                            {"label": "Cooling", "value": "COOL"},
                                            {"label": "Heating", "value": "HEAT"},
                                            {"label": "Off", "value": "OFF"},
                                        ],
                                        "title": "Zone Mode",
                                        "type": "zone_mode",
                                        "values": ["AUTO", "COOL", "HEAT", "OFF"],
                                    },
                                    {
                                        "_links": {
                                            "self": {
                                                "href": (
                                                    "https://www.mynexia.com/mobile"
                                                    "/xxl_zones/83261008/run_mode"
                                                )
                                            }
                                        },
                                        "current_value": "permanent_hold",
                                        "labels": [
                                            "Permanent Hold",
                                            "Run Schedule",
                                        ],
                                        "options": [
                                            {
                                                "label": "Permanent Hold",
                                                "value": "permanent_hold",
                                            },
                                            {
                                                "label": "Run Schedule",
                                                "value": "run_schedule",
                                            },
                                        ],
                                        "title": "Run Mode",
                                        "type": "run_mode",
                                        "values": ["permanent_hold", "run_schedule"],
                                    },
                                    {
                                        "_links": {
                                            "self": {
                                                "href": (
                                                    "https://www.mynexia.com/mobile"
                                                    "/xxl_zones/83261008"
                                                    "/scheduling_enabled"
                                                )
                                            }
                                        },
                                        "current_value": True,
                                        "labels": ["ON", "OFF"],
                                        "options": [
                                            {"label": "ON", "value": True},
                                            {"label": "OFF", "value": False},
                                        ],
                                        "title": "Scheduling",
                                        "type": "scheduling_enabled",
                                        "values": [True, False],
                                    },
                                ],
                                "temperature": 72,
                                "type": "xxl_zone",
                                "zone_status": "",
                            },
                            {
                                "_links": {
                                    "self": {
                                        "href": (
                                            "https://www.mynexia.com/mobile"
                                            "/xxl_zones/83261011"
                                        )
                                    }
                                },
                                "cooling_setpoint": 79,
                                "current_zone_mode": "AUTO",
                                "features": [
                                    {
                                        "actions": {
                                            "set_cool_setpoint": {
                                                "href": (
                                                    "https://www.mynexia.com/mobile"
                                                    "/xxl_zones/83261011/setpoints"
                                                )
                                            },
                                            "set_heat_setpoint": {
                                                "href": (
                                                    "https://www.mynexia.com/mobile"
                                                    "/xxl_zones/83261011/setpoints"
                                                )
                                            },
                                        },
                                        "name": "thermostat",
                                        "scale": "f",
                                        "setpoint_cool": 79,
                                        "setpoint_cool_max": 99,
                                        "setpoint_cool_min": 60,
                                        "setpoint_delta": 3,
                                        "setpoint_heat": 63,
                                        "setpoint_heat_max": 90,
                                        "setpoint_heat_min": 55,
                                        "setpoint_increment": 1.0,
                                        "status": "",
                                        "status_icon": None,
                                        "system_status": "System Idle",
                                        "temperature": 78,
                                    },
                                    {
                                        "is_connected": True,
                                        "name": "connection",
                                        "signal_strength": "unknown",
                                    },
                                    {
                                        "actions": {
                                            "update_thermostat_mode": {
                                                "href": (
                                                    "https://www.mynexia.com/mobile"
                                                    "/xxl_zones/83261011/zone_mode"
                                                ),
                                                "method": "POST",
                                            }
                                        },
                                        "display_value": "Auto",
                                        "label": "Zone Mode",
                                        "name": "thermostat_mode",
                                        "options": [
                                            {
                                                "header": True,
                                                "id": "thermostat_mode",
                                                "label": "Zone Mode",
                                                "value": "thermostat_mode",
                                            },
                                            {"label": "Auto", "value": "AUTO"},
                                            {"label": "Cooling", "value": "COOL"},
                                            {"label": "Heating", "value": "HEAT"},
                                            {"label": "Off", "value": "OFF"},
                                        ],
                                        "value": "AUTO",
                                    },
                                    {
                                        "actions": {
                                            "update_thermostat_run_mode": {
                                                "href": (
                                                    "https://www.mynexia.com/mobile"
                                                    "/xxl_zones/83261011/run_mode"
                                                ),
                                                "method": "POST",
                                            }
                                        },
                                        "display_value": "Hold",
                                        "label": "Run Mode",
                                        "name": "thermostat_run_mode",
                                        "options": [
                                            {
                                                "header": True,
                                                "id": "thermostat_run_mode",
                                                "label": "Run Mode",
                                                "value": "thermostat_run_mode",
                                            },
                                            {
                                                "id": "info_text",
                                                "info": True,
                                                "label": (
                                                    "Follow or override the schedule."
                                                ),
                                                "value": "info_text",
                                            },
                                            {
                                                "label": "Permanent Hold",
                                                "value": "permanent_hold",
                                            },
                                            {
                                                "label": "Run Schedule",
                                                "value": "run_schedule",
                                            },
                                        ],
                                        "value": "permanent_hold",
                                    },
                                    {
                                        "actions": {
                                            "enable_scheduling": {
                                                "data": {"value": True},
                                                "href": (
                                                    "https://www.mynexia.com/mobile"
                                                    "/xxl_zones/83261011"
                                                    "/scheduling_enabled"
                                                ),
                                                "method": "POST",
                                            },
                                            "get_active_schedule": {
                                                "href": (
                                                    "https://www.mynexia.com/mobile"
                                                    "/thermostat_schedules"
                                                    "/get_active_schedule"
                                                    "?device_identifier"
                                                    "=XxlZone-83261011"
                                                ),
                                                "method": "POST",
                                            },
                                            "get_default_schedule": {
                                                "href": (
                                                    "https://www.mynexia.com/mobile"
                                                    "/thermostat_schedules"
                                                    "/get_default_schedule"
                                                    "?device_identifier"
                                                    "=XxlZone-83261011"
                                                ),
                                                "method": "GET",
                                            },
                                            "set_active_schedule": {
                                                "href": (
                                                    "https://www.mynexia.com/mobile"
                                                    "/thermostat_schedules"
                                                    "/set_active_schedule"
                                                    "?device_identifier"
                                                    "=XxlZone-83261011"
                                                ),
                                                "method": "POST",
                                            },
                                        },
                                        "can_add_remove_periods": True,
                                        "collection_url": (
                                            "https://www.mynexia.com/mobile"
                                            "/schedules"
                                            "?device_identifier"
                                            "=XxlZone-83261011"
                                            "&house_id=123456"
                                        ),
                                        "enabled": True,
                                        "max_period_name_length": 10,
                                        "max_periods_per_day": 4,
                                        "name": "schedule",
                                        "setpoint_increment": 1,
                                    },
                                ],
                                "heating_setpoint": 63,
                                "icon": {
                                    "modifiers": ["temperature-78"],
                                    "name": "thermostat",
                                },
                                "id": 83261011,
                                "name": "Tech Room",
                                "operating_state": "",
                                "setpoints": {"cool": 79, "heat": 63},
                                "settings": [
                                    {
                                        "_links": {
                                            "self": {
                                                "href": (
                                                    "https://www.mynexia.com/mobile"
                                                    "/xxl_zones/83261011"
                                                    "/preset_selected"
                                                )
                                            }
                                        },
                                        "current_value": 0,
                                        "labels": ["None", "Home", "Away", "Sleep"],
                                        "options": [
                                            {"label": "None", "value": 0},
                                            {"label": "Home", "value": 1},
                                            {"label": "Away", "value": 2},
                                            {"label": "Sleep", "value": 3},
                                        ],
                                        "title": "Preset",
                                        "type": "preset_selected",
                                        "values": [0, 1, 2, 3],
                                    },
                                    {
                                        "_links": {
                                            "self": {
                                                "href": (
                                                    "https://www.mynexia.com/mobile"
                                                    "/xxl_zones/83261011/zone_mode"
                                                )
                                            }
                                        },
                                        "current_value": "AUTO",
                                        "labels": ["Auto", "Cooling", "Heating", "Off"],
                                        "options": [
                                            {"label": "Auto", "value": "AUTO"},
                                            {"label": "Cooling", "value": "COOL"},
                                            {"label": "Heating", "value": "HEAT"},
                                            {"label": "Off", "value": "OFF"},
                                        ],
                                        "title": "Zone Mode",
                                        "type": "zone_mode",
                                        "values": ["AUTO", "COOL", "HEAT", "OFF"],
                                    },
                                    {
                                        "_links": {
                                            "self": {
                                                "href": (
                                                    "https://www.mynexia.com/mobile"
                                                    "/xxl_zones/83261011/run_mode"
                                                )
                                            }
                                        },
                                        "current_value": "permanent_hold",
                                        "labels": [
                                            "Permanent Hold",
                                            "Run Schedule",
                                        ],
                                        "options": [
                                            {
                                                "label": "Permanent Hold",
                                                "value": "permanent_hold",
                                            },
                                            {
                                                "label": "Run Schedule",
                                                "value": "run_schedule",
                                            },
                                        ],
                                        "title": "Run Mode",
                                        "type": "run_mode",
                                        "values": ["permanent_hold", "run_schedule"],
                                    },
                                    {
                                        "_links": {
                                            "self": {
                                                "href": (
                                                    "https://www.mynexia.com/mobile"
                                                    "/xxl_zones/83261011"
                                                    "/scheduling_enabled"
                                                )
                                            }
                                        },
                                        "current_value": True,
                                        "labels": ["ON", "OFF"],
                                        "options": [
                                            {"label": "ON", "value": True},
                                            {"label": "OFF", "value": False},
                                        ],
                                        "title": "Scheduling",
                                        "type": "scheduling_enabled",
                                        "values": [True, False],
                                    },
                                ],
                                "temperature": 78,
                                "type": "xxl_zone",
                                "zone_status": "",
                            },
                        ],
                        "name": "group",
                    },
                    {
                        "actions": {
                            "update_thermostat_fan_mode": {
                                "href": (
                                    "https://www.mynexia.com/mobile"
                                    "/xxl_thermostats/2059661/fan_mode"
                                ),
                                "method": "POST",
                            }
                        },
                        "display_value": "Auto",
                        "label": "Fan Mode",
                        "name": "thermostat_fan_mode",
                        "options": [
                            {
                                "header": True,
                                "id": "thermostat_fan_mode",
                                "label": "Fan Mode",
                                "value": "thermostat_fan_mode",
                            },
                            {"label": "Auto", "value": "auto"},
                            {"label": "On", "value": "on"},
                            {"label": "Circulate", "value": "circulate"},
                        ],
                        "status_icon": {"modifiers": [], "name": "thermostat_fan_off"},
                        "value": "auto",
                    },
                    {"compressor_speed": 0.0, "name": "thermostat_compressor_speed"},
                    {
                        "actions": {
                            "get_monthly_runtime_history": {
                                "href": (
                                    "https://www.mynexia.com/mobile"
                                    "/runtime_history/2059661?report_type=monthly"
                                ),
                                "method": "GET",
                            },
                            "get_runtime_history": {
                                "href": (
                                    "https://www.mynexia.com/mobile"
                                    "/runtime_history/2059661?report_type=daily"
                                ),
                                "method": "GET",
                            },
                        },
                        "name": "runtime_history",
                    },
                ],
                "has_indoor_humidity": True,
                "has_outdoor_temperature": True,
                "icon": [
                    {"modifiers": ["temperature-71"], "name": "thermostat"},
                    {"modifiers": ["temperature-77"], "name": "thermostat"},
                    {"modifiers": ["temperature-72"], "name": "thermostat"},
                    {"modifiers": ["temperature-78"], "name": "thermostat"},
                ],
                "id": 2059661,
                "indoor_humidity": "36",
                "last_updated_at": "2020-03-11T15:15:53.000-05:00",
                "name": "Downstairs East Wing",
                "name_editable": True,
                "outdoor_temperature": "88",
                "settings": [
                    {
                        "_links": {
                            "self": {
                                "href": (
                                    "https://www.mynexia.com/mobile"
                                    "/xxl_thermostats/2059661/fan_mode"
                                )
                            }
                        },
                        "current_value": "auto",
                        "labels": ["Auto", "On", "Circulate"],
                        "options": [
                            {"label": "Auto", "value": "auto"},
                            {"label": "On", "value": "on"},
                            {"label": "Circulate", "value": "circulate"},
                        ],
                        "title": "Fan Mode",
                        "type": "fan_mode",
                        "values": ["auto", "on", "circulate"],
                    },
                    {
                        "_links": {
                            "self": {
                                "href": (
                                    "https://www.mynexia.com/mobile"
                                    "/xxl_thermostats/2059661/fan_speed"
                                )
                            }
                        },
                        "current_value": 0.35,
                        "labels": [
                            "35%",
                            "40%",
                            "45%",
                            "50%",
                            "55%",
                            "60%",
                            "65%",
                            "70%",
                            "75%",
                            "80%",
                            "85%",
                            "90%",
                            "95%",
                            "100%",
                        ],
                        "options": [
                            {"label": "35%", "value": 0.35},
                            {"label": "40%", "value": 0.4},
                            {"label": "45%", "value": 0.45},
                            {"label": "50%", "value": 0.5},
                            {"label": "55%", "value": 0.55},
                            {"label": "60%", "value": 0.6},
                            {"label": "65%", "value": 0.65},
                            {"label": "70%", "value": 0.7},
                            {"label": "75%", "value": 0.75},
                            {"label": "80%", "value": 0.8},
                            {"label": "85%", "value": 0.85},
                            {"label": "90%", "value": 0.9},
                            {"label": "95%", "value": 0.95},
                            {"label": "100%", "value": 1.0},
                        ],
                        "title": "Fan Speed",
                        "type": "fan_speed",
                        "values": [
                            0.35,
                            0.4,
                            0.45,
                            0.5,
                            0.55,
                            0.6,
                            0.65,
                            0.7,
                            0.75,
                            0.8,
                            0.85,
                            0.9,
                            0.95,
                            1.0,
                        ],
                    },
                    {
                        "_links": {
                            "self": {
                                "href": (
                                    "https://www.mynexia.com/mobile"
                                    "/xxl_thermostats/2059661"
                                    "/fan_circulation_time"
                                )
                            }
                        },
                        "current_value": 30,
                        "labels": [
                            "10 minutes",
                            "15 minutes",
                            "20 minutes",
                            "25 minutes",
                            "30 minutes",
                            "35 minutes",
                            "40 minutes",
                            "45 minutes",
                            "50 minutes",
                            "55 minutes",
                        ],
                        "options": [
                            {"label": "10 minutes", "value": 10},
                            {"label": "15 minutes", "value": 15},
                            {"label": "20 minutes", "value": 20},
                            {"label": "25 minutes", "value": 25},
                            {"label": "30 minutes", "value": 30},
                            {"label": "35 minutes", "value": 35},
                            {"label": "40 minutes", "value": 40},
                            {"label": "45 minutes", "value": 45},
                            {"label": "50 minutes", "value": 50},
                            {"label": "55 minutes", "value": 55},
                        ],
                        "title": "Fan Circulation Time",
                        "type": "fan_circulation_time",
                        "values": [10, 15, 20, 25, 30, 35, 40, 45, 50, 55],
                    },
                    {
                        "_links": {
                            "self": {
                                "href": (
                                    "https://www.mynexia.com/mobile"
                                    "/xxl_thermostats/2059661/air_cleaner_mode"
                                )
                            }
                        },
                        "current_value": "auto",
                        "labels": ["Auto", "Quick", "Allergy"],
                        "options": [
                            {"label": "Auto", "value": "auto"},
                            {"label": "Quick", "value": "quick"},
                            {"label": "Allergy", "value": "allergy"},
                        ],
                        "title": "Air Cleaner Mode",
                        "type": "air_cleaner_mode",
                        "values": ["auto", "quick", "allergy"],
                    },
                    {
                        "_links": {
                            "self": {
                                "href": (
                                    "https://www.mynexia.com/mobile"
                                    "/xxl_thermostats/2059661/dehumidify"
                                )
                            }
                        },
                        "current_value": 0.5,
                        "labels": ["35%", "40%", "45%", "50%", "55%", "60%", "65%"],
                        "options": [
                            {"label": "35%", "value": 0.35},
                            {"label": "40%", "value": 0.4},
                            {"label": "45%", "value": 0.45},
                            {"label": "50%", "value": 0.5},
                            {"label": "55%", "value": 0.55},
                            {"label": "60%", "value": 0.6},
                            {"label": "65%", "value": 0.65},
                        ],
                        "title": "Cooling Dehumidify Set Point",
                        "type": "dehumidify",
                        "values": [0.35, 0.4, 0.45, 0.5, 0.55, 0.6, 0.65],
                    },
                    {
                        "_links": {
                            "self": {
                                "href": (
                                    "https://www.mynexia.com/mobile"
                                    "/xxl_thermostats/2059661/scale"
                                )
                            }
                        },
                        "current_value": "f",
                        "labels": ["F", "C"],
                        "options": [
                            {"label": "F", "value": "f"},
                            {"label": "C", "value": "c"},
                        ],
                        "title": "Temperature Scale",
                        "type": "scale",
                        "values": ["f", "c"],
                    },
                ],
                "status_secondary": None,
                "status_tertiary": None,
                "system_status": "System Idle",
                "type": "xxl_thermostat",
                "zones": [
                    {
                        "_links": {
                            "self": {
                                "href": (
                                    "https://www.mynexia.com/mobile/xxl_zones/83261002"
                                )
                            }
                        },
                        "cooling_setpoint": 79,
                        "current_zone_mode": "AUTO",
                        "features": [
                            {
                                "actions": {
                                    "set_cool_setpoint": {
                                        "href": (
                                            "https://www.mynexia.com/mobile"
                                            "/xxl_zones/83261002/setpoints"
                                        )
                                    },
                                    "set_heat_setpoint": {
                                        "href": (
                                            "https://www.mynexia.com/mobile"
                                            "/xxl_zones/83261002/setpoints"
                                        )
                                    },
                                },
                                "name": "thermostat",
                                "scale": "f",
                                "setpoint_cool": 79,
                                "setpoint_cool_max": 99,
                                "setpoint_cool_min": 60,
                                "setpoint_delta": 3,
                                "setpoint_heat": 63,
                                "setpoint_heat_max": 90,
                                "setpoint_heat_min": 55,
                                "setpoint_increment": 1.0,
                                "status": "",
                                "status_icon": None,
                                "system_status": "System Idle",
                                "temperature": 71,
                            },
                            {
                                "is_connected": True,
                                "name": "connection",
                                "signal_strength": "unknown",
                            },
                            {
                                "actions": {
                                    "update_thermostat_mode": {
                                        "href": (
                                            "https://www.mynexia.com/mobile"
                                            "/xxl_zones/83261002/zone_mode"
                                        ),
                                        "method": "POST",
                                    }
                                },
                                "display_value": "Auto",
                                "label": "Zone Mode",
                                "name": "thermostat_mode",
                                "options": [
                                    {
                                        "header": True,
                                        "id": "thermostat_mode",
                                        "label": "Zone Mode",
                                        "value": "thermostat_mode",
                                    },
                                    {"label": "Auto", "value": "AUTO"},
                                    {"label": "Cooling", "value": "COOL"},
                                    {"label": "Heating", "value": "HEAT"},
                                    {"label": "Off", "value": "OFF"},
                                ],
                                "value": "AUTO",
                            },
                            {
                                "actions": {
                                    "update_thermostat_run_mode": {
                                        "href": (
                                            "https://www.mynexia.com/mobile"
                                            "/xxl_zones/83261002/run_mode"
                                        ),
                                        "method": "POST",
                                    }
                                },
                                "display_value": "Hold",
                                "label": "Run Mode",
                                "name": "thermostat_run_mode",
                                "options": [
                                    {
                                        "header": True,
                                        "id": "thermostat_run_mode",
                                        "label": "Run Mode",
                                        "value": "thermostat_run_mode",
                                    },
                                    {
                                        "id": "info_text",
                                        "info": True,
                                        "label": "Follow or override the schedule.",
                                        "value": "info_text",
                                    },
                                    {
                                        "label": "Permanent Hold",
                                        "value": "permanent_hold",
                                    },
                                    {"label": "Run Schedule", "value": "run_schedule"},
                                ],
                                "value": "permanent_hold",
                            },
                            {
                                "actions": {
                                    "enable_scheduling": {
                                        "data": {"value": True},
                                        "href": (
                                            "https://www.mynexia.com/mobile"
                                            "/xxl_zones/83261002/scheduling_enabled"
                                        ),
                                        "method": "POST",
                                    },
                                    "get_active_schedule": {
                                        "href": (
                                            "https://www.mynexia.com/mobile"
                                            "/thermostat_schedules/get_active_schedule"
                                            "?device_identifier=XxlZone-83261002"
                                        ),
                                        "method": "POST",
                                    },
                                    "get_default_schedule": {
                                        "href": (
                                            "https://www.mynexia.com/mobile"
                                            "/thermostat_schedules/get_default_schedule"
                                            "?device_identifier=XxlZone-83261002"
                                        ),
                                        "method": "GET",
                                    },
                                    "set_active_schedule": {
                                        "href": (
                                            "https://www.mynexia.com/mobile"
                                            "/thermostat_schedules"
                                            "/set_active_schedule"
                                            "?device_identifier=XxlZone-83261002"
                                        ),
                                        "method": "POST",
                                    },
                                },
                                "can_add_remove_periods": True,
                                "collection_url": (
                                    "https://www.mynexia.com/mobile/schedules"
                                    "?device_identifier=XxlZone-83261002"
                                    "&house_id=123456"
                                ),
                                "enabled": True,
                                "max_period_name_length": 10,
                                "max_periods_per_day": 4,
                                "name": "schedule",
                                "setpoint_increment": 1,
                            },
                        ],
                        "heating_setpoint": 63,
                        "icon": {"modifiers": ["temperature-71"], "name": "thermostat"},
                        "id": 83261002,
                        "name": "Living East",
                        "operating_state": "",
                        "setpoints": {"cool": 79, "heat": 63},
                        "settings": [
                            {
                                "_links": {
                                    "self": {
                                        "href": (
                                            "https://www.mynexia.com/mobile/xxl_zones"
                                            "/83261002/preset_selected"
                                        )
                                    }
                                },
                                "current_value": 0,
                                "labels": ["None", "Home", "Away", "Sleep"],
                                "options": [
                                    {"label": "None", "value": 0},
                                    {"label": "Home", "value": 1},
                                    {"label": "Away", "value": 2},
                                    {"label": "Sleep", "value": 3},
                                ],
                                "title": "Preset",
                                "type": "preset_selected",
                                "values": [0, 1, 2, 3],
                            },
                            {
                                "_links": {
                                    "self": {
                                        "href": (
                                            "https://www.mynexia.com/mobile"
                                            "/xxl_zones/83261002/zone_mode"
                                        )
                                    }
                                },
                                "current_value": "AUTO",
                                "labels": ["Auto", "Cooling", "Heating", "Off"],
                                "options": [
                                    {"label": "Auto", "value": "AUTO"},
                                    {"label": "Cooling", "value": "COOL"},
                                    {"label": "Heating", "value": "HEAT"},
                                    {"label": "Off", "value": "OFF"},
                                ],
                                "title": "Zone Mode",
                                "type": "zone_mode",
                                "values": ["AUTO", "COOL", "HEAT", "OFF"],
                            },
                            {
                                "_links": {
                                    "self": {
                                        "href": (
                                            "https://www.mynexia.com/mobile"
                                            "/xxl_zones/83261002/run_mode"
                                        )
                                    }
                                },
                                "current_value": "permanent_hold",
                                "labels": ["Permanent Hold", "Run Schedule"],
                                "options": [
                                    {
                                        "label": "Permanent Hold",
                                        "value": "permanent_hold",
                                    },
                                    {"label": "Run Schedule", "value": "run_schedule"},
                                ],
                                "title": "Run Mode",
                                "type": "run_mode",
                                "values": ["permanent_hold", "run_schedule"],
                            },
                            {
                                "_links": {
                                    "self": {
                                        "href": (
                                            "https://www.mynexia.com/mobile"
                                            "/xxl_zones/83261002/scheduling_enabled"
                                        )
                                    }
                                },
                                "current_value": True,
                                "labels": ["ON", "OFF"],
                                "options": [
                                    {"label": "ON", "value": True},
                                    {"label": "OFF", "value": False},
                                ],
                                "title": "Scheduling",
                                "type": "scheduling_enabled",
                                "values": [True, False],
                            },
                        ],
                        "temperature": 71,
                        "type": "xxl_zone",
                        "zone_status": "",
                    },
                    {
                        "_links": {
                            "self": {
                                "href": (
                                    "https://www.mynexia.com/mobile/xxl_zones/83261005"
                                )
                            }
                        },
                        "cooling_setpoint": 79,
                        "current_zone_mode": "AUTO",
                        "features": [
                            {
                                "actions": {
                                    "set_cool_setpoint": {
                                        "href": (
                                            "https://www.mynexia.com/mobile"
                                            "/xxl_zones/83261005/setpoints"
                                        )
                                    },
                                    "set_heat_setpoint": {
                                        "href": (
                                            "https://www.mynexia.com/mobile"
                                            "/xxl_zones/83261005/setpoints"
                                        )
                                    },
                                },
                                "name": "thermostat",
                                "scale": "f",
                                "setpoint_cool": 79,
                                "setpoint_cool_max": 99,
                                "setpoint_cool_min": 60,
                                "setpoint_delta": 3,
                                "setpoint_heat": 63,
                                "setpoint_heat_max": 90,
                                "setpoint_heat_min": 55,
                                "setpoint_increment": 1.0,
                                "status": "",
                                "status_icon": None,
                                "system_status": "System Idle",
                                "temperature": 77,
                            },
                            {
                                "is_connected": True,
                                "name": "connection",
                                "signal_strength": "unknown",
                            },
                            {
                                "actions": {
                                    "update_thermostat_mode": {
                                        "href": (
                                            "https://www.mynexia.com/mobile"
                                            "/xxl_zones/83261005/zone_mode"
                                        ),
                                        "method": "POST",
                                    }
                                },
                                "display_value": "Auto",
                                "label": "Zone Mode",
                                "name": "thermostat_mode",
                                "options": [
                                    {
                                        "header": True,
                                        "id": "thermostat_mode",
                                        "label": "Zone Mode",
                                        "value": "thermostat_mode",
                                    },
                                    {"label": "Auto", "value": "AUTO"},
                                    {"label": "Cooling", "value": "COOL"},
                                    {"label": "Heating", "value": "HEAT"},
                                    {"label": "Off", "value": "OFF"},
                                ],
                                "value": "AUTO",
                            },
                            {
                                "actions": {
                                    "update_thermostat_run_mode": {
                                        "href": (
                                            "https://www.mynexia.com/mobile"
                                            "/xxl_zones/83261005/run_mode"
                                        ),
                                        "method": "POST",
                                    }
                                },
                                "display_value": "Hold",
                                "label": "Run Mode",
                                "name": "thermostat_run_mode",
                                "options": [
                                    {
                                        "header": True,
                                        "id": "thermostat_run_mode",
                                        "label": "Run Mode",
                                        "value": "thermostat_run_mode",
                                    },
                                    {
                                        "id": "info_text",
                                        "info": True,
                                        "label": "Follow or override the schedule.",
                                        "value": "info_text",
                                    },
                                    {
                                        "label": "Permanent Hold",
                                        "value": "permanent_hold",
                                    },
                                    {"label": "Run Schedule", "value": "run_schedule"},
                                ],
                                "value": "permanent_hold",
                            },
                            {
                                "actions": {
                                    "enable_scheduling": {
                                        "data": {"value": True},
                                        "href": (
                                            "https://www.mynexia.com/mobile/xxl_zones"
                                            "/83261005/scheduling_enabled"
                                        ),
                                        "method": "POST",
                                    },
                                    "get_active_schedule": {
                                        "href": (
                                            "https://www.mynexia.com/mobile"
                                            "/thermostat_schedules"
                                            "/get_active_schedule"
                                            "?device_identifier=XxlZone-83261005"
                                        ),
                                        "method": "POST",
                                    },
                                    "get_default_schedule": {
                                        "href": (
                                            "https://www.mynexia.com/mobile"
                                            "/thermostat_schedules"
                                            "/get_default_schedule"
                                            "?device_identifier=XxlZone-83261005"
                                        ),
                                        "method": "GET",
                                    },
                                    "set_active_schedule": {
                                        "href": (
                                            "https://www.mynexia.com/mobile"
                                            "/thermostat_schedules"
                                            "/set_active_schedule"
                                            "?device_identifier=XxlZone-83261005"
                                        ),
                                        "method": "POST",
                                    },
                                },
                                "can_add_remove_periods": True,
                                "collection_url": (
                                    "https://www.mynexia.com/mobile/schedules"
                                    "?device_identifier=XxlZone-83261005"
                                    "&house_id=123456"
                                ),
                                "enabled": True,
                                "max_period_name_length": 10,
                                "max_periods_per_day": 4,
                                "name": "schedule",
                                "setpoint_increment": 1,
                            },
                        ],
                        "heating_setpoint": 63,
                        "icon": {"modifiers": ["temperature-77"], "name": "thermostat"},
                        "id": 83261005,
                        "name": "Kitchen",
                        "operating_state": "",
                        "setpoints": {"cool": 79, "heat": 63},
                        "settings": [
                            {
                                "_links": {
                                    "self": {
                                        "href": (
                                            "https://www.mynexia.com/mobile"
                                            "/xxl_zones/83261005/preset_selected"
                                        )
                                    }
                                },
                                "current_value": 0,
                                "labels": ["None", "Home", "Away", "Sleep"],
                                "options": [
                                    {"label": "None", "value": 0},
                                    {"label": "Home", "value": 1},
                                    {"label": "Away", "value": 2},
                                    {"label": "Sleep", "value": 3},
                                ],
                                "title": "Preset",
                                "type": "preset_selected",
                                "values": [0, 1, 2, 3],
                            },
                            {
                                "_links": {
                                    "self": {
                                        "href": (
                                            "https://www.mynexia.com/mobile"
                                            "/xxl_zones/83261005/zone_mode"
                                        )
                                    }
                                },
                                "current_value": "AUTO",
                                "labels": ["Auto", "Cooling", "Heating", "Off"],
                                "options": [
                                    {"label": "Auto", "value": "AUTO"},
                                    {"label": "Cooling", "value": "COOL"},
                                    {"label": "Heating", "value": "HEAT"},
                                    {"label": "Off", "value": "OFF"},
                                ],
                                "title": "Zone Mode",
                                "type": "zone_mode",
                                "values": ["AUTO", "COOL", "HEAT", "OFF"],
                            },
                            {
                                "_links": {
                                    "self": {
                                        "href": (
                                            "https://www.mynexia.com/mobile"
                                            "/xxl_zones/83261005/run_mode"
                                        )
                                    }
                                },
                                "current_value": "permanent_hold",
                                "labels": ["Permanent Hold", "Run Schedule"],
                                "options": [
                                    {
                                        "label": "Permanent Hold",
                                        "value": "permanent_hold",
                                    },
                                    {"label": "Run Schedule", "value": "run_schedule"},
                                ],
                                "title": "Run Mode",
                                "type": "run_mode",
                                "values": ["permanent_hold", "run_schedule"],
                            },
                            {
                                "_links": {
                                    "self": {
                                        "href": (
                                            "https://www.mynexia.com/mobile"
                                            "/xxl_zones/83261005/scheduling_enabled"
                                        )
                                    }
                                },
                                "current_value": True,
                                "labels": ["ON", "OFF"],
                                "options": [
                                    {"label": "ON", "value": True},
                                    {"label": "OFF", "value": False},
                                ],
                                "title": "Scheduling",
                                "type": "scheduling_enabled",
                                "values": [True, False],
                            },
                        ],
                        "temperature": 77,
                        "type": "xxl_zone",
                        "zone_status": "",
                    },
                    {
                        "_links": {
                            "self": {
                                "href": (
                                    "https://www.mynexia.com/mobile/xxl_zones/83261008"
                                )
                            }
                        },
                        "cooling_setpoint": 79,
                        "current_zone_mode": "AUTO",
                        "features": [
                            {
                                "actions": {
                                    "set_cool_setpoint": {
                                        "href": (
                                            "https://www.mynexia.com/mobile"
                                            "/xxl_zones/83261008/setpoints"
                                        )
                                    },
                                    "set_heat_setpoint": {
                                        "href": (
                                            "https://www.mynexia.com/mobile"
                                            "/xxl_zones/83261008/setpoints"
                                        )
                                    },
                                },
                                "name": "thermostat",
                                "scale": "f",
                                "setpoint_cool": 79,
                                "setpoint_cool_max": 99,
                                "setpoint_cool_min": 60,
                                "setpoint_delta": 3,
                                "setpoint_heat": 63,
                                "setpoint_heat_max": 90,
                                "setpoint_heat_min": 55,
                                "setpoint_increment": 1.0,
                                "status": "",
                                "status_icon": None,
                                "system_status": "System Idle",
                                "temperature": 72,
                            },
                            {
                                "is_connected": True,
                                "name": "connection",
                                "signal_strength": "unknown",
                            },
                            {
                                "actions": {
                                    "update_thermostat_mode": {
                                        "href": (
                                            "https://www.mynexia.com/mobile"
                                            "/xxl_zones/83261008/zone_mode"
                                        ),
                                        "method": "POST",
                                    }
                                },
                                "display_value": "Auto",
                                "label": "Zone Mode",
                                "name": "thermostat_mode",
                                "options": [
                                    {
                                        "header": True,
                                        "id": "thermostat_mode",
                                        "label": "Zone Mode",
                                        "value": "thermostat_mode",
                                    },
                                    {"label": "Auto", "value": "AUTO"},
                                    {"label": "Cooling", "value": "COOL"},
                                    {"label": "Heating", "value": "HEAT"},
                                    {"label": "Off", "value": "OFF"},
                                ],
                                "value": "AUTO",
                            },
                            {
                                "actions": {
                                    "update_thermostat_run_mode": {
                                        "href": (
                                            "https://www.mynexia.com/mobile"
                                            "/xxl_zones/83261008/run_mode"
                                        ),
                                        "method": "POST",
                                    }
                                },
                                "display_value": "Hold",
                                "label": "Run Mode",
                                "name": "thermostat_run_mode",
                                "options": [
                                    {
                                        "header": True,
                                        "id": "thermostat_run_mode",
                                        "label": "Run Mode",
                                        "value": "thermostat_run_mode",
                                    },
                                    {
                                        "id": "info_text",
                                        "info": True,
                                        "label": "Follow or override the schedule.",
                                        "value": "info_text",
                                    },
                                    {
                                        "label": "Permanent Hold",
                                        "value": "permanent_hold",
                                    },
                                    {"label": "Run Schedule", "value": "run_schedule"},
                                ],
                                "value": "permanent_hold",
                            },
                            {
                                "actions": {
                                    "enable_scheduling": {
                                        "data": {"value": True},
                                        "href": (
                                            "https://www.mynexia.com/mobile"
                                            "/xxl_zones/83261008/scheduling_enabled"
                                        ),
                                        "method": "POST",
                                    },
                                    "get_active_schedule": {
                                        "href": (
                                            "https://www.mynexia.com/mobile"
                                            "/thermostat_schedules/get_active_schedule"
                                            "?device_identifier=XxlZone-83261008"
                                        ),
                                        "method": "POST",
                                    },
                                    "get_default_schedule": {
                                        "href": (
                                            "https://www.mynexia.com/mobile"
                                            "/thermostat_schedules/get_default_schedule"
                                            "?device_identifier=XxlZone-83261008"
                                        ),
                                        "method": "GET",
                                    },
                                    "set_active_schedule": {
                                        "href": (
                                            "https://www.mynexia.com/mobile"
                                            "/thermostat_schedules/set_active_schedule"
                                            "?device_identifier=XxlZone-83261008"
                                        ),
                                        "method": "POST",
                                    },
                                },
                                "can_add_remove_periods": True,
                                "collection_url": (
                                    "https://www.mynexia.com/mobile/schedules"
                                    "?device_identifier=XxlZone-83261008"
                                    "&house_id=123456"
                                ),
                                "enabled": True,
                                "max_period_name_length": 10,
                                "max_periods_per_day": 4,
                                "name": "schedule",
                                "setpoint_increment": 1,
                            },
                        ],
                        "heating_setpoint": 63,
                        "icon": {"modifiers": ["temperature-72"], "name": "thermostat"},
                        "id": 83261008,
                        "name": "Down Bedroom",
                        "operating_state": "",
                        "setpoints": {"cool": 79, "heat": 63},
                        "settings": [
                            {
                                "_links": {
                                    "self": {
                                        "href": (
                                            "https://www.mynexia.com/mobile/xxl_zones"
                                            "/83261008/preset_selected"
                                        )
                                    }
                                },
                                "current_value": 0,
                                "labels": ["None", "Home", "Away", "Sleep"],
                                "options": [
                                    {"label": "None", "value": 0},
                                    {"label": "Home", "value": 1},
                                    {"label": "Away", "value": 2},
                                    {"label": "Sleep", "value": 3},
                                ],
                                "title": "Preset",
                                "type": "preset_selected",
                                "values": [0, 1, 2, 3],
                            },
                            {
                                "_links": {
                                    "self": {
                                        "href": (
                                            "https://www.mynexia.com/mobile/xxl_zones"
                                            "/83261008/zone_mode"
                                        )
                                    }
                                },
                                "current_value": "AUTO",
                                "labels": ["Auto", "Cooling", "Heating", "Off"],
                                "options": [
                                    {"label": "Auto", "value": "AUTO"},
                                    {"label": "Cooling", "value": "COOL"},
                                    {"label": "Heating", "value": "HEAT"},
                                    {"label": "Off", "value": "OFF"},
                                ],
                                "title": "Zone Mode",
                                "type": "zone_mode",
                                "values": ["AUTO", "COOL", "HEAT", "OFF"],
                            },
                            {
                                "_links": {
                                    "self": {
                                        "href": (
                                            "https://www.mynexia.com/mobile/xxl_zones"
                                            "/83261008/run_mode"
                                        )
                                    }
                                },
                                "current_value": "permanent_hold",
                                "labels": ["Permanent Hold", "Run Schedule"],
                                "options": [
                                    {
                                        "label": "Permanent Hold",
                                        "value": "permanent_hold",
                                    },
                                    {"label": "Run Schedule", "value": "run_schedule"},
                                ],
                                "title": "Run Mode",
                                "type": "run_mode",
                                "values": ["permanent_hold", "run_schedule"],
                            },
                            {
                                "_links": {
                                    "self": {
                                        "href": (
                                            "https://www.mynexia.com/mobile/xxl_zones"
                                            "/83261008/scheduling_enabled"
                                        )
                                    }
                                },
                                "current_value": True,
                                "labels": ["ON", "OFF"],
                                "options": [
                                    {"label": "ON", "value": True},
                                    {"label": "OFF", "value": False},
                                ],
                                "title": "Scheduling",
                                "type": "scheduling_enabled",
                                "values": [True, False],
                            },
                        ],
                        "temperature": 72,
                        "type": "xxl_zone",
                        "zone_status": "",
                    },
                    {
                        "_links": {
                            "self": {
                                "href": (
                                    "https://www.mynexia.com/mobile/xxl_zones/83261011"
                                )
                            }
                        },
                        "cooling_setpoint": 79,
                        "current_zone_mode": "AUTO",
                        "features": [
                            {
                                "actions": {
                                    "set_cool_setpoint": {
                                        "href": (
                                            "https://www.mynexia.com/mobile/xxl_zones"
                                            "/83261011/setpoints"
                                        )
                                    },
                                    "set_heat_setpoint": {
                                        "href": (
                                            "https://www.mynexia.com/mobile/xxl_zones"
                                            "/83261011/setpoints"
                                        )
                                    },
                                },
                                "name": "thermostat",
                                "scale": "f",
                                "setpoint_cool": 79,
                                "setpoint_cool_max": 99,
                                "setpoint_cool_min": 60,
                                "setpoint_delta": 3,
                                "setpoint_heat": 63,
                                "setpoint_heat_max": 90,
                                "setpoint_heat_min": 55,
                                "setpoint_increment": 1.0,
                                "status": "",
                                "status_icon": None,
                                "system_status": "System Idle",
                                "temperature": 78,
                            },
                            {
                                "is_connected": True,
                                "name": "connection",
                                "signal_strength": "unknown",
                            },
                            {
                                "actions": {
                                    "update_thermostat_mode": {
                                        "href": (
                                            "https://www.mynexia.com/mobile/xxl_zones"
                                            "/83261011/zone_mode"
                                        ),
                                        "method": "POST",
                                    }
                                },
                                "display_value": "Auto",
                                "label": "Zone Mode",
                                "name": "thermostat_mode",
                                "options": [
                                    {
                                        "header": True,
                                        "id": "thermostat_mode",
                                        "label": "Zone Mode",
                                        "value": "thermostat_mode",
                                    },
                                    {"label": "Auto", "value": "AUTO"},
                                    {"label": "Cooling", "value": "COOL"},
                                    {"label": "Heating", "value": "HEAT"},
                                    {"label": "Off", "value": "OFF"},
                                ],
                                "value": "AUTO",
                            },
                            {
                                "actions": {
                                    "update_thermostat_run_mode": {
                                        "href": (
                                            "https://www.mynexia.com/mobile/xxl_zones"
                                            "/83261011/run_mode"
                                        ),
                                        "method": "POST",
                                    }
                                },
                                "display_value": "Hold",
                                "label": "Run Mode",
                                "name": "thermostat_run_mode",
                                "options": [
                                    {
                                        "header": True,
                                        "id": "thermostat_run_mode",
                                        "label": "Run Mode",
                                        "value": "thermostat_run_mode",
                                    },
                                    {
                                        "id": "info_text",
                                        "info": True,
                                        "label": "Follow or override the schedule.",
                                        "value": "info_text",
                                    },
                                    {
                                        "label": "Permanent Hold",
                                        "value": "permanent_hold",
                                    },
                                    {"label": "Run Schedule", "value": "run_schedule"},
                                ],
                                "value": "permanent_hold",
                            },
                            {
                                "actions": {
                                    "enable_scheduling": {
                                        "data": {"value": True},
                                        "href": (
                                            "https://www.mynexia.com/mobile/xxl_zones"
                                            "/83261011/scheduling_enabled"
                                        ),
                                        "method": "POST",
                                    },
                                    "get_active_schedule": {
                                        "href": (
                                            "https://www.mynexia.com/mobile"
                                            "/thermostat_schedules/get_active_schedule"
                                            "?device_identifier=XxlZone-83261011"
                                        ),
                                        "method": "POST",
                                    },
                                    "get_default_schedule": {
                                        "href": (
                                            "https://www.mynexia.com/mobile"
                                            "/thermostat_schedules/get_default_schedule"
                                            "?device_identifier=XxlZone-83261011"
                                        ),
                                        "method": "GET",
                                    },
                                    "set_active_schedule": {
                                        "href": (
                                            "https://www.mynexia.com/mobile"
                                            "/thermostat_schedules/set_active_schedule"
                                            "?device_identifier=XxlZone-83261011"
                                        ),
                                        "method": "POST",
                                    },
                                },
                                "can_add_remove_periods": True,
                                "collection_url": (
                                    "https://www.mynexia.com/mobile/schedules"
                                    "?device_identifier=XxlZone-83261011"
                                    "&house_id=123456"
                                ),
                                "enabled": True,
                                "max_period_name_length": 10,
                                "max_periods_per_day": 4,
                                "name": "schedule",
                                "setpoint_increment": 1,
                            },
                        ],
                        "heating_setpoint": 63,
                        "icon": {"modifiers": ["temperature-78"], "name": "thermostat"},
                        "id": 83261011,
                        "name": "Tech Room",
                        "operating_state": "",
                        "setpoints": {"cool": 79, "heat": 63},
                        "settings": [
                            {
                                "_links": {
                                    "self": {
                                        "href": (
                                            "https://www.mynexia.com/mobile/xxl_zones"
                                            "/83261011/preset_selected"
                                        )
                                    }
                                },
                                "current_value": 0,
                                "labels": ["None", "Home", "Away", "Sleep"],
                                "options": [
                                    {"label": "None", "value": 0},
                                    {"label": "Home", "value": 1},
                                    {"label": "Away", "value": 2},
                                    {"label": "Sleep", "value": 3},
                                ],
                                "title": "Preset",
                                "type": "preset_selected",
                                "values": [0, 1, 2, 3],
                            },
                            {
                                "_links": {
                                    "self": {
                                        "href": (
                                            "https://www.mynexia.com/mobile/xxl_zones"
                                            "/83261011/zone_mode"
                                        )
                                    }
                                },
                                "current_value": "AUTO",
                                "labels": ["Auto", "Cooling", "Heating", "Off"],
                                "options": [
                                    {"label": "Auto", "value": "AUTO"},
                                    {"label": "Cooling", "value": "COOL"},
                                    {"label": "Heating", "value": "HEAT"},
                                    {"label": "Off", "value": "OFF"},
                                ],
                                "title": "Zone Mode",
                                "type": "zone_mode",
                                "values": ["AUTO", "COOL", "HEAT", "OFF"],
                            },
                            {
                                "_links": {
                                    "self": {
                                        "href": (
                                            "https://www.mynexia.com/mobile/xxl_zones"
                                            "/83261011/run_mode"
                                        )
                                    }
                                },
                                "current_value": "permanent_hold",
                                "labels": ["Permanent Hold", "Run Schedule"],
                                "options": [
                                    {
                                        "label": "Permanent Hold",
                                        "value": "permanent_hold",
                                    },
                                    {"label": "Run Schedule", "value": "run_schedule"},
                                ],
                                "title": "Run Mode",
                                "type": "run_mode",
                                "values": ["permanent_hold", "run_schedule"],
                            },
                            {
                                "_links": {
                                    "self": {
                                        "href": (
                                            "https://www.mynexia.com/mobile/xxl_zones"
                                            "/83261011/scheduling_enabled"
                                        )
                                    }
                                },
                                "current_value": True,
                                "labels": ["ON", "OFF"],
                                "options": [
                                    {"label": "ON", "value": True},
                                    {"label": "OFF", "value": False},
                                ],
                                "title": "Scheduling",
                                "type": "scheduling_enabled",
                                "values": [True, False],
                            },
                        ],
                        "temperature": 78,
                        "type": "xxl_zone",
                        "zone_status": "",
                    },
                ],
            },
            {
                "_links": {
                    "filter_events": {
                        "href": (
                            "https://www.mynexia.com/mobile/houses/123456/events"
                            "/collection?sys_guid=5aae72a6-1bd0-4d84-9bfd-673e7bc4907c"
                        )
                    },
                    "nexia:history": {
                        "href": (
                            "https://www.mynexia.com/mobile/houses/123456"
                            "/events?device_id=2059676"
                        )
                    },
                    "pending_request": {
                        "polling_path": (
                            "https://www.mynexia.com/backstage/announcements"
                            "/3412f1d96eb0c5edb5466c3c0598af60c06f8443f21e9bcb"
                        )
                    },
                    "self": {
                        "href": "https://www.mynexia.com/mobile/xxl_thermostats/2059676"
                    },
                },
                "connected": True,
                "delta": 3,
                "features": [
                    {
                        "items": [
                            {
                                "label": "Model",
                                "type": "label_value",
                                "value": "XL1050",
                            },
                            {
                                "label": "AUID",
                                "type": "label_value",
                                "value": "02853E08",
                            },
                            {
                                "label": "Firmware Build Number",
                                "type": "label_value",
                                "value": "1581321824",
                            },
                            {
                                "label": "Firmware Build Date",
                                "type": "label_value",
                                "value": "2020-02-10 08:03:44 UTC",
                            },
                            {
                                "label": "Firmware Version",
                                "type": "label_value",
                                "value": "5.9.1",
                            },
                            {
                                "label": "Zoning Enabled",
                                "type": "label_value",
                                "value": "yes",
                            },
                        ],
                        "name": "advanced_info",
                    },
                    {
                        "actions": {},
                        "name": "thermostat",
                        "scale": "f",
                        "setpoint_cool_max": 99,
                        "setpoint_cool_min": 60,
                        "setpoint_delta": 3,
                        "setpoint_heat_max": 90,
                        "setpoint_heat_min": 55,
                        "setpoint_increment": 1.0,
                        "status": "System Idle",
                        "status_icon": None,
                        "temperature": 75,
                    },
                    {
                        "is_connected": True,
                        "name": "connection",
                        "signal_strength": "unknown",
                    },
                    {
                        "members": [
                            {
                                "_links": {
                                    "self": {
                                        "href": (
                                            "https://www.mynexia.com/mobile"
                                            "/xxl_zones/83261015"
                                        )
                                    }
                                },
                                "cooling_setpoint": 79,
                                "current_zone_mode": "AUTO",
                                "features": [
                                    {
                                        "actions": {
                                            "set_cool_setpoint": {
                                                "href": (
                                                    "https://www.mynexia.com/mobile"
                                                    "/xxl_zones/83261015/setpoints"
                                                )
                                            },
                                            "set_heat_setpoint": {
                                                "href": (
                                                    "https://www.mynexia.com/mobile"
                                                    "/xxl_zones/83261015/setpoints"
                                                )
                                            },
                                        },
                                        "name": "thermostat",
                                        "scale": "f",
                                        "setpoint_cool": 79,
                                        "setpoint_cool_max": 99,
                                        "setpoint_cool_min": 60,
                                        "setpoint_delta": 3,
                                        "setpoint_heat": 63,
                                        "setpoint_heat_max": 90,
                                        "setpoint_heat_min": 55,
                                        "setpoint_increment": 1.0,
                                        "status": "",
                                        "status_icon": None,
                                        "system_status": "System Idle",
                                        "temperature": 75,
                                    },
                                    {
                                        "is_connected": True,
                                        "name": "connection",
                                        "signal_strength": "unknown",
                                    },
                                    {
                                        "actions": {
                                            "update_thermostat_mode": {
                                                "href": (
                                                    "https://www.mynexia.com/mobile"
                                                    "/xxl_zones/83261015/zone_mode"
                                                ),
                                                "method": "POST",
                                            }
                                        },
                                        "display_value": "Auto",
                                        "label": "Zone Mode",
                                        "name": "thermostat_mode",
                                        "options": [
                                            {
                                                "header": True,
                                                "id": "thermostat_mode",
                                                "label": "Zone Mode",
                                                "value": "thermostat_mode",
                                            },
                                            {"label": "Auto", "value": "AUTO"},
                                            {"label": "Cooling", "value": "COOL"},
                                            {"label": "Heating", "value": "HEAT"},
                                            {"label": "Off", "value": "OFF"},
                                        ],
                                        "value": "AUTO",
                                    },
                                    {
                                        "actions": {
                                            "update_thermostat_run_mode": {
                                                "href": (
                                                    "https://www.mynexia.com/mobile"
                                                    "/xxl_zones/83261015/run_mode"
                                                ),
                                                "method": "POST",
                                            }
                                        },
                                        "display_value": "Hold",
                                        "label": "Run Mode",
                                        "name": "thermostat_run_mode",
                                        "options": [
                                            {
                                                "header": True,
                                                "id": "thermostat_run_mode",
                                                "label": "Run Mode",
                                                "value": "thermostat_run_mode",
                                            },
                                            {
                                                "id": "info_text",
                                                "info": True,
                                                "label": (
                                                    "Follow or override the schedule."
                                                ),
                                                "value": "info_text",
                                            },
                                            {
                                                "label": "Permanent Hold",
                                                "value": "permanent_hold",
                                            },
                                            {
                                                "label": "Run Schedule",
                                                "value": "run_schedule",
                                            },
                                        ],
                                        "value": "permanent_hold",
                                    },
                                    {
                                        "actions": {
                                            "enable_scheduling": {
                                                "data": {"value": True},
                                                "href": (
                                                    "https://www.mynexia.com/mobile"
                                                    "/xxl_zones/83261015/scheduling_enabled"
                                                ),
                                                "method": "POST",
                                            },
                                            "get_active_schedule": {
                                                "href": (
                                                    "https://www.mynexia.com/mobile"
                                                    "/thermostat_schedules"
                                                    "/get_active_schedule"
                                                    "?device_identifier"
                                                    "=XxlZone-83261015"
                                                ),
                                                "method": "POST",
                                            },
                                            "get_default_schedule": {
                                                "href": (
                                                    "https://www.mynexia.com/mobile"
                                                    "/thermostat_schedules"
                                                    "/get_default_schedule"
                                                    "?device_identifier"
                                                    "=XxlZone-83261015"
                                                ),
                                                "method": "GET",
                                            },
                                            "set_active_schedule": {
                                                "href": (
                                                    "https://www.mynexia.com/mobile"
                                                    "/thermostat_schedules"
                                                    "/set_active_schedule"
                                                    "?device_identifier"
                                                    "=XxlZone-83261015"
                                                ),
                                                "method": "POST",
                                            },
                                        },
                                        "can_add_remove_periods": True,
                                        "collection_url": (
                                            "https://www.mynexia.com/mobile/schedules"
                                            "?device_identifier=XxlZone-83261015"
                                            "&house_id=123456"
                                        ),
                                        "enabled": True,
                                        "max_period_name_length": 10,
                                        "max_periods_per_day": 4,
                                        "name": "schedule",
                                        "setpoint_increment": 1,
                                    },
                                ],
                                "heating_setpoint": 63,
                                "icon": {
                                    "modifiers": ["temperature-75"],
                                    "name": "thermostat",
                                },
                                "id": 83261015,
                                "name": "Living West",
                                "operating_state": "",
                                "setpoints": {"cool": 79, "heat": 63},
                                "settings": [
                                    {
                                        "_links": {
                                            "self": {
                                                "href": (
                                                    "https://www.mynexia.com/mobile"
                                                    "/xxl_zones/83261015"
                                                    "/preset_selected"
                                                )
                                            }
                                        },
                                        "current_value": 0,
                                        "labels": ["None", "Home", "Away", "Sleep"],
                                        "options": [
                                            {"label": "None", "value": 0},
                                            {"label": "Home", "value": 1},
                                            {"label": "Away", "value": 2},
                                            {"label": "Sleep", "value": 3},
                                        ],
                                        "title": "Preset",
                                        "type": "preset_selected",
                                        "values": [0, 1, 2, 3],
                                    },
                                    {
                                        "_links": {
                                            "self": {
                                                "href": (
                                                    "https://www.mynexia.com/mobile"
                                                    "/xxl_zones/83261015/zone_mode"
                                                )
                                            }
                                        },
                                        "current_value": "AUTO",
                                        "labels": ["Auto", "Cooling", "Heating", "Off"],
                                        "options": [
                                            {"label": "Auto", "value": "AUTO"},
                                            {"label": "Cooling", "value": "COOL"},
                                            {"label": "Heating", "value": "HEAT"},
                                            {"label": "Off", "value": "OFF"},
                                        ],
                                        "title": "Zone Mode",
                                        "type": "zone_mode",
                                        "values": ["AUTO", "COOL", "HEAT", "OFF"],
                                    },
                                    {
                                        "_links": {
                                            "self": {
                                                "href": (
                                                    "https://www.mynexia.com/mobile"
                                                    "/xxl_zones/83261015/run_mode"
                                                )
                                            }
                                        },
                                        "current_value": "permanent_hold",
                                        "labels": [
                                            "Permanent Hold",
                                            "Run Schedule",
                                        ],
                                        "options": [
                                            {
                                                "label": "Permanent Hold",
                                                "value": "permanent_hold",
                                            },
                                            {
                                                "label": "Run Schedule",
                                                "value": "run_schedule",
                                            },
                                        ],
                                        "title": "Run Mode",
                                        "type": "run_mode",
                                        "values": ["permanent_hold", "run_schedule"],
                                    },
                                    {
                                        "_links": {
                                            "self": {
                                                "href": (
                                                    "https://www.mynexia.com/mobile"
                                                    "/xxl_zones/83261015"
                                                    "/scheduling_enabled"
                                                )
                                            }
                                        },
                                        "current_value": True,
                                        "labels": ["ON", "OFF"],
                                        "options": [
                                            {"label": "ON", "value": True},
                                            {"label": "OFF", "value": False},
                                        ],
                                        "title": "Scheduling",
                                        "type": "scheduling_enabled",
                                        "values": [True, False],
                                    },
                                ],
                                "temperature": 75,
                                "type": "xxl_zone",
                                "zone_status": "",
                            },
                            {
                                "_links": {
                                    "self": {
                                        "href": (
                                            "https://www.mynexia.com/mobile"
                                            "/xxl_zones/83261018"
                                        )
                                    }
                                },
                                "cooling_setpoint": 79,
                                "current_zone_mode": "AUTO",
                                "features": [
                                    {
                                        "actions": {
                                            "set_cool_setpoint": {
                                                "href": (
                                                    "https://www.mynexia.com/mobile"
                                                    "/xxl_zones/83261018/setpoints"
                                                )
                                            },
                                            "set_heat_setpoint": {
                                                "href": (
                                                    "https://www.mynexia.com/mobile"
                                                    "/xxl_zones/83261018/setpoints"
                                                )
                                            },
                                        },
                                        "name": "thermostat",
                                        "scale": "f",
                                        "setpoint_cool": 79,
                                        "setpoint_cool_max": 99,
                                        "setpoint_cool_min": 60,
                                        "setpoint_delta": 3,
                                        "setpoint_heat": 63,
                                        "setpoint_heat_max": 90,
                                        "setpoint_heat_min": 55,
                                        "setpoint_increment": 1.0,
                                        "status": "",
                                        "status_icon": None,
                                        "system_status": "System Idle",
                                        "temperature": 75,
                                    },
                                    {
                                        "is_connected": True,
                                        "name": "connection",
                                        "signal_strength": "unknown",
                                    },
                                    {
                                        "actions": {
                                            "update_thermostat_mode": {
                                                "href": (
                                                    "https://www.mynexia.com/mobile"
                                                    "/xxl_zones/83261018/zone_mode"
                                                ),
                                                "method": "POST",
                                            }
                                        },
                                        "display_value": "Auto",
                                        "label": "Zone Mode",
                                        "name": "thermostat_mode",
                                        "options": [
                                            {
                                                "header": True,
                                                "id": "thermostat_mode",
                                                "label": "Zone Mode",
                                                "value": "thermostat_mode",
                                            },
                                            {"label": "Auto", "value": "AUTO"},
                                            {"label": "Cooling", "value": "COOL"},
                                            {"label": "Heating", "value": "HEAT"},
                                            {"label": "Off", "value": "OFF"},
                                        ],
                                        "value": "AUTO",
                                    },
                                    {
                                        "actions": {
                                            "update_thermostat_run_mode": {
                                                "href": (
                                                    "https://www.mynexia.com/mobile"
                                                    "/xxl_zones/83261018/run_mode"
                                                ),
                                                "method": "POST",
                                            }
                                        },
                                        "display_value": "Hold",
                                        "label": "Run Mode",
                                        "name": "thermostat_run_mode",
                                        "options": [
                                            {
                                                "header": True,
                                                "id": "thermostat_run_mode",
                                                "label": "Run Mode",
                                                "value": "thermostat_run_mode",
                                            },
                                            {
                                                "id": "info_text",
                                                "info": True,
                                                "label": (
                                                    "Follow or override the schedule."
                                                ),
                                                "value": "info_text",
                                            },
                                            {
                                                "label": "Permanent Hold",
                                                "value": "permanent_hold",
                                            },
                                            {
                                                "label": "Run Schedule",
                                                "value": "run_schedule",
                                            },
                                        ],
                                        "value": "permanent_hold",
                                    },
                                    {
                                        "actions": {
                                            "enable_scheduling": {
                                                "data": {"value": True},
                                                "href": (
                                                    "https://www.mynexia.com/mobile"
                                                    "/xxl_zones/83261018"
                                                    "/scheduling_enabled"
                                                ),
                                                "method": "POST",
                                            },
                                            "get_active_schedule": {
                                                "href": (
                                                    "https://www.mynexia.com/mobile"
                                                    "/thermostat_schedules"
                                                    "/get_active_schedule"
                                                    "?device_identifier"
                                                    "=XxlZone-83261018"
                                                ),
                                                "method": "POST",
                                            },
                                            "get_default_schedule": {
                                                "href": (
                                                    "https://www.mynexia.com/mobile"
                                                    "/thermostat_schedules"
                                                    "/get_default_schedule"
                                                    "?device_identifier"
                                                    "=XxlZone-83261018"
                                                ),
                                                "method": "GET",
                                            },
                                            "set_active_schedule": {
                                                "href": (
                                                    "https://www.mynexia.com/mobile"
                                                    "/thermostat_schedules"
                                                    "/set_active_schedule"
                                                    "?device_identifier"
                                                    "=XxlZone-83261018"
                                                ),
                                                "method": "POST",
                                            },
                                        },
                                        "can_add_remove_periods": True,
                                        "collection_url": (
                                            "https://www.mynexia.com/mobile/schedules"
                                            "?device_identifier=XxlZone-83261018"
                                            "&house_id=123456"
                                        ),
                                        "enabled": True,
                                        "max_period_name_length": 10,
                                        "max_periods_per_day": 4,
                                        "name": "schedule",
                                        "setpoint_increment": 1,
                                    },
                                ],
                                "heating_setpoint": 63,
                                "icon": {
                                    "modifiers": ["temperature-75"],
                                    "name": "thermostat",
                                },
                                "id": 83261018,
                                "name": "David Office",
                                "operating_state": "",
                                "setpoints": {"cool": 79, "heat": 63},
                                "settings": [
                                    {
                                        "_links": {
                                            "self": {
                                                "href": (
                                                    "https://www.mynexia.com/mobile"
                                                    "/xxl_zones/83261018"
                                                    "/preset_selected"
                                                )
                                            }
                                        },
                                        "current_value": 0,
                                        "labels": ["None", "Home", "Away", "Sleep"],
                                        "options": [
                                            {"label": "None", "value": 0},
                                            {"label": "Home", "value": 1},
                                            {"label": "Away", "value": 2},
                                            {"label": "Sleep", "value": 3},
                                        ],
                                        "title": "Preset",
                                        "type": "preset_selected",
                                        "values": [0, 1, 2, 3],
                                    },
                                    {
                                        "_links": {
                                            "self": {
                                                "href": (
                                                    "https://www.mynexia.com/mobile"
                                                    "/xxl_zones/83261018/zone_mode"
                                                )
                                            }
                                        },
                                        "current_value": "AUTO",
                                        "labels": ["Auto", "Cooling", "Heating", "Off"],
                                        "options": [
                                            {"label": "Auto", "value": "AUTO"},
                                            {"label": "Cooling", "value": "COOL"},
                                            {"label": "Heating", "value": "HEAT"},
                                            {"label": "Off", "value": "OFF"},
                                        ],
                                        "title": "Zone Mode",
                                        "type": "zone_mode",
                                        "values": ["AUTO", "COOL", "HEAT", "OFF"],
                                    },
                                    {
                                        "_links": {
                                            "self": {
                                                "href": (
                                                    "https://www.mynexia.com/mobile"
                                                    "/xxl_zones/83261018/run_mode"
                                                )
                                            }
                                        },
                                        "current_value": "permanent_hold",
                                        "labels": [
                                            "Permanent Hold",
                                            "Run Schedule",
                                        ],
                                        "options": [
                                            {
                                                "label": "Permanent Hold",
                                                "value": "permanent_hold",
                                            },
                                            {
                                                "label": "Run Schedule",
                                                "value": "run_schedule",
                                            },
                                        ],
                                        "title": "Run Mode",
                                        "type": "run_mode",
                                        "values": ["permanent_hold", "run_schedule"],
                                    },
                                    {
                                        "_links": {
                                            "self": {
                                                "href": (
                                                    "https://www.mynexia.com/mobile"
                                                    "/xxl_zones/83261018"
                                                    "/scheduling_enabled"
                                                )
                                            }
                                        },
                                        "current_value": True,
                                        "labels": ["ON", "OFF"],
                                        "options": [
                                            {"label": "ON", "value": True},
                                            {"label": "OFF", "value": False},
                                        ],
                                        "title": "Scheduling",
                                        "type": "scheduling_enabled",
                                        "values": [True, False],
                                    },
                                ],
                                "temperature": 75,
                                "type": "xxl_zone",
                                "zone_status": "",
                            },
                        ],
                        "name": "group",
                    },
                    {
                        "actions": {
                            "update_thermostat_fan_mode": {
                                "href": (
                                    "https://www.mynexia.com/mobile/xxl_thermostats"
                                    "/2059676/fan_mode"
                                ),
                                "method": "POST",
                            }
                        },
                        "display_value": "Auto",
                        "label": "Fan Mode",
                        "name": "thermostat_fan_mode",
                        "options": [
                            {
                                "header": True,
                                "id": "thermostat_fan_mode",
                                "label": "Fan Mode",
                                "value": "thermostat_fan_mode",
                            },
                            {"label": "Auto", "value": "auto"},
                            {"label": "On", "value": "on"},
                            {"label": "Circulate", "value": "circulate"},
                        ],
                        "status_icon": {"modifiers": [], "name": "thermostat_fan_off"},
                        "value": "auto",
                    },
                    {"compressor_speed": 0.0, "name": "thermostat_compressor_speed"},
                    {
                        "actions": {
                            "get_monthly_runtime_history": {
                                "href": (
                                    "https://www.mynexia.com/mobile/runtime_history"
                                    "/2059676?report_type=monthly"
                                ),
                                "method": "GET",
                            },
                            "get_runtime_history": {
                                "href": (
                                    "https://www.mynexia.com/mobile/runtime_history"
                                    "/2059676?report_type=daily"
                                ),
                                "method": "GET",
                            },
                        },
                        "name": "runtime_history",
                    },
                ],
                "has_indoor_humidity": True,
                "has_outdoor_temperature": True,
                "icon": [
                    {"modifiers": ["temperature-75"], "name": "thermostat"},
                    {"modifiers": ["temperature-75"], "name": "thermostat"},
                ],
                "id": 2059676,
                "indoor_humidity": "52",
                "last_updated_at": "2020-03-11T15:15:53.000-05:00",
                "name": "Downstairs West Wing",
                "name_editable": True,
                "outdoor_temperature": "88",
                "settings": [
                    {
                        "_links": {
                            "self": {
                                "href": (
                                    "https://www.mynexia.com/mobile/xxl_thermostats"
                                    "/2059676/fan_mode"
                                )
                            }
                        },
                        "current_value": "auto",
                        "labels": ["Auto", "On", "Circulate"],
                        "options": [
                            {"label": "Auto", "value": "auto"},
                            {"label": "On", "value": "on"},
                            {"label": "Circulate", "value": "circulate"},
                        ],
                        "title": "Fan Mode",
                        "type": "fan_mode",
                        "values": ["auto", "on", "circulate"],
                    },
                    {
                        "_links": {
                            "self": {
                                "href": (
                                    "https://www.mynexia.com/mobile/xxl_thermostats"
                                    "/2059676/fan_speed"
                                )
                            }
                        },
                        "current_value": 0.35,
                        "labels": [
                            "35%",
                            "40%",
                            "45%",
                            "50%",
                            "55%",
                            "60%",
                            "65%",
                            "70%",
                            "75%",
                            "80%",
                            "85%",
                            "90%",
                            "95%",
                            "100%",
                        ],
                        "options": [
                            {"label": "35%", "value": 0.35},
                            {"label": "40%", "value": 0.4},
                            {"label": "45%", "value": 0.45},
                            {"label": "50%", "value": 0.5},
                            {"label": "55%", "value": 0.55},
                            {"label": "60%", "value": 0.6},
                            {"label": "65%", "value": 0.65},
                            {"label": "70%", "value": 0.7},
                            {"label": "75%", "value": 0.75},
                            {"label": "80%", "value": 0.8},
                            {"label": "85%", "value": 0.85},
                            {"label": "90%", "value": 0.9},
                            {"label": "95%", "value": 0.95},
                            {"label": "100%", "value": 1.0},
                        ],
                        "title": "Fan Speed",
                        "type": "fan_speed",
                        "values": [
                            0.35,
                            0.4,
                            0.45,
                            0.5,
                            0.55,
                            0.6,
                            0.65,
                            0.7,
                            0.75,
                            0.8,
                            0.85,
                            0.9,
                            0.95,
                            1.0,
                        ],
                    },
                    {
                        "_links": {
                            "self": {
                                "href": (
                                    "https://www.mynexia.com/mobile/xxl_thermostats"
                                    "/2059676/fan_circulation_time"
                                )
                            }
                        },
                        "current_value": 30,
                        "labels": [
                            "10 minutes",
                            "15 minutes",
                            "20 minutes",
                            "25 minutes",
                            "30 minutes",
                            "35 minutes",
                            "40 minutes",
                            "45 minutes",
                            "50 minutes",
                            "55 minutes",
                        ],
                        "options": [
                            {"label": "10 minutes", "value": 10},
                            {"label": "15 minutes", "value": 15},
                            {"label": "20 minutes", "value": 20},
                            {"label": "25 minutes", "value": 25},
                            {"label": "30 minutes", "value": 30},
                            {"label": "35 minutes", "value": 35},
                            {"label": "40 minutes", "value": 40},
                            {"label": "45 minutes", "value": 45},
                            {"label": "50 minutes", "value": 50},
                            {"label": "55 minutes", "value": 55},
                        ],
                        "title": "Fan Circulation Time",
                        "type": "fan_circulation_time",
                        "values": [10, 15, 20, 25, 30, 35, 40, 45, 50, 55],
                    },
                    {
                        "_links": {
                            "self": {
                                "href": (
                                    "https://www.mynexia.com/mobile/xxl_thermostats"
                                    "/2059676/air_cleaner_mode"
                                )
                            }
                        },
                        "current_value": "auto",
                        "labels": ["Auto", "Quick", "Allergy"],
                        "options": [
                            {"label": "Auto", "value": "auto"},
                            {"label": "Quick", "value": "quick"},
                            {"label": "Allergy", "value": "allergy"},
                        ],
                        "title": "Air Cleaner Mode",
                        "type": "air_cleaner_mode",
                        "values": ["auto", "quick", "allergy"],
                    },
                    {
                        "_links": {
                            "self": {
                                "href": (
                                    "https://www.mynexia.com/mobile/xxl_thermostats"
                                    "/2059676/dehumidify"
                                )
                            }
                        },
                        "current_value": 0.45,
                        "labels": ["35%", "40%", "45%", "50%", "55%", "60%", "65%"],
                        "options": [
                            {"label": "35%", "value": 0.35},
                            {"label": "40%", "value": 0.4},
                            {"label": "45%", "value": 0.45},
                            {"label": "50%", "value": 0.5},
                            {"label": "55%", "value": 0.55},
                            {"label": "60%", "value": 0.6},
                            {"label": "65%", "value": 0.65},
                        ],
                        "title": "Cooling Dehumidify Set Point",
                        "type": "dehumidify",
                        "values": [0.35, 0.4, 0.45, 0.5, 0.55, 0.6, 0.65],
                    },
                    {
                        "_links": {
                            "self": {
                                "href": (
                                    "https://www.mynexia.com/mobile/xxl_thermostats"
                                    "/2059676/scale"
                                )
                            }
                        },
                        "current_value": "f",
                        "labels": ["F", "C"],
                        "options": [
                            {"label": "F", "value": "f"},
                            {"label": "C", "value": "c"},
                        ],
                        "title": "Temperature Scale",
                        "type": "scale",
                        "values": ["f", "c"],
                    },
                ],
                "status_secondary": None,
                "status_tertiary": None,
                "system_status": "System Idle",
                "type": "xxl_thermostat",
                "zones": [
                    {
                        "_links": {
                            "self": {
                                "href": (
                                    "https://www.mynexia.com/mobile/xxl_zones/83261015"
                                )
                            }
                        },
                        "cooling_setpoint": 79,
                        "current_zone_mode": "AUTO",
                        "features": [
                            {
                                "actions": {
                                    "set_cool_setpoint": {
                                        "href": (
                                            "https://www.mynexia.com/mobile/xxl_zones"
                                            "/83261015/setpoints"
                                        )
                                    },
                                    "set_heat_setpoint": {
                                        "href": (
                                            "https://www.mynexia.com/mobile/xxl_zones"
                                            "/83261015/setpoints"
                                        )
                                    },
                                },
                                "name": "thermostat",
                                "scale": "f",
                                "setpoint_cool": 79,
                                "setpoint_cool_max": 99,
                                "setpoint_cool_min": 60,
                                "setpoint_delta": 3,
                                "setpoint_heat": 63,
                                "setpoint_heat_max": 90,
                                "setpoint_heat_min": 55,
                                "setpoint_increment": 1.0,
                                "status": "",
                                "status_icon": None,
                                "system_status": "System Idle",
                                "temperature": 75,
                            },
                            {
                                "is_connected": True,
                                "name": "connection",
                                "signal_strength": "unknown",
                            },
                            {
                                "actions": {
                                    "update_thermostat_mode": {
                                        "href": (
                                            "https://www.mynexia.com/mobile/xxl_zones"
                                            "/83261015/zone_mode"
                                        ),
                                        "method": "POST",
                                    }
                                },
                                "display_value": "Auto",
                                "label": "Zone Mode",
                                "name": "thermostat_mode",
                                "options": [
                                    {
                                        "header": True,
                                        "id": "thermostat_mode",
                                        "label": "Zone Mode",
                                        "value": "thermostat_mode",
                                    },
                                    {"label": "Auto", "value": "AUTO"},
                                    {"label": "Cooling", "value": "COOL"},
                                    {"label": "Heating", "value": "HEAT"},
                                    {"label": "Off", "value": "OFF"},
                                ],
                                "value": "AUTO",
                            },
                            {
                                "actions": {
                                    "update_thermostat_run_mode": {
                                        "href": (
                                            "https://www.mynexia.com/mobile/xxl_zones"
                                            "/83261015/run_mode"
                                        ),
                                        "method": "POST",
                                    }
                                },
                                "display_value": "Hold",
                                "label": "Run Mode",
                                "name": "thermostat_run_mode",
                                "options": [
                                    {
                                        "header": True,
                                        "id": "thermostat_run_mode",
                                        "label": "Run Mode",
                                        "value": "thermostat_run_mode",
                                    },
                                    {
                                        "id": "info_text",
                                        "info": True,
                                        "label": "Follow or override the schedule.",
                                        "value": "info_text",
                                    },
                                    {
                                        "label": "Permanent Hold",
                                        "value": "permanent_hold",
                                    },
                                    {"label": "Run Schedule", "value": "run_schedule"},
                                ],
                                "value": "permanent_hold",
                            },
                            {
                                "actions": {
                                    "enable_scheduling": {
                                        "data": {"value": True},
                                        "href": (
                                            "https://www.mynexia.com/mobile/xxl_zones"
                                            "/83261015/scheduling_enabled"
                                        ),
                                        "method": "POST",
                                    },
                                    "get_active_schedule": {
                                        "href": (
                                            "https://www.mynexia.com/mobile"
                                            "/thermostat_schedules/get_active_schedule"
                                            "?device_identifier=XxlZone-83261015"
                                        ),
                                        "method": "POST",
                                    },
                                    "get_default_schedule": {
                                        "href": (
                                            "https://www.mynexia.com/mobile"
                                            "/thermostat_schedules/get_default_schedule"
                                            "?device_identifier=XxlZone-83261015"
                                        ),
                                        "method": "GET",
                                    },
                                    "set_active_schedule": {
                                        "href": (
                                            "https://www.mynexia.com/mobile"
                                            "/thermostat_schedules/set_active_schedule"
                                            "?device_identifier=XxlZone-83261015"
                                        ),
                                        "method": "POST",
                                    },
                                },
                                "can_add_remove_periods": True,
                                "collection_url": (
                                    "https://www.mynexia.com/mobile/schedules"
                                    "?device_identifier=XxlZone-83261015"
                                    "&house_id=123456"
                                ),
                                "enabled": True,
                                "max_period_name_length": 10,
                                "max_periods_per_day": 4,
                                "name": "schedule",
                                "setpoint_increment": 1,
                            },
                        ],
                        "heating_setpoint": 63,
                        "icon": {"modifiers": ["temperature-75"], "name": "thermostat"},
                        "id": 83261015,
                        "name": "Living West",
                        "operating_state": "",
                        "setpoints": {"cool": 79, "heat": 63},
                        "settings": [
                            {
                                "_links": {
                                    "self": {
                                        "href": (
                                            "https://www.mynexia.com/mobile/xxl_zones"
                                            "/83261015/preset_selected"
                                        )
                                    }
                                },
                                "current_value": 0,
                                "labels": ["None", "Home", "Away", "Sleep"],
                                "options": [
                                    {"label": "None", "value": 0},
                                    {"label": "Home", "value": 1},
                                    {"label": "Away", "value": 2},
                                    {"label": "Sleep", "value": 3},
                                ],
                                "title": "Preset",
                                "type": "preset_selected",
                                "values": [0, 1, 2, 3],
                            },
                            {
                                "_links": {
                                    "self": {
                                        "href": (
                                            "https://www.mynexia.com/mobile"
                                            "/xxl_zones/83261015/zone_mode"
                                        )
                                    }
                                },
                                "current_value": "AUTO",
                                "labels": ["Auto", "Cooling", "Heating", "Off"],
                                "options": [
                                    {"label": "Auto", "value": "AUTO"},
                                    {"label": "Cooling", "value": "COOL"},
                                    {"label": "Heating", "value": "HEAT"},
                                    {"label": "Off", "value": "OFF"},
                                ],
                                "title": "Zone Mode",
                                "type": "zone_mode",
                                "values": ["AUTO", "COOL", "HEAT", "OFF"],
                            },
                            {
                                "_links": {
                                    "self": {
                                        "href": (
                                            "https://www.mynexia.com/mobile"
                                            "/xxl_zones/83261015/run_mode"
                                        )
                                    }
                                },
                                "current_value": "permanent_hold",
                                "labels": ["Permanent Hold", "Run Schedule"],
                                "options": [
                                    {
                                        "label": "Permanent Hold",
                                        "value": "permanent_hold",
                                    },
                                    {"label": "Run Schedule", "value": "run_schedule"},
                                ],
                                "title": "Run Mode",
                                "type": "run_mode",
                                "values": ["permanent_hold", "run_schedule"],
                            },
                            {
                                "_links": {
                                    "self": {
                                        "href": (
                                            "https://www.mynexia.com/mobile"
                                            "/xxl_zones/83261015/scheduling_enabled"
                                        )
                                    }
                                },
                                "current_value": True,
                                "labels": ["ON", "OFF"],
                                "options": [
                                    {"label": "ON", "value": True},
                                    {"label": "OFF", "value": False},
                                ],
                                "title": "Scheduling",
                                "type": "scheduling_enabled",
                                "values": [True, False],
                            },
                        ],
                        "temperature": 75,
                        "type": "xxl_zone",
                        "zone_status": "",
                    },
                    {
                        "_links": {
                            "self": {
                                "href": (
                                    "https://www.mynexia.com/mobile/xxl_zones/83261018"
                                )
                            }
                        },
                        "cooling_setpoint": 79,
                        "current_zone_mode": "AUTO",
                        "features": [
                            {
                                "actions": {
                                    "set_cool_setpoint": {
                                        "href": (
                                            "https://www.mynexia.com/mobile"
                                            "/xxl_zones/83261018/setpoints"
                                        )
                                    },
                                    "set_heat_setpoint": {
                                        "href": (
                                            "https://www.mynexia.com/mobile"
                                            "/xxl_zones/83261018/setpoints"
                                        )
                                    },
                                },
                                "name": "thermostat",
                                "scale": "f",
                                "setpoint_cool": 79,
                                "setpoint_cool_max": 99,
                                "setpoint_cool_min": 60,
                                "setpoint_delta": 3,
                                "setpoint_heat": 63,
                                "setpoint_heat_max": 90,
                                "setpoint_heat_min": 55,
                                "setpoint_increment": 1.0,
                                "status": "",
                                "status_icon": None,
                                "system_status": "System Idle",
                                "temperature": 75,
                            },
                            {
                                "is_connected": True,
                                "name": "connection",
                                "signal_strength": "unknown",
                            },
                            {
                                "actions": {
                                    "update_thermostat_mode": {
                                        "href": (
                                            "https://www.mynexia.com/mobile"
                                            "/xxl_zones/83261018/zone_mode"
                                        ),
                                        "method": "POST",
                                    }
                                },
                                "display_value": "Auto",
                                "label": "Zone Mode",
                                "name": "thermostat_mode",
                                "options": [
                                    {
                                        "header": True,
                                        "id": "thermostat_mode",
                                        "label": "Zone Mode",
                                        "value": "thermostat_mode",
                                    },
                                    {"label": "Auto", "value": "AUTO"},
                                    {"label": "Cooling", "value": "COOL"},
                                    {"label": "Heating", "value": "HEAT"},
                                    {"label": "Off", "value": "OFF"},
                                ],
                                "value": "AUTO",
                            },
                            {
                                "actions": {
                                    "update_thermostat_run_mode": {
                                        "href": (
                                            "https://www.mynexia.com/mobile"
                                            "/xxl_zones/83261018/run_mode"
                                        ),
                                        "method": "POST",
                                    }
                                },
                                "display_value": "Hold",
                                "label": "Run Mode",
                                "name": "thermostat_run_mode",
                                "options": [
                                    {
                                        "header": True,
                                        "id": "thermostat_run_mode",
                                        "label": "Run Mode",
                                        "value": "thermostat_run_mode",
                                    },
                                    {
                                        "id": "info_text",
                                        "info": True,
                                        "label": "Follow or override the schedule.",
                                        "value": "info_text",
                                    },
                                    {
                                        "label": "Permanent Hold",
                                        "value": "permanent_hold",
                                    },
                                    {"label": "Run Schedule", "value": "run_schedule"},
                                ],
                                "value": "permanent_hold",
                            },
                            {
                                "actions": {
                                    "enable_scheduling": {
                                        "data": {"value": True},
                                        "href": (
                                            "https://www.mynexia.com/mobile/xxl_zones"
                                            "/83261018/scheduling_enabled"
                                        ),
                                        "method": "POST",
                                    },
                                    "get_active_schedule": {
                                        "href": (
                                            "https://www.mynexia.com/mobile"
                                            "/thermostat_schedules/get_active_schedule"
                                            "?device_identifier=XxlZone-83261018"
                                        ),
                                        "method": "POST",
                                    },
                                    "get_default_schedule": {
                                        "href": (
                                            "https://www.mynexia.com/mobile"
                                            "/thermostat_schedules/get_default_schedule"
                                            "?device_identifier=XxlZone-83261018"
                                        ),
                                        "method": "GET",
                                    },
                                    "set_active_schedule": {
                                        "href": (
                                            "https://www.mynexia.com/mobile"
                                            "/thermostat_schedules/set_active_schedule"
                                            "?device_identifier=XxlZone-83261018"
                                        ),
                                        "method": "POST",
                                    },
                                },
                                "can_add_remove_periods": True,
                                "collection_url": (
                                    "https://www.mynexia.com/mobile/schedules"
                                    "?device_identifier=XxlZone-83261018"
                                    "&house_id=123456"
                                ),
                                "enabled": True,
                                "max_period_name_length": 10,
                                "max_periods_per_day": 4,
                                "name": "schedule",
                                "setpoint_increment": 1,
                            },
                        ],
                        "heating_setpoint": 63,
                        "icon": {"modifiers": ["temperature-75"], "name": "thermostat"},
                        "id": 83261018,
                        "name": "David Office",
                        "operating_state": "",
                        "setpoints": {"cool": 79, "heat": 63},
                        "settings": [
                            {
                                "_links": {
                                    "self": {
                                        "href": (
                                            "https://www.mynexia.com/mobile"
                                            "/xxl_zones/83261018/preset_selected"
                                        )
                                    }
                                },
                                "current_value": 0,
                                "labels": ["None", "Home", "Away", "Sleep"],
                                "options": [
                                    {"label": "None", "value": 0},
                                    {"label": "Home", "value": 1},
                                    {"label": "Away", "value": 2},
                                    {"label": "Sleep", "value": 3},
                                ],
                                "title": "Preset",
                                "type": "preset_selected",
                                "values": [0, 1, 2, 3],
                            },
                            {
                                "_links": {
                                    "self": {
                                        "href": (
                                            "https://www.mynexia.com/mobile"
                                            "/xxl_zones/83261018/zone_mode"
                                        )
                                    }
                                },
                                "current_value": "AUTO",
                                "labels": ["Auto", "Cooling", "Heating", "Off"],
                                "options": [
                                    {"label": "Auto", "value": "AUTO"},
                                    {"label": "Cooling", "value": "COOL"},
                                    {"label": "Heating", "value": "HEAT"},
                                    {"label": "Off", "value": "OFF"},
                                ],
                                "title": "Zone Mode",
                                "type": "zone_mode",
                                "values": ["AUTO", "COOL", "HEAT", "OFF"],
                            },
                            {
                                "_links": {
                                    "self": {
                                        "href": (
                                            "https://www.mynexia.com/mobile"
                                            "/xxl_zones/83261018/run_mode"
                                        )
                                    }
                                },
                                "current_value": "permanent_hold",
                                "labels": ["Permanent Hold", "Run Schedule"],
                                "options": [
                                    {
                                        "label": "Permanent Hold",
                                        "value": "permanent_hold",
                                    },
                                    {"label": "Run Schedule", "value": "run_schedule"},
                                ],
                                "title": "Run Mode",
                                "type": "run_mode",
                                "values": ["permanent_hold", "run_schedule"],
                            },
                            {
                                "_links": {
                                    "self": {
                                        "href": (
                                            "https://www.mynexia.com/mobile"
                                            "/xxl_zones/83261018/scheduling_enabled"
                                        )
                                    }
                                },
                                "current_value": True,
                                "labels": ["ON", "OFF"],
                                "options": [
                                    {"label": "ON", "value": True},
                                    {"label": "OFF", "value": False},
                                ],
                                "title": "Scheduling",
                                "type": "scheduling_enabled",
                                "values": [True, False],
                            },
                        ],
                        "temperature": 75,
                        "type": "xxl_zone",
                        "zone_status": "",
                    },
                ],
            },
            {
                "_links": {
                    "filter_events": {
                        "href": (
                            "https://www.mynexia.com/mobile/houses/123456/events"
                            "/collection?sys_guid=e3fc90c7-2885-4f57-ae76-99e9ec81eef0"
                        )
                    },
                    "nexia:history": {
                        "href": (
                            "https://www.mynexia.com/mobile/houses/123456"
                            "/events?device_id=2293892"
                        )
                    },
                    "pending_request": {
                        "polling_path": (
                            "https://www.mynexia.com/backstage/announcements"
                            "/967361e8aed874aa5230930fd0e0bbd8b653261e982a6e0e"
                        )
                    },
                    "self": {
                        "href": "https://www.mynexia.com/mobile/xxl_thermostats/2293892"
                    },
                },
                "connected": True,
                "delta": 3,
                "features": [
                    {
                        "items": [
                            {
                                "label": "Model",
                                "type": "label_value",
                                "value": "XL1050",
                            },
                            {
                                "label": "AUID",
                                "type": "label_value",
                                "value": "0281B02C",
                            },
                            {
                                "label": "Firmware Build Number",
                                "type": "label_value",
                                "value": "1581321824",
                            },
                            {
                                "label": "Firmware Build Date",
                                "type": "label_value",
                                "value": "2020-02-10 08:03:44 UTC",
                            },
                            {
                                "label": "Firmware Version",
                                "type": "label_value",
                                "value": "5.9.1",
                            },
                            {
                                "label": "Zoning Enabled",
                                "type": "label_value",
                                "value": "yes",
                            },
                        ],
                        "name": "advanced_info",
                    },
                    {
                        "actions": {},
                        "name": "thermostat",
                        "scale": "f",
                        "setpoint_cool_max": 99,
                        "setpoint_cool_min": 60,
                        "setpoint_delta": 3,
                        "setpoint_heat_max": 90,
                        "setpoint_heat_min": 55,
                        "setpoint_increment": 1.0,
                        "status": "Cooling",
                        "status_icon": {"modifiers": [], "name": "cooling"},
                        "temperature": 73,
                    },
                    {
                        "is_connected": True,
                        "name": "connection",
                        "signal_strength": "unknown",
                    },
                    {
                        "members": [
                            {
                                "_links": {
                                    "self": {
                                        "href": (
                                            "https://www.mynexia.com/mobile"
                                            "/xxl_zones/83394133"
                                        )
                                    }
                                },
                                "cooling_setpoint": 79,
                                "current_zone_mode": "AUTO",
                                "features": [
                                    {
                                        "actions": {
                                            "set_cool_setpoint": {
                                                "href": (
                                                    "https://www.mynexia.com/mobile"
                                                    "/xxl_zones/83394133/setpoints"
                                                )
                                            },
                                            "set_heat_setpoint": {
                                                "href": (
                                                    "https://www.mynexia.com/mobile"
                                                    "/xxl_zones/83394133/setpoints"
                                                )
                                            },
                                        },
                                        "name": "thermostat",
                                        "scale": "f",
                                        "setpoint_cool": 79,
                                        "setpoint_cool_max": 99,
                                        "setpoint_cool_min": 60,
                                        "setpoint_delta": 3,
                                        "setpoint_heat": 63,
                                        "setpoint_heat_max": 90,
                                        "setpoint_heat_min": 55,
                                        "setpoint_increment": 1.0,
                                        "status": "Relieving Air",
                                        "status_icon": {
                                            "modifiers": [],
                                            "name": "cooling",
                                        },
                                        "system_status": "Cooling",
                                        "temperature": 73,
                                    },
                                    {
                                        "is_connected": True,
                                        "name": "connection",
                                        "signal_strength": "unknown",
                                    },
                                    {
                                        "actions": {
                                            "update_thermostat_mode": {
                                                "href": (
                                                    "https://www.mynexia.com/mobile"
                                                    "/xxl_zones/83394133/zone_mode"
                                                ),
                                                "method": "POST",
                                            }
                                        },
                                        "display_value": "Auto",
                                        "label": "Zone Mode",
                                        "name": "thermostat_mode",
                                        "options": [
                                            {
                                                "header": True,
                                                "id": "thermostat_mode",
                                                "label": "Zone Mode",
                                                "value": "thermostat_mode",
                                            },
                                            {"label": "Auto", "value": "AUTO"},
                                            {"label": "Cooling", "value": "COOL"},
                                            {"label": "Heating", "value": "HEAT"},
                                            {"label": "Off", "value": "OFF"},
                                        ],
                                        "value": "AUTO",
                                    },
                                    {
                                        "actions": {
                                            "update_thermostat_run_mode": {
                                                "href": (
                                                    "https://www.mynexia.com/mobile"
                                                    "/xxl_zones/83394133/run_mode"
                                                ),
                                                "method": "POST",
                                            }
                                        },
                                        "display_value": "Hold",
                                        "label": "Run Mode",
                                        "name": "thermostat_run_mode",
                                        "options": [
                                            {
                                                "header": True,
                                                "id": "thermostat_run_mode",
                                                "label": "Run Mode",
                                                "value": "thermostat_run_mode",
                                            },
                                            {
                                                "id": "info_text",
                                                "info": True,
                                                "label": (
                                                    "Follow or override the schedule."
                                                ),
                                                "value": "info_text",
                                            },
                                            {
                                                "label": "Permanent Hold",
                                                "value": "permanent_hold",
                                            },
                                            {
                                                "label": "Run Schedule",
                                                "value": "run_schedule",
                                            },
                                        ],
                                        "value": "permanent_hold",
                                    },
                                    {
                                        "actions": {
                                            "enable_scheduling": {
                                                "data": {"value": True},
                                                "href": (
                                                    "https://www.mynexia.com/mobile"
                                                    "/xxl_zones/83394133/scheduling_enabled"
                                                ),
                                                "method": "POST",
                                            },
                                            "get_active_schedule": {
                                                "href": (
                                                    "https://www.mynexia.com/mobile"
                                                    "/thermostat_schedules"
                                                    "/get_active_schedule"
                                                    "?device_identifier=XxlZone-83394133"
                                                ),
                                                "method": "POST",
                                            },
                                            "get_default_schedule": {
                                                "href": (
                                                    "https://www.mynexia.com/mobile"
                                                    "/thermostat_schedules"
                                                    "/get_default_schedule"
                                                    "?device_identifier=XxlZone-83394133"
                                                ),
                                                "method": "GET",
                                            },
                                            "set_active_schedule": {
                                                "href": (
                                                    "https://www.mynexia.com/mobile"
                                                    "/thermostat_schedules/set_active_schedule"
                                                    "?device_identifier=XxlZone-83394133"
                                                ),
                                                "method": "POST",
                                            },
                                        },
                                        "can_add_remove_periods": True,
                                        "collection_url": (
                                            "https://www.mynexia.com/mobile/schedules"
                                            "?device_identifier=XxlZone-83394133"
                                            "&house_id=123456"
                                        ),
                                        "enabled": True,
                                        "max_period_name_length": 10,
                                        "max_periods_per_day": 4,
                                        "name": "schedule",
                                        "setpoint_increment": 1,
                                    },
                                ],
                                "heating_setpoint": 63,
                                "icon": {
                                    "modifiers": ["temperature-73"],
                                    "name": "thermostat",
                                },
                                "id": 83394133,
                                "name": "Bath Closet",
                                "operating_state": "Relieving Air",
                                "setpoints": {"cool": 79, "heat": 63},
                                "settings": [
                                    {
                                        "_links": {
                                            "self": {
                                                "href": (
                                                    "https://www.mynexia.com/mobile"
                                                    "/xxl_zones/83394133/preset_selected"
                                                )
                                            }
                                        },
                                        "current_value": 0,
                                        "labels": ["None", "Home", "Away", "Sleep"],
                                        "options": [
                                            {"label": "None", "value": 0},
                                            {"label": "Home", "value": 1},
                                            {"label": "Away", "value": 2},
                                            {"label": "Sleep", "value": 3},
                                        ],
                                        "title": "Preset",
                                        "type": "preset_selected",
                                        "values": [0, 1, 2, 3],
                                    },
                                    {
                                        "_links": {
                                            "self": {
                                                "href": (
                                                    "https://www.mynexia.com/mobile"
                                                    "/xxl_zones/83394133/zone_mode"
                                                )
                                            }
                                        },
                                        "current_value": "AUTO",
                                        "labels": ["Auto", "Cooling", "Heating", "Off"],
                                        "options": [
                                            {"label": "Auto", "value": "AUTO"},
                                            {"label": "Cooling", "value": "COOL"},
                                            {"label": "Heating", "value": "HEAT"},
                                            {"label": "Off", "value": "OFF"},
                                        ],
                                        "title": "Zone Mode",
                                        "type": "zone_mode",
                                        "values": ["AUTO", "COOL", "HEAT", "OFF"],
                                    },
                                    {
                                        "_links": {
                                            "self": {
                                                "href": (
                                                    "https://www.mynexia.com/mobile"
                                                    "/xxl_zones/83394133/run_mode"
                                                )
                                            }
                                        },
                                        "current_value": "permanent_hold",
                                        "labels": [
                                            "Permanent Hold",
                                            "Run Schedule",
                                        ],
                                        "options": [
                                            {
                                                "label": "Permanent Hold",
                                                "value": "permanent_hold",
                                            },
                                            {
                                                "label": "Run Schedule",
                                                "value": "run_schedule",
                                            },
                                        ],
                                        "title": "Run Mode",
                                        "type": "run_mode",
                                        "values": ["permanent_hold", "run_schedule"],
                                    },
                                    {
                                        "_links": {
                                            "self": {
                                                "href": (
                                                    "https://www.mynexia.com/mobile"
                                                    "/xxl_zones/83394133/scheduling_enabled"
                                                )
                                            }
                                        },
                                        "current_value": True,
                                        "labels": ["ON", "OFF"],
                                        "options": [
                                            {"label": "ON", "value": True},
                                            {"label": "OFF", "value": False},
                                        ],
                                        "title": "Scheduling",
                                        "type": "scheduling_enabled",
                                        "values": [True, False],
                                    },
                                ],
                                "temperature": 73,
                                "type": "xxl_zone",
                                "zone_status": "Relieving Air",
                            },
                            {
                                "_links": {
                                    "self": {
                                        "href": (
                                            "https://www.mynexia.com/mobile"
                                            "/xxl_zones/83394130"
                                        )
                                    }
                                },
                                "cooling_setpoint": 71,
                                "current_zone_mode": "AUTO",
                                "features": [
                                    {
                                        "actions": {
                                            "set_cool_setpoint": {
                                                "href": (
                                                    "https://www.mynexia.com/mobile"
                                                    "/xxl_zones/83394130/setpoints"
                                                )
                                            },
                                            "set_heat_setpoint": {
                                                "href": (
                                                    "https://www.mynexia.com/mobile"
                                                    "/xxl_zones/83394130/setpoints"
                                                )
                                            },
                                        },
                                        "name": "thermostat",
                                        "scale": "f",
                                        "setpoint_cool": 71,
                                        "setpoint_cool_max": 99,
                                        "setpoint_cool_min": 60,
                                        "setpoint_delta": 3,
                                        "setpoint_heat": 63,
                                        "setpoint_heat_max": 90,
                                        "setpoint_heat_min": 55,
                                        "setpoint_increment": 1.0,
                                        "status": "Damper Open",
                                        "status_icon": {
                                            "modifiers": [],
                                            "name": "cooling",
                                        },
                                        "system_status": "Cooling",
                                        "temperature": 74,
                                    },
                                    {
                                        "is_connected": True,
                                        "name": "connection",
                                        "signal_strength": "unknown",
                                    },
                                    {
                                        "actions": {
                                            "update_thermostat_mode": {
                                                "href": (
                                                    "https://www.mynexia.com/mobile"
                                                    "/xxl_zones/83394130/zone_mode"
                                                ),
                                                "method": "POST",
                                            }
                                        },
                                        "display_value": "Auto",
                                        "label": "Zone Mode",
                                        "name": "thermostat_mode",
                                        "options": [
                                            {
                                                "header": True,
                                                "id": "thermostat_mode",
                                                "label": "Zone Mode",
                                                "value": "thermostat_mode",
                                            },
                                            {"label": "Auto", "value": "AUTO"},
                                            {"label": "Cooling", "value": "COOL"},
                                            {"label": "Heating", "value": "HEAT"},
                                            {"label": "Off", "value": "OFF"},
                                        ],
                                        "value": "AUTO",
                                    },
                                    {
                                        "actions": {
                                            "update_thermostat_run_mode": {
                                                "href": (
                                                    "https://www.mynexia.com/mobile"
                                                    "/xxl_zones/83394130/run_mode"
                                                ),
                                                "method": "POST",
                                            }
                                        },
                                        "display_value": "Hold",
                                        "label": "Run Mode",
                                        "name": "thermostat_run_mode",
                                        "options": [
                                            {
                                                "header": True,
                                                "id": "thermostat_run_mode",
                                                "label": "Run Mode",
                                                "value": "thermostat_run_mode",
                                            },
                                            {
                                                "id": "info_text",
                                                "info": True,
                                                "label": (
                                                    "Follow or override the schedule."
                                                ),
                                                "value": "info_text",
                                            },
                                            {
                                                "label": "Permanent Hold",
                                                "value": "permanent_hold",
                                            },
                                            {
                                                "label": "Run Schedule",
                                                "value": "run_schedule",
                                            },
                                        ],
                                        "value": "permanent_hold",
                                    },
                                    {
                                        "actions": {
                                            "enable_scheduling": {
                                                "data": {"value": True},
                                                "href": (
                                                    "https://www.mynexia.com/mobile"
                                                    "/xxl_zones/83394130"
                                                    "/scheduling_enabled"
                                                ),
                                                "method": "POST",
                                            },
                                            "get_active_schedule": {
                                                "href": (
                                                    "https://www.mynexia.com/mobile"
                                                    "/thermostat_schedules"
                                                    "/get_active_schedule"
                                                    "?device_identifier"
                                                    "=XxlZone-83394130"
                                                ),
                                                "method": "POST",
                                            },
                                            "get_default_schedule": {
                                                "href": (
                                                    "https://www.mynexia.com/mobile"
                                                    "/thermostat_schedules"
                                                    "/get_default_schedule"
                                                    "?device_identifier"
                                                    "=XxlZone-83394130"
                                                ),
                                                "method": "GET",
                                            },
                                            "set_active_schedule": {
                                                "href": (
                                                    "https://www.mynexia.com/mobile"
                                                    "/thermostat_schedules"
                                                    "/set_active_schedule"
                                                    "?device_identifier"
                                                    "=XxlZone-83394130"
                                                ),
                                                "method": "POST",
                                            },
                                        },
                                        "can_add_remove_periods": True,
                                        "collection_url": (
                                            "https://www.mynexia.com/mobile/schedules"
                                            "?device_identifier=XxlZone-83394130"
                                            "&house_id=123456"
                                        ),
                                        "enabled": True,
                                        "max_period_name_length": 10,
                                        "max_periods_per_day": 4,
                                        "name": "schedule",
                                        "setpoint_increment": 1,
                                    },
                                ],
                                "heating_setpoint": 63,
                                "icon": {
                                    "modifiers": ["temperature-74"],
                                    "name": "thermostat",
                                },
                                "id": 83394130,
                                "name": "Master",
                                "operating_state": "Damper Open",
                                "setpoints": {"cool": 71, "heat": 63},
                                "settings": [
                                    {
                                        "_links": {
                                            "self": {
                                                "href": (
                                                    "https://www.mynexia.com/mobile"
                                                    "/xxl_zones/83394130"
                                                    "/preset_selected"
                                                )
                                            }
                                        },
                                        "current_value": 0,
                                        "labels": ["None", "Home", "Away", "Sleep"],
                                        "options": [
                                            {"label": "None", "value": 0},
                                            {"label": "Home", "value": 1},
                                            {"label": "Away", "value": 2},
                                            {"label": "Sleep", "value": 3},
                                        ],
                                        "title": "Preset",
                                        "type": "preset_selected",
                                        "values": [0, 1, 2, 3],
                                    },
                                    {
                                        "_links": {
                                            "self": {
                                                "href": (
                                                    "https://www.mynexia.com/mobile"
                                                    "/xxl_zones/83394130/zone_mode"
                                                )
                                            }
                                        },
                                        "current_value": "AUTO",
                                        "labels": ["Auto", "Cooling", "Heating", "Off"],
                                        "options": [
                                            {"label": "Auto", "value": "AUTO"},
                                            {"label": "Cooling", "value": "COOL"},
                                            {"label": "Heating", "value": "HEAT"},
                                            {"label": "Off", "value": "OFF"},
                                        ],
                                        "title": "Zone Mode",
                                        "type": "zone_mode",
                                        "values": ["AUTO", "COOL", "HEAT", "OFF"],
                                    },
                                    {
                                        "_links": {
                                            "self": {
                                                "href": (
                                                    "https://www.mynexia.com/mobile"
                                                    "/xxl_zones/83394130/run_mode"
                                                )
                                            }
                                        },
                                        "current_value": "permanent_hold",
                                        "labels": [
                                            "Permanent Hold",
                                            "Run Schedule",
                                        ],
                                        "options": [
                                            {
                                                "label": "Permanent Hold",
                                                "value": "permanent_hold",
                                            },
                                            {
                                                "label": "Run Schedule",
                                                "value": "run_schedule",
                                            },
                                        ],
                                        "title": "Run Mode",
                                        "type": "run_mode",
                                        "values": ["permanent_hold", "run_schedule"],
                                    },
                                    {
                                        "_links": {
                                            "self": {
                                                "href": (
                                                    "https://www.mynexia.com/mobile"
                                                    "/xxl_zones/83394130"
                                                    "/scheduling_enabled"
                                                )
                                            }
                                        },
                                        "current_value": True,
                                        "labels": ["ON", "OFF"],
                                        "options": [
                                            {"label": "ON", "value": True},
                                            {"label": "OFF", "value": False},
                                        ],
                                        "title": "Scheduling",
                                        "type": "scheduling_enabled",
                                        "values": [True, False],
                                    },
                                ],
                                "temperature": 74,
                                "type": "xxl_zone",
                                "zone_status": "Damper Open",
                            },
                            {
                                "_links": {
                                    "self": {
                                        "href": (
                                            "https://www.mynexia.com/mobile"
                                            "/xxl_zones/83394136"
                                        )
                                    }
                                },
                                "cooling_setpoint": 79,
                                "current_zone_mode": "AUTO",
                                "features": [
                                    {
                                        "actions": {
                                            "set_cool_setpoint": {
                                                "href": (
                                                    "https://www.mynexia.com/mobile"
                                                    "/xxl_zones/83394136/setpoints"
                                                )
                                            },
                                            "set_heat_setpoint": {
                                                "href": (
                                                    "https://www.mynexia.com/mobile"
                                                    "/xxl_zones/83394136/setpoints"
                                                )
                                            },
                                        },
                                        "name": "thermostat",
                                        "scale": "f",
                                        "setpoint_cool": 79,
                                        "setpoint_cool_max": 99,
                                        "setpoint_cool_min": 60,
                                        "setpoint_delta": 3,
                                        "setpoint_heat": 63,
                                        "setpoint_heat_max": 90,
                                        "setpoint_heat_min": 55,
                                        "setpoint_increment": 1.0,
                                        "status": "Relieving Air",
                                        "status_icon": {
                                            "modifiers": [],
                                            "name": "cooling",
                                        },
                                        "system_status": "Cooling",
                                        "temperature": 73,
                                    },
                                    {
                                        "is_connected": True,
                                        "name": "connection",
                                        "signal_strength": "unknown",
                                    },
                                    {
                                        "actions": {
                                            "update_thermostat_mode": {
                                                "href": (
                                                    "https://www.mynexia.com/mobile"
                                                    "/xxl_zones/83394136/zone_mode"
                                                ),
                                                "method": "POST",
                                            }
                                        },
                                        "display_value": "Auto",
                                        "label": "Zone Mode",
                                        "name": "thermostat_mode",
                                        "options": [
                                            {
                                                "header": True,
                                                "id": "thermostat_mode",
                                                "label": "Zone Mode",
                                                "value": "thermostat_mode",
                                            },
                                            {"label": "Auto", "value": "AUTO"},
                                            {"label": "Cooling", "value": "COOL"},
                                            {"label": "Heating", "value": "HEAT"},
                                            {"label": "Off", "value": "OFF"},
                                        ],
                                        "value": "AUTO",
                                    },
                                    {
                                        "actions": {
                                            "update_thermostat_run_mode": {
                                                "href": (
                                                    "https://www.mynexia.com/mobile"
                                                    "/xxl_zones/83394136/run_mode"
                                                ),
                                                "method": "POST",
                                            }
                                        },
                                        "display_value": "Hold",
                                        "label": "Run Mode",
                                        "name": "thermostat_run_mode",
                                        "options": [
                                            {
                                                "header": True,
                                                "id": "thermostat_run_mode",
                                                "label": "Run Mode",
                                                "value": "thermostat_run_mode",
                                            },
                                            {
                                                "id": "info_text",
                                                "info": True,
                                                "label": (
                                                    "Follow or override the schedule."
                                                ),
                                                "value": "info_text",
                                            },
                                            {
                                                "label": "Permanent Hold",
                                                "value": "permanent_hold",
                                            },
                                            {
                                                "label": "Run Schedule",
                                                "value": "run_schedule",
                                            },
                                        ],
                                        "value": "permanent_hold",
                                    },
                                    {
                                        "actions": {
                                            "enable_scheduling": {
                                                "data": {"value": True},
                                                "href": (
                                                    "https://www.mynexia.com/mobile"
                                                    "/xxl_zones/83394136"
                                                    "/scheduling_enabled"
                                                ),
                                                "method": "POST",
                                            },
                                            "get_active_schedule": {
                                                "href": (
                                                    "https://www.mynexia.com/mobile"
                                                    "/thermostat_schedules"
                                                    "/get_active_schedule"
                                                    "?device_identifier"
                                                    "=XxlZone-83394136"
                                                ),
                                                "method": "POST",
                                            },
                                            "get_default_schedule": {
                                                "href": (
                                                    "https://www.mynexia.com/mobile"
                                                    "/thermostat_schedules"
                                                    "/get_default_schedule"
                                                    "?device_identifier"
                                                    "=XxlZone-83394136"
                                                ),
                                                "method": "GET",
                                            },
                                            "set_active_schedule": {
                                                "href": (
                                                    "https://www.mynexia.com/mobile"
                                                    "/thermostat_schedules"
                                                    "/set_active_schedule"
                                                    "?device_identifier"
                                                    "=XxlZone-83394136"
                                                ),
                                                "method": "POST",
                                            },
                                        },
                                        "can_add_remove_periods": True,
                                        "collection_url": (
                                            "https://www.mynexia.com/mobile/schedules"
                                            "?device_identifier=XxlZone-83394136"
                                            "&house_id=123456"
                                        ),
                                        "enabled": True,
                                        "max_period_name_length": 10,
                                        "max_periods_per_day": 4,
                                        "name": "schedule",
                                        "setpoint_increment": 1,
                                    },
                                ],
                                "heating_setpoint": 63,
                                "icon": {
                                    "modifiers": ["temperature-73"],
                                    "name": "thermostat",
                                },
                                "id": 83394136,
                                "name": "Nick Office",
                                "operating_state": "Relieving Air",
                                "setpoints": {"cool": 79, "heat": 63},
                                "settings": [
                                    {
                                        "_links": {
                                            "self": {
                                                "href": (
                                                    "https://www.mynexia.com/mobile"
                                                    "/xxl_zones/83394136/preset_selected"
                                                )
                                            }
                                        },
                                        "current_value": 0,
                                        "labels": ["None", "Home", "Away", "Sleep"],
                                        "options": [
                                            {"label": "None", "value": 0},
                                            {"label": "Home", "value": 1},
                                            {"label": "Away", "value": 2},
                                            {"label": "Sleep", "value": 3},
                                        ],
                                        "title": "Preset",
                                        "type": "preset_selected",
                                        "values": [0, 1, 2, 3],
                                    },
                                    {
                                        "_links": {
                                            "self": {
                                                "href": (
                                                    "https://www.mynexia.com/mobile"
                                                    "/xxl_zones/83394136/zone_mode"
                                                )
                                            }
                                        },
                                        "current_value": "AUTO",
                                        "labels": ["Auto", "Cooling", "Heating", "Off"],
                                        "options": [
                                            {"label": "Auto", "value": "AUTO"},
                                            {"label": "Cooling", "value": "COOL"},
                                            {"label": "Heating", "value": "HEAT"},
                                            {"label": "Off", "value": "OFF"},
                                        ],
                                        "title": "Zone Mode",
                                        "type": "zone_mode",
                                        "values": ["AUTO", "COOL", "HEAT", "OFF"],
                                    },
                                    {
                                        "_links": {
                                            "self": {
                                                "href": (
                                                    "https://www.mynexia.com/mobile"
                                                    "/xxl_zones/83394136/run_mode"
                                                )
                                            }
                                        },
                                        "current_value": "permanent_hold",
                                        "labels": [
                                            "Permanent Hold",
                                            "Run Schedule",
                                        ],
                                        "options": [
                                            {
                                                "label": "Permanent Hold",
                                                "value": "permanent_hold",
                                            },
                                            {
                                                "label": "Run Schedule",
                                                "value": "run_schedule",
                                            },
                                        ],
                                        "title": "Run Mode",
                                        "type": "run_mode",
                                        "values": ["permanent_hold", "run_schedule"],
                                    },
                                    {
                                        "_links": {
                                            "self": {
                                                "href": (
                                                    "https://www.mynexia.com/mobile"
                                                    "/xxl_zones/83394136/scheduling_enabled"
                                                )
                                            }
                                        },
                                        "current_value": True,
                                        "labels": ["ON", "OFF"],
                                        "options": [
                                            {"label": "ON", "value": True},
                                            {"label": "OFF", "value": False},
                                        ],
                                        "title": "Scheduling",
                                        "type": "scheduling_enabled",
                                        "values": [True, False],
                                    },
                                ],
                                "temperature": 73,
                                "type": "xxl_zone",
                                "zone_status": "Relieving Air",
                            },
                            {
                                "_links": {
                                    "self": {
                                        "href": (
                                            "https://www.mynexia.com/mobile"
                                            "/xxl_zones/83394127"
                                        )
                                    }
                                },
                                "cooling_setpoint": 79,
                                "current_zone_mode": "AUTO",
                                "features": [
                                    {
                                        "actions": {
                                            "set_cool_setpoint": {
                                                "href": (
                                                    "https://www.mynexia.com/mobile"
                                                    "/xxl_zones/83394127/setpoints"
                                                )
                                            },
                                            "set_heat_setpoint": {
                                                "href": (
                                                    "https://www.mynexia.com/mobile"
                                                    "/xxl_zones/83394127/setpoints"
                                                )
                                            },
                                        },
                                        "name": "thermostat",
                                        "scale": "f",
                                        "setpoint_cool": 79,
                                        "setpoint_cool_max": 99,
                                        "setpoint_cool_min": 60,
                                        "setpoint_delta": 3,
                                        "setpoint_heat": 63,
                                        "setpoint_heat_max": 90,
                                        "setpoint_heat_min": 55,
                                        "setpoint_increment": 1.0,
                                        "status": "Damper Closed",
                                        "status_icon": {
                                            "modifiers": [],
                                            "name": "cooling",
                                        },
                                        "system_status": "Cooling",
                                        "temperature": 72,
                                    },
                                    {
                                        "is_connected": True,
                                        "name": "connection",
                                        "signal_strength": "unknown",
                                    },
                                    {
                                        "actions": {
                                            "update_thermostat_mode": {
                                                "href": (
                                                    "https://www.mynexia.com/mobile"
                                                    "/xxl_zones/83394127/zone_mode"
                                                ),
                                                "method": "POST",
                                            }
                                        },
                                        "display_value": "Auto",
                                        "label": "Zone Mode",
                                        "name": "thermostat_mode",
                                        "options": [
                                            {
                                                "header": True,
                                                "id": "thermostat_mode",
                                                "label": "Zone Mode",
                                                "value": "thermostat_mode",
                                            },
                                            {"label": "Auto", "value": "AUTO"},
                                            {"label": "Cooling", "value": "COOL"},
                                            {"label": "Heating", "value": "HEAT"},
                                            {"label": "Off", "value": "OFF"},
                                        ],
                                        "value": "AUTO",
                                    },
                                    {
                                        "actions": {
                                            "update_thermostat_run_mode": {
                                                "href": (
                                                    "https://www.mynexia.com/mobile"
                                                    "/xxl_zones/83394127/run_mode"
                                                ),
                                                "method": "POST",
                                            }
                                        },
                                        "display_value": "Hold",
                                        "label": "Run Mode",
                                        "name": "thermostat_run_mode",
                                        "options": [
                                            {
                                                "header": True,
                                                "id": "thermostat_run_mode",
                                                "label": "Run Mode",
                                                "value": "thermostat_run_mode",
                                            },
                                            {
                                                "id": "info_text",
                                                "info": True,
                                                "label": (
                                                    "Follow or override the schedule."
                                                ),
                                                "value": "info_text",
                                            },
                                            {
                                                "label": "Permanent Hold",
                                                "value": "permanent_hold",
                                            },
                                            {
                                                "label": "Run Schedule",
                                                "value": "run_schedule",
                                            },
                                        ],
                                        "value": "permanent_hold",
                                    },
                                    {
                                        "actions": {
                                            "enable_scheduling": {
                                                "data": {"value": True},
                                                "href": (
                                                    "https://www.mynexia.com/mobile"
                                                    "/xxl_zones/83394127"
                                                    "/scheduling_enabled"
                                                ),
                                                "method": "POST",
                                            },
                                            "get_active_schedule": {
                                                "href": (
                                                    "https://www.mynexia.com/mobile"
                                                    "/thermostat_schedules"
                                                    "/get_active_schedule"
                                                    "?device_identifier"
                                                    "=XxlZone-83394127"
                                                ),
                                                "method": "POST",
                                            },
                                            "get_default_schedule": {
                                                "href": (
                                                    "https://www.mynexia.com/mobile"
                                                    "/thermostat_schedules"
                                                    "/get_default_schedule"
                                                    "?device_identifier"
                                                    "=XxlZone-83394127"
                                                ),
                                                "method": "GET",
                                            },
                                            "set_active_schedule": {
                                                "href": (
                                                    "https://www.mynexia.com/mobile"
                                                    "/thermostat_schedules"
                                                    "/set_active_schedule"
                                                    "?device_identifier"
                                                    "=XxlZone-83394127"
                                                ),
                                                "method": "POST",
                                            },
                                        },
                                        "can_add_remove_periods": True,
                                        "collection_url": (
                                            "https://www.mynexia.com/mobile/schedules"
                                            "?device_identifier=XxlZone-83394127"
                                            "&house_id=123456"
                                        ),
                                        "enabled": True,
                                        "max_period_name_length": 10,
                                        "max_periods_per_day": 4,
                                        "name": "schedule",
                                        "setpoint_increment": 1,
                                    },
                                ],
                                "heating_setpoint": 63,
                                "icon": {
                                    "modifiers": ["temperature-72"],
                                    "name": "thermostat",
                                },
                                "id": 83394127,
                                "name": "Snooze Room",
                                "operating_state": "Damper Closed",
                                "setpoints": {"cool": 79, "heat": 63},
                                "settings": [
                                    {
                                        "_links": {
                                            "self": {
                                                "href": (
                                                    "https://www.mynexia.com/mobile"
                                                    "/xxl_zones/83394127"
                                                    "/preset_selected"
                                                )
                                            }
                                        },
                                        "current_value": 0,
                                        "labels": ["None", "Home", "Away", "Sleep"],
                                        "options": [
                                            {"label": "None", "value": 0},
                                            {"label": "Home", "value": 1},
                                            {"label": "Away", "value": 2},
                                            {"label": "Sleep", "value": 3},
                                        ],
                                        "title": "Preset",
                                        "type": "preset_selected",
                                        "values": [0, 1, 2, 3],
                                    },
                                    {
                                        "_links": {
                                            "self": {
                                                "href": (
                                                    "https://www.mynexia.com/mobile"
                                                    "/xxl_zones/83394127/zone_mode"
                                                )
                                            }
                                        },
                                        "current_value": "AUTO",
                                        "labels": ["Auto", "Cooling", "Heating", "Off"],
                                        "options": [
                                            {"label": "Auto", "value": "AUTO"},
                                            {"label": "Cooling", "value": "COOL"},
                                            {"label": "Heating", "value": "HEAT"},
                                            {"label": "Off", "value": "OFF"},
                                        ],
                                        "title": "Zone Mode",
                                        "type": "zone_mode",
                                        "values": ["AUTO", "COOL", "HEAT", "OFF"],
                                    },
                                    {
                                        "_links": {
                                            "self": {
                                                "href": (
                                                    "https://www.mynexia.com/mobile"
                                                    "/xxl_zones/83394127/run_mode"
                                                )
                                            }
                                        },
                                        "current_value": "permanent_hold",
                                        "labels": [
                                            "Permanent Hold",
                                            "Run Schedule",
                                        ],
                                        "options": [
                                            {
                                                "label": "Permanent Hold",
                                                "value": "permanent_hold",
                                            },
                                            {
                                                "label": "Run Schedule",
                                                "value": "run_schedule",
                                            },
                                        ],
                                        "title": "Run Mode",
                                        "type": "run_mode",
                                        "values": ["permanent_hold", "run_schedule"],
                                    },
                                    {
                                        "_links": {
                                            "self": {
                                                "href": (
                                                    "https://www.mynexia.com/mobile"
                                                    "/xxl_zones/83394127"
                                                    "/scheduling_enabled"
                                                )
                                            }
                                        },
                                        "current_value": True,
                                        "labels": ["ON", "OFF"],
                                        "options": [
                                            {"label": "ON", "value": True},
                                            {"label": "OFF", "value": False},
                                        ],
                                        "title": "Scheduling",
                                        "type": "scheduling_enabled",
                                        "values": [True, False],
                                    },
                                ],
                                "temperature": 72,
                                "type": "xxl_zone",
                                "zone_status": "Damper Closed",
                            },
                            {
                                "_links": {
                                    "self": {
                                        "href": (
                                            "https://www.mynexia.com/mobile"
                                            "/xxl_zones/83394139"
                                        )
                                    }
                                },
                                "cooling_setpoint": 79,
                                "current_zone_mode": "AUTO",
                                "features": [
                                    {
                                        "actions": {
                                            "set_cool_setpoint": {
                                                "href": (
                                                    "https://www.mynexia.com/mobile"
                                                    "/xxl_zones/83394139/setpoints"
                                                )
                                            },
                                            "set_heat_setpoint": {
                                                "href": (
                                                    "https://www.mynexia.com/mobile"
                                                    "/xxl_zones/83394139/setpoints"
                                                )
                                            },
                                        },
                                        "name": "thermostat",
                                        "scale": "f",
                                        "setpoint_cool": 79,
                                        "setpoint_cool_max": 99,
                                        "setpoint_cool_min": 60,
                                        "setpoint_delta": 3,
                                        "setpoint_heat": 63,
                                        "setpoint_heat_max": 90,
                                        "setpoint_heat_min": 55,
                                        "setpoint_increment": 1.0,
                                        "status": "Damper Closed",
                                        "status_icon": {
                                            "modifiers": [],
                                            "name": "cooling",
                                        },
                                        "system_status": "Cooling",
                                        "temperature": 74,
                                    },
                                    {
                                        "is_connected": True,
                                        "name": "connection",
                                        "signal_strength": "unknown",
                                    },
                                    {
                                        "actions": {
                                            "update_thermostat_mode": {
                                                "href": (
                                                    "https://www.mynexia.com/mobile"
                                                    "/xxl_zones/83394139/zone_mode"
                                                ),
                                                "method": "POST",
                                            }
                                        },
                                        "display_value": "Auto",
                                        "label": "Zone Mode",
                                        "name": "thermostat_mode",
                                        "options": [
                                            {
                                                "header": True,
                                                "id": "thermostat_mode",
                                                "label": "Zone Mode",
                                                "value": "thermostat_mode",
                                            },
                                            {"label": "Auto", "value": "AUTO"},
                                            {"label": "Cooling", "value": "COOL"},
                                            {"label": "Heating", "value": "HEAT"},
                                            {"label": "Off", "value": "OFF"},
                                        ],
                                        "value": "AUTO",
                                    },
                                    {
                                        "actions": {
                                            "update_thermostat_run_mode": {
                                                "href": (
                                                    "https://www.mynexia.com/mobile"
                                                    "/xxl_zones/83394139/run_mode"
                                                ),
                                                "method": "POST",
                                            }
                                        },
                                        "display_value": "Hold",
                                        "label": "Run Mode",
                                        "name": "thermostat_run_mode",
                                        "options": [
                                            {
                                                "header": True,
                                                "id": "thermostat_run_mode",
                                                "label": "Run Mode",
                                                "value": "thermostat_run_mode",
                                            },
                                            {
                                                "id": "info_text",
                                                "info": True,
                                                "label": (
                                                    "Follow or override the schedule."
                                                ),
                                                "value": "info_text",
                                            },
                                            {
                                                "label": "Permanent Hold",
                                                "value": "permanent_hold",
                                            },
                                            {
                                                "label": "Run Schedule",
                                                "value": "run_schedule",
                                            },
                                        ],
                                        "value": "permanent_hold",
                                    },
                                    {
                                        "actions": {
                                            "enable_scheduling": {
                                                "data": {"value": True},
                                                "href": (
                                                    "https://www.mynexia.com/mobile"
                                                    "/xxl_zones/83394139"
                                                    "/scheduling_enabled"
                                                ),
                                                "method": "POST",
                                            },
                                            "get_active_schedule": {
                                                "href": (
                                                    "https://www.mynexia.com/mobile"
                                                    "/thermostat_schedules"
                                                    "/get_active_schedule"
                                                    "?device_identifier"
                                                    "=XxlZone-83394139"
                                                ),
                                                "method": "POST",
                                            },
                                            "get_default_schedule": {
                                                "href": (
                                                    "https://www.mynexia.com/mobile"
                                                    "/thermostat_schedules"
                                                    "/get_default_schedule"
                                                    "?device_identifier"
                                                    "=XxlZone-83394139"
                                                ),
                                                "method": "GET",
                                            },
                                            "set_active_schedule": {
                                                "href": (
                                                    "https://www.mynexia.com/mobile"
                                                    "/thermostat_schedules"
                                                    "/set_active_schedule"
                                                    "?device_identifier"
                                                    "=XxlZone-83394139"
                                                ),
                                                "method": "POST",
                                            },
                                        },
                                        "can_add_remove_periods": True,
                                        "collection_url": (
                                            "https://www.mynexia.com/mobile/schedules"
                                            "?device_identifier=XxlZone-83394139"
                                            "&house_id=123456"
                                        ),
                                        "enabled": True,
                                        "max_period_name_length": 10,
                                        "max_periods_per_day": 4,
                                        "name": "schedule",
                                        "setpoint_increment": 1,
                                    },
                                ],
                                "heating_setpoint": 63,
                                "icon": {
                                    "modifiers": ["temperature-74"],
                                    "name": "thermostat",
                                },
                                "id": 83394139,
                                "name": "Safe Room",
                                "operating_state": "Damper Closed",
                                "setpoints": {"cool": 79, "heat": 63},
                                "settings": [
                                    {
                                        "_links": {
                                            "self": {
                                                "href": (
                                                    "https://www.mynexia.com/mobile"
                                                    "/xxl_zones/83394139"
                                                    "/preset_selected"
                                                )
                                            }
                                        },
                                        "current_value": 0,
                                        "labels": ["None", "Home", "Away", "Sleep"],
                                        "options": [
                                            {"label": "None", "value": 0},
                                            {"label": "Home", "value": 1},
                                            {"label": "Away", "value": 2},
                                            {"label": "Sleep", "value": 3},
                                        ],
                                        "title": "Preset",
                                        "type": "preset_selected",
                                        "values": [0, 1, 2, 3],
                                    },
                                    {
                                        "_links": {
                                            "self": {
                                                "href": (
                                                    "https://www.mynexia.com/mobile"
                                                    "/xxl_zones/83394139/zone_mode"
                                                )
                                            }
                                        },
                                        "current_value": "AUTO",
                                        "labels": ["Auto", "Cooling", "Heating", "Off"],
                                        "options": [
                                            {"label": "Auto", "value": "AUTO"},
                                            {"label": "Cooling", "value": "COOL"},
                                            {"label": "Heating", "value": "HEAT"},
                                            {"label": "Off", "value": "OFF"},
                                        ],
                                        "title": "Zone Mode",
                                        "type": "zone_mode",
                                        "values": ["AUTO", "COOL", "HEAT", "OFF"],
                                    },
                                    {
                                        "_links": {
                                            "self": {
                                                "href": (
                                                    "https://www.mynexia.com/mobile"
                                                    "/xxl_zones/83394139/run_mode"
                                                )
                                            }
                                        },
                                        "current_value": "permanent_hold",
                                        "labels": [
                                            "Permanent Hold",
                                            "Run Schedule",
                                        ],
                                        "options": [
                                            {
                                                "label": "Permanent Hold",
                                                "value": "permanent_hold",
                                            },
                                            {
                                                "label": "Run Schedule",
                                                "value": "run_schedule",
                                            },
                                        ],
                                        "title": "Run Mode",
                                        "type": "run_mode",
                                        "values": ["permanent_hold", "run_schedule"],
                                    },
                                    {
                                        "_links": {
                                            "self": {
                                                "href": (
                                                    "https://www.mynexia.com/mobile"
                                                    "/xxl_zones/83394139"
                                                    "/scheduling_enabled"
                                                )
                                            }
                                        },
                                        "current_value": True,
                                        "labels": ["ON", "OFF"],
                                        "options": [
                                            {"label": "ON", "value": True},
                                            {"label": "OFF", "value": False},
                                        ],
                                        "title": "Scheduling",
                                        "type": "scheduling_enabled",
                                        "values": [True, False],
                                    },
                                ],
                                "temperature": 74,
                                "type": "xxl_zone",
                                "zone_status": "Damper Closed",
                            },
                        ],
                        "name": "group",
                    },
                    {
                        "actions": {
                            "update_thermostat_fan_mode": {
                                "href": (
                                    "https://www.mynexia.com/mobile"
                                    "/xxl_thermostats/2293892/fan_mode"
                                ),
                                "method": "POST",
                            }
                        },
                        "display_value": "Auto",
                        "label": "Fan Mode",
                        "name": "thermostat_fan_mode",
                        "options": [
                            {
                                "header": True,
                                "id": "thermostat_fan_mode",
                                "label": "Fan Mode",
                                "value": "thermostat_fan_mode",
                            },
                            {"label": "Auto", "value": "auto"},
                            {"label": "On", "value": "on"},
                            {"label": "Circulate", "value": "circulate"},
                        ],
                        "status_icon": {"modifiers": [], "name": "thermostat_fan_on"},
                        "value": "auto",
                    },
                    {"compressor_speed": 0.69, "name": "thermostat_compressor_speed"},
                    {
                        "actions": {
                            "get_monthly_runtime_history": {
                                "href": (
                                    "https://www.mynexia.com/mobile/runtime_history"
                                    "/2293892?report_type=monthly"
                                ),
                                "method": "GET",
                            },
                            "get_runtime_history": {
                                "href": (
                                    "https://www.mynexia.com/mobile/runtime_history"
                                    "/2293892?report_type=daily"
                                ),
                                "method": "GET",
                            },
                        },
                        "name": "runtime_history",
                    },
                ],
                "has_indoor_humidity": True,
                "has_outdoor_temperature": True,
                "icon": [
                    {"modifiers": ["temperature-73"], "name": "thermostat"},
                    {"modifiers": ["temperature-74"], "name": "thermostat"},
                    {"modifiers": ["temperature-73"], "name": "thermostat"},
                    {"modifiers": ["temperature-72"], "name": "thermostat"},
                    {"modifiers": ["temperature-74"], "name": "thermostat"},
                ],
                "id": 2293892,
                "indoor_humidity": "52",
                "last_updated_at": "2020-03-11T15:15:53.000-05:00",
                "name": "Master Suite",
                "name_editable": True,
                "outdoor_temperature": "87",
                "settings": [
                    {
                        "_links": {
                            "self": {
                                "href": (
                                    "https://www.mynexia.com/mobile/xxl_thermostats"
                                    "/2293892/fan_mode"
                                )
                            }
                        },
                        "current_value": "auto",
                        "labels": ["Auto", "On", "Circulate"],
                        "options": [
                            {"label": "Auto", "value": "auto"},
                            {"label": "On", "value": "on"},
                            {"label": "Circulate", "value": "circulate"},
                        ],
                        "title": "Fan Mode",
                        "type": "fan_mode",
                        "values": ["auto", "on", "circulate"],
                    },
                    {
                        "_links": {
                            "self": {
                                "href": (
                                    "https://www.mynexia.com/mobile/xxl_thermostats"
                                    "/2293892/fan_speed"
                                )
                            }
                        },
                        "current_value": 0.35,
                        "labels": [
                            "35%",
                            "40%",
                            "45%",
                            "50%",
                            "55%",
                            "60%",
                            "65%",
                            "70%",
                            "75%",
                            "80%",
                            "85%",
                            "90%",
                            "95%",
                            "100%",
                        ],
                        "options": [
                            {"label": "35%", "value": 0.35},
                            {"label": "40%", "value": 0.4},
                            {"label": "45%", "value": 0.45},
                            {"label": "50%", "value": 0.5},
                            {"label": "55%", "value": 0.55},
                            {"label": "60%", "value": 0.6},
                            {"label": "65%", "value": 0.65},
                            {"label": "70%", "value": 0.7},
                            {"label": "75%", "value": 0.75},
                            {"label": "80%", "value": 0.8},
                            {"label": "85%", "value": 0.85},
                            {"label": "90%", "value": 0.9},
                            {"label": "95%", "value": 0.95},
                            {"label": "100%", "value": 1.0},
                        ],
                        "title": "Fan Speed",
                        "type": "fan_speed",
                        "values": [
                            0.35,
                            0.4,
                            0.45,
                            0.5,
                            0.55,
                            0.6,
                            0.65,
                            0.7,
                            0.75,
                            0.8,
                            0.85,
                            0.9,
                            0.95,
                            1.0,
                        ],
                    },
                    {
                        "_links": {
                            "self": {
                                "href": (
                                    "https://www.mynexia.com/mobile/xxl_thermostats"
                                    "/2293892/fan_circulation_time"
                                )
                            }
                        },
                        "current_value": 30,
                        "labels": [
                            "10 minutes",
                            "15 minutes",
                            "20 minutes",
                            "25 minutes",
                            "30 minutes",
                            "35 minutes",
                            "40 minutes",
                            "45 minutes",
                            "50 minutes",
                            "55 minutes",
                        ],
                        "options": [
                            {"label": "10 minutes", "value": 10},
                            {"label": "15 minutes", "value": 15},
                            {"label": "20 minutes", "value": 20},
                            {"label": "25 minutes", "value": 25},
                            {"label": "30 minutes", "value": 30},
                            {"label": "35 minutes", "value": 35},
                            {"label": "40 minutes", "value": 40},
                            {"label": "45 minutes", "value": 45},
                            {"label": "50 minutes", "value": 50},
                            {"label": "55 minutes", "value": 55},
                        ],
                        "title": "Fan Circulation Time",
                        "type": "fan_circulation_time",
                        "values": [10, 15, 20, 25, 30, 35, 40, 45, 50, 55],
                    },
                    {
                        "_links": {
                            "self": {
                                "href": (
                                    "https://www.mynexia.com/mobile/xxl_thermostats"
                                    "/2293892/air_cleaner_mode"
                                )
                            }
                        },
                        "current_value": "auto",
                        "labels": ["Auto", "Quick", "Allergy"],
                        "options": [
                            {"label": "Auto", "value": "auto"},
                            {"label": "Quick", "value": "quick"},
                            {"label": "Allergy", "value": "allergy"},
                        ],
                        "title": "Air Cleaner Mode",
                        "type": "air_cleaner_mode",
                        "values": ["auto", "quick", "allergy"],
                    },
                    {
                        "_links": {
                            "self": {
                                "href": (
                                    "https://www.mynexia.com/mobile"
                                    "/xxl_thermostats/2293892/dehumidify"
                                )
                            }
                        },
                        "current_value": 0.45,
                        "labels": ["35%", "40%", "45%", "50%", "55%", "60%", "65%"],
                        "options": [
                            {"label": "35%", "value": 0.35},
                            {"label": "40%", "value": 0.4},
                            {"label": "45%", "value": 0.45},
                            {"label": "50%", "value": 0.5},
                            {"label": "55%", "value": 0.55},
                            {"label": "60%", "value": 0.6},
                            {"label": "65%", "value": 0.65},
                        ],
                        "title": "Cooling Dehumidify Set Point",
                        "type": "dehumidify",
                        "values": [0.35, 0.4, 0.45, 0.5, 0.55, 0.6, 0.65],
                    },
                    {
                        "_links": {
                            "self": {
                                "href": (
                                    "https://www.mynexia.com/mobile"
                                    "/xxl_thermostats/2293892/scale"
                                )
                            }
                        },
                        "current_value": "f",
                        "labels": ["F", "C"],
                        "options": [
                            {"label": "F", "value": "f"},
                            {"label": "C", "value": "c"},
                        ],
                        "title": "Temperature Scale",
                        "type": "scale",
                        "values": ["f", "c"],
                    },
                ],
                "status_secondary": None,
                "status_tertiary": None,
                "system_status": "Cooling",
                "type": "xxl_thermostat",
                "zones": [
                    {
                        "_links": {
                            "self": {
                                "href": (
                                    "https://www.mynexia.com/mobile/xxl_zones/83394133"
                                )
                            }
                        },
                        "cooling_setpoint": 79,
                        "current_zone_mode": "AUTO",
                        "features": [
                            {
                                "actions": {
                                    "set_cool_setpoint": {
                                        "href": (
                                            "https://www.mynexia.com/mobile"
                                            "/xxl_zones/83394133/setpoints"
                                        )
                                    },
                                    "set_heat_setpoint": {
                                        "href": (
                                            "https://www.mynexia.com/mobile"
                                            "/xxl_zones/83394133/setpoints"
                                        )
                                    },
                                },
                                "name": "thermostat",
                                "scale": "f",
                                "setpoint_cool": 79,
                                "setpoint_cool_max": 99,
                                "setpoint_cool_min": 60,
                                "setpoint_delta": 3,
                                "setpoint_heat": 63,
                                "setpoint_heat_max": 90,
                                "setpoint_heat_min": 55,
                                "setpoint_increment": 1.0,
                                "status": "Relieving Air",
                                "status_icon": {"modifiers": [], "name": "cooling"},
                                "system_status": "Cooling",
                                "temperature": 73,
                            },
                            {
                                "is_connected": True,
                                "name": "connection",
                                "signal_strength": "unknown",
                            },
                            {
                                "actions": {
                                    "update_thermostat_mode": {
                                        "href": (
                                            "https://www.mynexia.com/mobile"
                                            "/xxl_zones/83394133/zone_mode"
                                        ),
                                        "method": "POST",
                                    }
                                },
                                "display_value": "Auto",
                                "label": "Zone Mode",
                                "name": "thermostat_mode",
                                "options": [
                                    {
                                        "header": True,
                                        "id": "thermostat_mode",
                                        "label": "Zone Mode",
                                        "value": "thermostat_mode",
                                    },
                                    {"label": "Auto", "value": "AUTO"},
                                    {"label": "Cooling", "value": "COOL"},
                                    {"label": "Heating", "value": "HEAT"},
                                    {"label": "Off", "value": "OFF"},
                                ],
                                "value": "AUTO",
                            },
                            {
                                "actions": {
                                    "update_thermostat_run_mode": {
                                        "href": (
                                            "https://www.mynexia.com/mobile"
                                            "/xxl_zones/83394133/run_mode"
                                        ),
                                        "method": "POST",
                                    }
                                },
                                "display_value": "Hold",
                                "label": "Run Mode",
                                "name": "thermostat_run_mode",
                                "options": [
                                    {
                                        "header": True,
                                        "id": "thermostat_run_mode",
                                        "label": "Run Mode",
                                        "value": "thermostat_run_mode",
                                    },
                                    {
                                        "id": "info_text",
                                        "info": True,
                                        "label": "Follow or override the schedule.",
                                        "value": "info_text",
                                    },
                                    {
                                        "label": "Permanent Hold",
                                        "value": "permanent_hold",
                                    },
                                    {"label": "Run Schedule", "value": "run_schedule"},
                                ],
                                "value": "permanent_hold",
                            },
                            {
                                "actions": {
                                    "enable_scheduling": {
                                        "data": {"value": True},
                                        "href": (
                                            "https://www.mynexia.com/mobile/xxl_zones"
                                            "/83394133/scheduling_enabled"
                                        ),
                                        "method": "POST",
                                    },
                                    "get_active_schedule": {
                                        "href": (
                                            "https://www.mynexia.com/mobile"
                                            "/thermostat_schedules"
                                            "/get_active_schedule"
                                            "?device_identifier"
                                            "=XxlZone-83394133"
                                        ),
                                        "method": "POST",
                                    },
                                    "get_default_schedule": {
                                        "href": (
                                            "https://www.mynexia.com/mobile"
                                            "/thermostat_schedules"
                                            "/get_default_schedule"
                                            "?device_identifier"
                                            "=XxlZone-83394133"
                                        ),
                                        "method": "GET",
                                    },
                                    "set_active_schedule": {
                                        "href": (
                                            "https://www.mynexia.com/mobile"
                                            "/thermostat_schedules"
                                            "/set_active_schedule"
                                            "?device_identifier"
                                            "=XxlZone-83394133"
                                        ),
                                        "method": "POST",
                                    },
                                },
                                "can_add_remove_periods": True,
                                "collection_url": (
                                    "https://www.mynexia.com/mobile/schedules"
                                    "?device_identifier=XxlZone-83394133"
                                    "&house_id=123456"
                                ),
                                "enabled": True,
                                "max_period_name_length": 10,
                                "max_periods_per_day": 4,
                                "name": "schedule",
                                "setpoint_increment": 1,
                            },
                        ],
                        "heating_setpoint": 63,
                        "icon": {"modifiers": ["temperature-73"], "name": "thermostat"},
                        "id": 83394133,
                        "name": "Bath Closet",
                        "operating_state": "Relieving Air",
                        "setpoints": {"cool": 79, "heat": 63},
                        "settings": [
                            {
                                "_links": {
                                    "self": {
                                        "href": (
                                            "https://www.mynexia.com/mobile"
                                            "/xxl_zones/83394133/preset_selected"
                                        )
                                    }
                                },
                                "current_value": 0,
                                "labels": ["None", "Home", "Away", "Sleep"],
                                "options": [
                                    {"label": "None", "value": 0},
                                    {"label": "Home", "value": 1},
                                    {"label": "Away", "value": 2},
                                    {"label": "Sleep", "value": 3},
                                ],
                                "title": "Preset",
                                "type": "preset_selected",
                                "values": [0, 1, 2, 3],
                            },
                            {
                                "_links": {
                                    "self": {
                                        "href": (
                                            "https://www.mynexia.com/mobile"
                                            "/xxl_zones/83394133/zone_mode"
                                        )
                                    }
                                },
                                "current_value": "AUTO",
                                "labels": ["Auto", "Cooling", "Heating", "Off"],
                                "options": [
                                    {"label": "Auto", "value": "AUTO"},
                                    {"label": "Cooling", "value": "COOL"},
                                    {"label": "Heating", "value": "HEAT"},
                                    {"label": "Off", "value": "OFF"},
                                ],
                                "title": "Zone Mode",
                                "type": "zone_mode",
                                "values": ["AUTO", "COOL", "HEAT", "OFF"],
                            },
                            {
                                "_links": {
                                    "self": {
                                        "href": (
                                            "https://www.mynexia.com/mobile"
                                            "/xxl_zones/83394133/run_mode"
                                        )
                                    }
                                },
                                "current_value": "permanent_hold",
                                "labels": ["Permanent Hold", "Run Schedule"],
                                "options": [
                                    {
                                        "label": "Permanent Hold",
                                        "value": "permanent_hold",
                                    },
                                    {"label": "Run Schedule", "value": "run_schedule"},
                                ],
                                "title": "Run Mode",
                                "type": "run_mode",
                                "values": ["permanent_hold", "run_schedule"],
                            },
                            {
                                "_links": {
                                    "self": {
                                        "href": (
                                            "https://www.mynexia.com/mobile"
                                            "/xxl_zones/83394133/scheduling_enabled"
                                        )
                                    }
                                },
                                "current_value": True,
                                "labels": ["ON", "OFF"],
                                "options": [
                                    {"label": "ON", "value": True},
                                    {"label": "OFF", "value": False},
                                ],
                                "title": "Scheduling",
                                "type": "scheduling_enabled",
                                "values": [True, False],
                            },
                        ],
                        "temperature": 73,
                        "type": "xxl_zone",
                        "zone_status": "Relieving Air",
                    },
                    {
                        "_links": {
                            "self": {
                                "href": (
                                    "https://www.mynexia.com/mobile/xxl_zones/83394130"
                                )
                            }
                        },
                        "cooling_setpoint": 71,
                        "current_zone_mode": "AUTO",
                        "features": [
                            {
                                "actions": {
                                    "set_cool_setpoint": {
                                        "href": (
                                            "https://www.mynexia.com/mobile"
                                            "/xxl_zones/83394130/setpoints"
                                        )
                                    },
                                    "set_heat_setpoint": {
                                        "href": (
                                            "https://www.mynexia.com/mobile"
                                            "/xxl_zones/83394130/setpoints"
                                        )
                                    },
                                },
                                "name": "thermostat",
                                "scale": "f",
                                "setpoint_cool": 71,
                                "setpoint_cool_max": 99,
                                "setpoint_cool_min": 60,
                                "setpoint_delta": 3,
                                "setpoint_heat": 63,
                                "setpoint_heat_max": 90,
                                "setpoint_heat_min": 55,
                                "setpoint_increment": 1.0,
                                "status": "Damper Open",
                                "status_icon": {"modifiers": [], "name": "cooling"},
                                "system_status": "Cooling",
                                "temperature": 74,
                            },
                            {
                                "is_connected": True,
                                "name": "connection",
                                "signal_strength": "unknown",
                            },
                            {
                                "actions": {
                                    "update_thermostat_mode": {
                                        "href": (
                                            "https://www.mynexia.com/mobile"
                                            "/xxl_zones/83394130/zone_mode"
                                        ),
                                        "method": "POST",
                                    }
                                },
                                "display_value": "Auto",
                                "label": "Zone Mode",
                                "name": "thermostat_mode",
                                "options": [
                                    {
                                        "header": True,
                                        "id": "thermostat_mode",
                                        "label": "Zone Mode",
                                        "value": "thermostat_mode",
                                    },
                                    {"label": "Auto", "value": "AUTO"},
                                    {"label": "Cooling", "value": "COOL"},
                                    {"label": "Heating", "value": "HEAT"},
                                    {"label": "Off", "value": "OFF"},
                                ],
                                "value": "AUTO",
                            },
                            {
                                "actions": {
                                    "update_thermostat_run_mode": {
                                        "href": (
                                            "https://www.mynexia.com/mobile"
                                            "/xxl_zones/83394130/run_mode"
                                        ),
                                        "method": "POST",
                                    }
                                },
                                "display_value": "Hold",
                                "label": "Run Mode",
                                "name": "thermostat_run_mode",
                                "options": [
                                    {
                                        "header": True,
                                        "id": "thermostat_run_mode",
                                        "label": "Run Mode",
                                        "value": "thermostat_run_mode",
                                    },
                                    {
                                        "id": "info_text",
                                        "info": True,
                                        "label": "Follow or override the schedule.",
                                        "value": "info_text",
                                    },
                                    {
                                        "label": "Permanent Hold",
                                        "value": "permanent_hold",
                                    },
                                    {"label": "Run Schedule", "value": "run_schedule"},
                                ],
                                "value": "permanent_hold",
                            },
                            {
                                "actions": {
                                    "enable_scheduling": {
                                        "data": {"value": True},
                                        "href": (
                                            "https://www.mynexia.com/mobile"
                                            "/xxl_zones/83394130"
                                            "/scheduling_enabled"
                                        ),
                                        "method": "POST",
                                    },
                                    "get_active_schedule": {
                                        "href": (
                                            "https://www.mynexia.com/mobile"
                                            "/thermostat_schedules"
                                            "/get_active_schedule"
                                            "?device_identifier"
                                            "=XxlZone-83394130"
                                        ),
                                        "method": "POST",
                                    },
                                    "get_default_schedule": {
                                        "href": (
                                            "https://www.mynexia.com/mobile"
                                            "/thermostat_schedules"
                                            "/get_default_schedule"
                                            "?device_identifier"
                                            "=XxlZone-83394130"
                                        ),
                                        "method": "GET",
                                    },
                                    "set_active_schedule": {
                                        "href": (
                                            "https://www.mynexia.com/mobile"
                                            "/thermostat_schedules"
                                            "/set_active_schedule"
                                            "?device_identifier"
                                            "=XxlZone-83394130"
                                        ),
                                        "method": "POST",
                                    },
                                },
                                "can_add_remove_periods": True,
                                "collection_url": (
                                    "https://www.mynexia.com/mobile/schedules"
                                    "?device_identifier=XxlZone-83394130"
                                    "&house_id=123456"
                                ),
                                "enabled": True,
                                "max_period_name_length": 10,
                                "max_periods_per_day": 4,
                                "name": "schedule",
                                "setpoint_increment": 1,
                            },
                        ],
                        "heating_setpoint": 63,
                        "icon": {"modifiers": ["temperature-74"], "name": "thermostat"},
                        "id": 83394130,
                        "name": "Master",
                        "operating_state": "Damper Open",
                        "setpoints": {"cool": 71, "heat": 63},
                        "settings": [
                            {
                                "_links": {
                                    "self": {
                                        "href": (
                                            "https://www.mynexia.com/mobile"
                                            "/xxl_zones/83394130/preset_selected"
                                        )
                                    }
                                },
                                "current_value": 0,
                                "labels": ["None", "Home", "Away", "Sleep"],
                                "options": [
                                    {"label": "None", "value": 0},
                                    {"label": "Home", "value": 1},
                                    {"label": "Away", "value": 2},
                                    {"label": "Sleep", "value": 3},
                                ],
                                "title": "Preset",
                                "type": "preset_selected",
                                "values": [0, 1, 2, 3],
                            },
                            {
                                "_links": {
                                    "self": {
                                        "href": (
                                            "https://www.mynexia.com/mobile"
                                            "/xxl_zones/83394130/zone_mode"
                                        )
                                    }
                                },
                                "current_value": "AUTO",
                                "labels": ["Auto", "Cooling", "Heating", "Off"],
                                "options": [
                                    {"label": "Auto", "value": "AUTO"},
                                    {"label": "Cooling", "value": "COOL"},
                                    {"label": "Heating", "value": "HEAT"},
                                    {"label": "Off", "value": "OFF"},
                                ],
                                "title": "Zone Mode",
                                "type": "zone_mode",
                                "values": ["AUTO", "COOL", "HEAT", "OFF"],
                            },
                            {
                                "_links": {
                                    "self": {
                                        "href": (
                                            "https://www.mynexia.com/mobile"
                                            "/xxl_zones/83394130/run_mode"
                                        )
                                    }
                                },
                                "current_value": "permanent_hold",
                                "labels": ["Permanent Hold", "Run Schedule"],
                                "options": [
                                    {
                                        "label": "Permanent Hold",
                                        "value": "permanent_hold",
                                    },
                                    {"label": "Run Schedule", "value": "run_schedule"},
                                ],
                                "title": "Run Mode",
                                "type": "run_mode",
                                "values": ["permanent_hold", "run_schedule"],
                            },
                            {
                                "_links": {
                                    "self": {
                                        "href": (
                                            "https://www.mynexia.com/mobile"
                                            "/xxl_zones/83394130"
                                            "/scheduling_enabled"
                                        )
                                    }
                                },
                                "current_value": True,
                                "labels": ["ON", "OFF"],
                                "options": [
                                    {"label": "ON", "value": True},
                                    {"label": "OFF", "value": False},
                                ],
                                "title": "Scheduling",
                                "type": "scheduling_enabled",
                                "values": [True, False],
                            },
                        ],
                        "temperature": 74,
                        "type": "xxl_zone",
                        "zone_status": "Damper Open",
                    },
                    {
                        "_links": {
                            "self": {
                                "href": (
                                    "https://www.mynexia.com/mobile/xxl_zones/83394136"
                                )
                            }
                        },
                        "cooling_setpoint": 79,
                        "current_zone_mode": "AUTO",
                        "features": [
                            {
                                "actions": {
                                    "set_cool_setpoint": {
                                        "href": (
                                            "https://www.mynexia.com/mobile"
                                            "/xxl_zones/83394136/setpoints"
                                        )
                                    },
                                    "set_heat_setpoint": {
                                        "href": (
                                            "https://www.mynexia.com/mobile"
                                            "/xxl_zones/83394136/setpoints"
                                        )
                                    },
                                },
                                "name": "thermostat",
                                "scale": "f",
                                "setpoint_cool": 79,
                                "setpoint_cool_max": 99,
                                "setpoint_cool_min": 60,
                                "setpoint_delta": 3,
                                "setpoint_heat": 63,
                                "setpoint_heat_max": 90,
                                "setpoint_heat_min": 55,
                                "setpoint_increment": 1.0,
                                "status": "Relieving Air",
                                "status_icon": {"modifiers": [], "name": "cooling"},
                                "system_status": "Cooling",
                                "temperature": 73,
                            },
                            {
                                "is_connected": True,
                                "name": "connection",
                                "signal_strength": "unknown",
                            },
                            {
                                "actions": {
                                    "update_thermostat_mode": {
                                        "href": (
                                            "https://www.mynexia.com/mobile"
                                            "/xxl_zones/83394136/zone_mode"
                                        ),
                                        "method": "POST",
                                    }
                                },
                                "display_value": "Auto",
                                "label": "Zone Mode",
                                "name": "thermostat_mode",
                                "options": [
                                    {
                                        "header": True,
                                        "id": "thermostat_mode",
                                        "label": "Zone Mode",
                                        "value": "thermostat_mode",
                                    },
                                    {"label": "Auto", "value": "AUTO"},
                                    {"label": "Cooling", "value": "COOL"},
                                    {"label": "Heating", "value": "HEAT"},
                                    {"label": "Off", "value": "OFF"},
                                ],
                                "value": "AUTO",
                            },
                            {
                                "actions": {
                                    "update_thermostat_run_mode": {
                                        "href": (
                                            "https://www.mynexia.com/mobile"
                                            "/xxl_zones/83394136/run_mode"
                                        ),
                                        "method": "POST",
                                    }
                                },
                                "display_value": "Hold",
                                "label": "Run Mode",
                                "name": "thermostat_run_mode",
                                "options": [
                                    {
                                        "header": True,
                                        "id": "thermostat_run_mode",
                                        "label": "Run Mode",
                                        "value": "thermostat_run_mode",
                                    },
                                    {
                                        "id": "info_text",
                                        "info": True,
                                        "label": "Follow or override the schedule.",
                                        "value": "info_text",
                                    },
                                    {
                                        "label": "Permanent Hold",
                                        "value": "permanent_hold",
                                    },
                                    {"label": "Run Schedule", "value": "run_schedule"},
                                ],
                                "value": "permanent_hold",
                            },
                            {
                                "actions": {
                                    "enable_scheduling": {
                                        "data": {"value": True},
                                        "href": (
                                            "https://www.mynexia.com/mobile"
                                            "/xxl_zones/83394136/scheduling_enabled"
                                        ),
                                        "method": "POST",
                                    },
                                    "get_active_schedule": {
                                        "href": (
                                            "https://www.mynexia.com/mobile"
                                            "/thermostat_schedules"
                                            "/get_active_schedule"
                                            "?device_identifier"
                                            "=XxlZone-83394136"
                                        ),
                                        "method": "POST",
                                    },
                                    "get_default_schedule": {
                                        "href": (
                                            "https://www.mynexia.com/mobile"
                                            "/thermostat_schedules"
                                            "/get_default_schedule"
                                            "?device_identifier"
                                            "=XxlZone-83394136"
                                        ),
                                        "method": "GET",
                                    },
                                    "set_active_schedule": {
                                        "href": (
                                            "https://www.mynexia.com/mobile"
                                            "/thermostat_schedules"
                                            "/set_active_schedule"
                                            "?device_identifier"
                                            "=XxlZone-83394136"
                                        ),
                                        "method": "POST",
                                    },
                                },
                                "can_add_remove_periods": True,
                                "collection_url": (
                                    "https://www.mynexia.com/mobile/schedules"
                                    "?device_identifier=XxlZone-83394136"
                                    "&house_id=123456"
                                ),
                                "enabled": True,
                                "max_period_name_length": 10,
                                "max_periods_per_day": 4,
                                "name": "schedule",
                                "setpoint_increment": 1,
                            },
                        ],
                        "heating_setpoint": 63,
                        "icon": {"modifiers": ["temperature-73"], "name": "thermostat"},
                        "id": 83394136,
                        "name": "Nick Office",
                        "operating_state": "Relieving Air",
                        "setpoints": {"cool": 79, "heat": 63},
                        "settings": [
                            {
                                "_links": {
                                    "self": {
                                        "href": (
                                            "https://www.mynexia.com/mobile"
                                            "/xxl_zones/83394136/preset_selected"
                                        )
                                    }
                                },
                                "current_value": 0,
                                "labels": ["None", "Home", "Away", "Sleep"],
                                "options": [
                                    {"label": "None", "value": 0},
                                    {"label": "Home", "value": 1},
                                    {"label": "Away", "value": 2},
                                    {"label": "Sleep", "value": 3},
                                ],
                                "title": "Preset",
                                "type": "preset_selected",
                                "values": [0, 1, 2, 3],
                            },
                            {
                                "_links": {
                                    "self": {
                                        "href": (
                                            "https://www.mynexia.com/mobile"
                                            "/xxl_zones/83394136/zone_mode"
                                        )
                                    }
                                },
                                "current_value": "AUTO",
                                "labels": ["Auto", "Cooling", "Heating", "Off"],
                                "options": [
                                    {"label": "Auto", "value": "AUTO"},
                                    {"label": "Cooling", "value": "COOL"},
                                    {"label": "Heating", "value": "HEAT"},
                                    {"label": "Off", "value": "OFF"},
                                ],
                                "title": "Zone Mode",
                                "type": "zone_mode",
                                "values": ["AUTO", "COOL", "HEAT", "OFF"],
                            },
                            {
                                "_links": {
                                    "self": {
                                        "href": (
                                            "https://www.mynexia.com/mobile"
                                            "/xxl_zones/83394136/run_mode"
                                        )
                                    }
                                },
                                "current_value": "permanent_hold",
                                "labels": ["Permanent Hold", "Run Schedule"],
                                "options": [
                                    {
                                        "label": "Permanent Hold",
                                        "value": "permanent_hold",
                                    },
                                    {"label": "Run Schedule", "value": "run_schedule"},
                                ],
                                "title": "Run Mode",
                                "type": "run_mode",
                                "values": ["permanent_hold", "run_schedule"],
                            },
                            {
                                "_links": {
                                    "self": {
                                        "href": (
                                            "https://www.mynexia.com/mobile"
                                            "/xxl_zones/83394136/scheduling_enabled"
                                        )
                                    }
                                },
                                "current_value": True,
                                "labels": ["ON", "OFF"],
                                "options": [
                                    {"label": "ON", "value": True},
                                    {"label": "OFF", "value": False},
                                ],
                                "title": "Scheduling",
                                "type": "scheduling_enabled",
                                "values": [True, False],
                            },
                        ],
                        "temperature": 73,
                        "type": "xxl_zone",
                        "zone_status": "Relieving Air",
                    },
                    {
                        "_links": {
                            "self": {
                                "href": (
                                    "https://www.mynexia.com/mobile/xxl_zones/83394127"
                                )
                            }
                        },
                        "cooling_setpoint": 79,
                        "current_zone_mode": "AUTO",
                        "features": [
                            {
                                "actions": {
                                    "set_cool_setpoint": {
                                        "href": (
                                            "https://www.mynexia.com/mobile"
                                            "/xxl_zones/83394127/setpoints"
                                        )
                                    },
                                    "set_heat_setpoint": {
                                        "href": (
                                            "https://www.mynexia.com/mobile"
                                            "/xxl_zones/83394127/setpoints"
                                        )
                                    },
                                },
                                "name": "thermostat",
                                "scale": "f",
                                "setpoint_cool": 79,
                                "setpoint_cool_max": 99,
                                "setpoint_cool_min": 60,
                                "setpoint_delta": 3,
                                "setpoint_heat": 63,
                                "setpoint_heat_max": 90,
                                "setpoint_heat_min": 55,
                                "setpoint_increment": 1.0,
                                "status": "Damper Closed",
                                "status_icon": {"modifiers": [], "name": "cooling"},
                                "system_status": "Cooling",
                                "temperature": 72,
                            },
                            {
                                "is_connected": True,
                                "name": "connection",
                                "signal_strength": "unknown",
                            },
                            {
                                "actions": {
                                    "update_thermostat_mode": {
                                        "href": (
                                            "https://www.mynexia.com/mobile"
                                            "/xxl_zones/83394127/zone_mode"
                                        ),
                                        "method": "POST",
                                    }
                                },
                                "display_value": "Auto",
                                "label": "Zone Mode",
                                "name": "thermostat_mode",
                                "options": [
                                    {
                                        "header": True,
                                        "id": "thermostat_mode",
                                        "label": "Zone Mode",
                                        "value": "thermostat_mode",
                                    },
                                    {"label": "Auto", "value": "AUTO"},
                                    {"label": "Cooling", "value": "COOL"},
                                    {"label": "Heating", "value": "HEAT"},
                                    {"label": "Off", "value": "OFF"},
                                ],
                                "value": "AUTO",
                            },
                            {
                                "actions": {
                                    "update_thermostat_run_mode": {
                                        "href": (
                                            "https://www.mynexia.com/mobile"
                                            "/xxl_zones/83394127/run_mode"
                                        ),
                                        "method": "POST",
                                    }
                                },
                                "display_value": "Hold",
                                "label": "Run Mode",
                                "name": "thermostat_run_mode",
                                "options": [
                                    {
                                        "header": True,
                                        "id": "thermostat_run_mode",
                                        "label": "Run Mode",
                                        "value": "thermostat_run_mode",
                                    },
                                    {
                                        "id": "info_text",
                                        "info": True,
                                        "label": "Follow or override the schedule.",
                                        "value": "info_text",
                                    },
                                    {
                                        "label": "Permanent Hold",
                                        "value": "permanent_hold",
                                    },
                                    {"label": "Run Schedule", "value": "run_schedule"},
                                ],
                                "value": "permanent_hold",
                            },
                            {
                                "actions": {
                                    "enable_scheduling": {
                                        "data": {"value": True},
                                        "href": (
                                            "https://www.mynexia.com/mobile/xxl_zones"
                                            "/83394127/scheduling_enabled"
                                        ),
                                        "method": "POST",
                                    },
                                    "get_active_schedule": {
                                        "href": (
                                            "https://www.mynexia.com/mobile"
                                            "/thermostat_schedules/get_active_schedule"
                                            "?device_identifier=XxlZone-83394127"
                                        ),
                                        "method": "POST",
                                    },
                                    "get_default_schedule": {
                                        "href": (
                                            "https://www.mynexia.com/mobile"
                                            "/thermostat_schedules/get_default_schedule"
                                            "?device_identifier=XxlZone-83394127"
                                        ),
                                        "method": "GET",
                                    },
                                    "set_active_schedule": {
                                        "href": (
                                            "https://www.mynexia.com/mobile"
                                            "/thermostat_schedules/set_active_schedule"
                                            "?device_identifier=XxlZone-83394127"
                                        ),
                                        "method": "POST",
                                    },
                                },
                                "can_add_remove_periods": True,
                                "collection_url": (
                                    "https://www.mynexia.com/mobile/schedules"
                                    "?device_identifier=XxlZone-83394127"
                                    "&house_id=123456"
                                ),
                                "enabled": True,
                                "max_period_name_length": 10,
                                "max_periods_per_day": 4,
                                "name": "schedule",
                                "setpoint_increment": 1,
                            },
                        ],
                        "heating_setpoint": 63,
                        "icon": {"modifiers": ["temperature-72"], "name": "thermostat"},
                        "id": 83394127,
                        "name": "Snooze Room",
                        "operating_state": "Damper Closed",
                        "setpoints": {"cool": 79, "heat": 63},
                        "settings": [
                            {
                                "_links": {
                                    "self": {
                                        "href": (
                                            "https://www.mynexia.com/mobile"
                                            "/xxl_zones/83394127/preset_selected"
                                        )
                                    }
                                },
                                "current_value": 0,
                                "labels": ["None", "Home", "Away", "Sleep"],
                                "options": [
                                    {"label": "None", "value": 0},
                                    {"label": "Home", "value": 1},
                                    {"label": "Away", "value": 2},
                                    {"label": "Sleep", "value": 3},
                                ],
                                "title": "Preset",
                                "type": "preset_selected",
                                "values": [0, 1, 2, 3],
                            },
                            {
                                "_links": {
                                    "self": {
                                        "href": (
                                            "https://www.mynexia.com/mobile"
                                            "/xxl_zones/83394127/zone_mode"
                                        )
                                    }
                                },
                                "current_value": "AUTO",
                                "labels": ["Auto", "Cooling", "Heating", "Off"],
                                "options": [
                                    {"label": "Auto", "value": "AUTO"},
                                    {"label": "Cooling", "value": "COOL"},
                                    {"label": "Heating", "value": "HEAT"},
                                    {"label": "Off", "value": "OFF"},
                                ],
                                "title": "Zone Mode",
                                "type": "zone_mode",
                                "values": ["AUTO", "COOL", "HEAT", "OFF"],
                            },
                            {
                                "_links": {
                                    "self": {
                                        "href": (
                                            "https://www.mynexia.com/mobile"
                                            "/xxl_zones/83394127/run_mode"
                                        )
                                    }
                                },
                                "current_value": "permanent_hold",
                                "labels": ["Permanent Hold", "Run Schedule"],
                                "options": [
                                    {
                                        "label": "Permanent Hold",
                                        "value": "permanent_hold",
                                    },
                                    {"label": "Run Schedule", "value": "run_schedule"},
                                ],
                                "title": "Run Mode",
                                "type": "run_mode",
                                "values": ["permanent_hold", "run_schedule"],
                            },
                            {
                                "_links": {
                                    "self": {
                                        "href": (
                                            "https://www.mynexia.com/mobile"
                                            "/xxl_zones/83394127/scheduling_enabled"
                                        )
                                    }
                                },
                                "current_value": True,
                                "labels": ["ON", "OFF"],
                                "options": [
                                    {"label": "ON", "value": True},
                                    {"label": "OFF", "value": False},
                                ],
                                "title": "Scheduling",
                                "type": "scheduling_enabled",
                                "values": [True, False],
                            },
                        ],
                        "temperature": 72,
                        "type": "xxl_zone",
                        "zone_status": "Damper Closed",
                    },
                    {
                        "_links": {
                            "self": {
                                "href": (
                                    "https://www.mynexia.com/mobile/xxl_zones/83394139"
                                )
                            }
                        },
                        "cooling_setpoint": 79,
                        "current_zone_mode": "AUTO",
                        "features": [
                            {
                                "actions": {
                                    "set_cool_setpoint": {
                                        "href": (
                                            "https://www.mynexia.com/mobile"
                                            "/xxl_zones/83394139/setpoints"
                                        )
                                    },
                                    "set_heat_setpoint": {
                                        "href": (
                                            "https://www.mynexia.com/mobile"
                                            "/xxl_zones/83394139/setpoints"
                                        )
                                    },
                                },
                                "name": "thermostat",
                                "scale": "f",
                                "setpoint_cool": 79,
                                "setpoint_cool_max": 99,
                                "setpoint_cool_min": 60,
                                "setpoint_delta": 3,
                                "setpoint_heat": 63,
                                "setpoint_heat_max": 90,
                                "setpoint_heat_min": 55,
                                "setpoint_increment": 1.0,
                                "status": "Damper Closed",
                                "status_icon": {"modifiers": [], "name": "cooling"},
                                "system_status": "Cooling",
                                "temperature": 74,
                            },
                            {
                                "is_connected": True,
                                "name": "connection",
                                "signal_strength": "unknown",
                            },
                            {
                                "actions": {
                                    "update_thermostat_mode": {
                                        "href": (
                                            "https://www.mynexia.com/mobile"
                                            "/xxl_zones/83394139/zone_mode"
                                        ),
                                        "method": "POST",
                                    }
                                },
                                "display_value": "Auto",
                                "label": "Zone Mode",
                                "name": "thermostat_mode",
                                "options": [
                                    {
                                        "header": True,
                                        "id": "thermostat_mode",
                                        "label": "Zone Mode",
                                        "value": "thermostat_mode",
                                    },
                                    {"label": "Auto", "value": "AUTO"},
                                    {"label": "Cooling", "value": "COOL"},
                                    {"label": "Heating", "value": "HEAT"},
                                    {"label": "Off", "value": "OFF"},
                                ],
                                "value": "AUTO",
                            },
                            {
                                "actions": {
                                    "update_thermostat_run_mode": {
                                        "href": (
                                            "https://www.mynexia.com/mobile"
                                            "/xxl_zones/83394139/run_mode"
                                        ),
                                        "method": "POST",
                                    }
                                },
                                "display_value": "Hold",
                                "label": "Run Mode",
                                "name": "thermostat_run_mode",
                                "options": [
                                    {
                                        "header": True,
                                        "id": "thermostat_run_mode",
                                        "label": "Run Mode",
                                        "value": "thermostat_run_mode",
                                    },
                                    {
                                        "id": "info_text",
                                        "info": True,
                                        "label": "Follow or override the schedule.",
                                        "value": "info_text",
                                    },
                                    {
                                        "label": "Permanent Hold",
                                        "value": "permanent_hold",
                                    },
                                    {"label": "Run Schedule", "value": "run_schedule"},
                                ],
                                "value": "permanent_hold",
                            },
                            {
                                "actions": {
                                    "enable_scheduling": {
                                        "data": {"value": True},
                                        "href": (
                                            "https://www.mynexia.com/mobile/xxl_zones"
                                            "/83394139/scheduling_enabled"
                                        ),
                                        "method": "POST",
                                    },
                                    "get_active_schedule": {
                                        "href": (
                                            "https://www.mynexia.com/mobile"
                                            "/thermostat_schedules/get_active_schedule"
                                            "?device_identifier=XxlZone-83394139"
                                        ),
                                        "method": "POST",
                                    },
                                    "get_default_schedule": {
                                        "href": (
                                            "https://www.mynexia.com/mobile"
                                            "/thermostat_schedules/get_default_schedule"
                                            "?device_identifier=XxlZone-83394139"
                                        ),
                                        "method": "GET",
                                    },
                                    "set_active_schedule": {
                                        "href": (
                                            "https://www.mynexia.com/mobile"
                                            "/thermostat_schedules/set_active_schedule"
                                            "?device_identifier=XxlZone-83394139"
                                        ),
                                        "method": "POST",
                                    },
                                },
                                "can_add_remove_periods": True,
                                "collection_url": (
                                    "https://www.mynexia.com/mobile/schedules"
                                    "?device_identifier=XxlZone-83394139"
                                    "&house_id=123456"
                                ),
                                "enabled": True,
                                "max_period_name_length": 10,
                                "max_periods_per_day": 4,
                                "name": "schedule",
                                "setpoint_increment": 1,
                            },
                        ],
                        "heating_setpoint": 63,
                        "icon": {"modifiers": ["temperature-74"], "name": "thermostat"},
                        "id": 83394139,
                        "name": "Safe Room",
                        "operating_state": "Damper Closed",
                        "setpoints": {"cool": 79, "heat": 63},
                        "settings": [
                            {
                                "_links": {
                                    "self": {
                                        "href": (
                                            "https://www.mynexia.com/mobile"
                                            "/xxl_zones/83394139/preset_selected"
                                        )
                                    }
                                },
                                "current_value": 0,
                                "labels": ["None", "Home", "Away", "Sleep"],
                                "options": [
                                    {"label": "None", "value": 0},
                                    {"label": "Home", "value": 1},
                                    {"label": "Away", "value": 2},
                                    {"label": "Sleep", "value": 3},
                                ],
                                "title": "Preset",
                                "type": "preset_selected",
                                "values": [0, 1, 2, 3],
                            },
                            {
                                "_links": {
                                    "self": {
                                        "href": (
                                            "https://www.mynexia.com/mobile"
                                            "/xxl_zones/83394139/zone_mode"
                                        )
                                    }
                                },
                                "current_value": "AUTO",
                                "labels": ["Auto", "Cooling", "Heating", "Off"],
                                "options": [
                                    {"label": "Auto", "value": "AUTO"},
                                    {"label": "Cooling", "value": "COOL"},
                                    {"label": "Heating", "value": "HEAT"},
                                    {"label": "Off", "value": "OFF"},
                                ],
                                "title": "Zone Mode",
                                "type": "zone_mode",
                                "values": ["AUTO", "COOL", "HEAT", "OFF"],
                            },
                            {
                                "_links": {
                                    "self": {
                                        "href": (
                                            "https://www.mynexia.com/mobile"
                                            "/xxl_zones/83394139/run_mode"
                                        )
                                    }
                                },
                                "current_value": "permanent_hold",
                                "labels": ["Permanent Hold", "Run Schedule"],
                                "options": [
                                    {
                                        "label": "Permanent Hold",
                                        "value": "permanent_hold",
                                    },
                                    {"label": "Run Schedule", "value": "run_schedule"},
                                ],
                                "title": "Run Mode",
                                "type": "run_mode",
                                "values": ["permanent_hold", "run_schedule"],
                            },
                            {
                                "_links": {
                                    "self": {
                                        "href": (
                                            "https://www.mynexia.com/mobile"
                                            "/xxl_zones/83394139/scheduling_enabled"
                                        )
                                    }
                                },
                                "current_value": True,
                                "labels": ["ON", "OFF"],
                                "options": [
                                    {"label": "ON", "value": True},
                                    {"label": "OFF", "value": False},
                                ],
                                "title": "Scheduling",
                                "type": "scheduling_enabled",
                                "values": [True, False],
                            },
                        ],
                        "temperature": 74,
                        "type": "xxl_zone",
                        "zone_status": "Damper Closed",
                    },
                ],
            },
            {
                "_links": {
                    "filter_events": {
                        "href": (
                            "https://www.mynexia.com/mobile/houses/123456/events"
                            "/collection?sys_guid=3679e95b-7337-48ae-aff4-e0522e9dd0eb"
                        )
                    },
                    "nexia:history": {
                        "href": (
                            "https://www.mynexia.com/mobile/houses/123456"
                            "/events?device_id=2059652"
                        )
                    },
                    "pending_request": {
                        "polling_path": (
                            "https://www.mynexia.com/backstage/announcements"
                            "/c6627726f6339d104ee66897028d6a2ea38215675b336650"
                        )
                    },
                    "self": {
                        "href": "https://www.mynexia.com/mobile/xxl_thermostats/2059652"
                    },
                },
                "connected": True,
                "delta": 3,
                "features": [
                    {
                        "items": [
                            {
                                "label": "Model",
                                "type": "label_value",
                                "value": "XL1050",
                            },
                            {
                                "label": "AUID",
                                "type": "label_value",
                                "value": "02853DF0",
                            },
                            {
                                "label": "Firmware Build Number",
                                "type": "label_value",
                                "value": "1581321824",
                            },
                            {
                                "label": "Firmware Build Date",
                                "type": "label_value",
                                "value": "2020-02-10 08:03:44 UTC",
                            },
                            {
                                "label": "Firmware Version",
                                "type": "label_value",
                                "value": "5.9.1",
                            },
                            {
                                "label": "Zoning Enabled",
                                "type": "label_value",
                                "value": "yes",
                            },
                        ],
                        "name": "advanced_info",
                    },
                    {
                        "actions": {},
                        "name": "thermostat",
                        "scale": "f",
                        "setpoint_cool_max": 99,
                        "setpoint_cool_min": 60,
                        "setpoint_delta": 3,
                        "setpoint_heat_max": 90,
                        "setpoint_heat_min": 55,
                        "setpoint_increment": 1.0,
                        "status": "System Idle",
                        "status_icon": None,
                        "temperature": 77,
                    },
                    {
                        "is_connected": True,
                        "name": "connection",
                        "signal_strength": "unknown",
                    },
                    {
                        "members": [
                            {
                                "_links": {
                                    "self": {
                                        "href": (
                                            "https://www.mynexia.com/mobile"
                                            "/xxl_zones/83260991"
                                        )
                                    }
                                },
                                "cooling_setpoint": 80,
                                "current_zone_mode": "OFF",
                                "features": [
                                    {
                                        "actions": {},
                                        "name": "thermostat",
                                        "scale": "f",
                                        "setpoint_cool_max": 99,
                                        "setpoint_cool_min": 60,
                                        "setpoint_delta": 3,
                                        "setpoint_heat_max": 90,
                                        "setpoint_heat_min": 55,
                                        "setpoint_increment": 1.0,
                                        "status": "",
                                        "status_icon": None,
                                        "system_status": "System Idle",
                                        "temperature": 77,
                                    },
                                    {
                                        "is_connected": True,
                                        "name": "connection",
                                        "signal_strength": "unknown",
                                    },
                                    {
                                        "actions": {
                                            "update_thermostat_mode": {
                                                "href": (
                                                    "https://www.mynexia.com/mobile"
                                                    "/xxl_zones/83260991/zone_mode"
                                                ),
                                                "method": "POST",
                                            }
                                        },
                                        "display_value": "Off",
                                        "label": "Zone Mode",
                                        "name": "thermostat_mode",
                                        "options": [
                                            {
                                                "header": True,
                                                "id": "thermostat_mode",
                                                "label": "Zone Mode",
                                                "value": "thermostat_mode",
                                            },
                                            {"label": "Auto", "value": "AUTO"},
                                            {"label": "Cooling", "value": "COOL"},
                                            {"label": "Heating", "value": "HEAT"},
                                            {"label": "Off", "value": "OFF"},
                                        ],
                                        "value": "OFF",
                                    },
                                    {
                                        "actions": {
                                            "update_thermostat_run_mode": {
                                                "href": (
                                                    "https://www.mynexia.com/mobile"
                                                    "/xxl_zones/83260991/run_mode"
                                                ),
                                                "method": "POST",
                                            }
                                        },
                                        "display_value": "Hold",
                                        "label": "Run Mode",
                                        "name": "thermostat_run_mode",
                                        "options": [
                                            {
                                                "header": True,
                                                "id": "thermostat_run_mode",
                                                "label": "Run Mode",
                                                "value": "thermostat_run_mode",
                                            },
                                            {
                                                "id": "info_text",
                                                "info": True,
                                                "label": (
                                                    "Follow or override the schedule."
                                                ),
                                                "value": "info_text",
                                            },
                                            {
                                                "label": "Permanent Hold",
                                                "value": "permanent_hold",
                                            },
                                            {
                                                "label": "Run Schedule",
                                                "value": "run_schedule",
                                            },
                                        ],
                                        "value": "permanent_hold",
                                    },
                                    {
                                        "actions": {
                                            "enable_scheduling": {
                                                "data": {"value": True},
                                                "href": (
                                                    "https://www.mynexia.com/mobile"
                                                    "/xxl_zones/83260991"
                                                    "/scheduling_enabled"
                                                ),
                                                "method": "POST",
                                            },
                                            "get_active_schedule": {
                                                "href": (
                                                    "https://www.mynexia.com/mobile"
                                                    "/thermostat_schedules"
                                                    "/get_active_schedule"
                                                    "?device_identifier"
                                                    "=XxlZone-83260991"
                                                ),
                                                "method": "POST",
                                            },
                                            "get_default_schedule": {
                                                "href": (
                                                    "https://www.mynexia.com/mobile"
                                                    "/thermostat_schedules"
                                                    "/get_default_schedule"
                                                    "?device_identifier"
                                                    "=XxlZone-83260991"
                                                ),
                                                "method": "GET",
                                            },
                                            "set_active_schedule": {
                                                "href": (
                                                    "https://www.mynexia.com/mobile"
                                                    "/thermostat_schedules"
                                                    "/set_active_schedule"
                                                    "?device_identifier"
                                                    "=XxlZone-83260991"
                                                ),
                                                "method": "POST",
                                            },
                                        },
                                        "can_add_remove_periods": True,
                                        "collection_url": (
                                            "https://www.mynexia.com/mobile/schedules"
                                            "?device_identifier=XxlZone-83260991"
                                            "&house_id=123456"
                                        ),
                                        "enabled": True,
                                        "max_period_name_length": 10,
                                        "max_periods_per_day": 4,
                                        "name": "schedule",
                                        "setpoint_increment": 1,
                                    },
                                ],
                                "heating_setpoint": 63,
                                "icon": {
                                    "modifiers": ["temperature-77"],
                                    "name": "thermostat",
                                },
                                "id": 83260991,
                                "name": "Hallway",
                                "operating_state": "",
                                "setpoints": {"cool": 80, "heat": 63},
                                "settings": [
                                    {
                                        "_links": {
                                            "self": {
                                                "href": (
                                                    "https://www.mynexia.com/mobile"
                                                    "/xxl_zones/83260991/preset_selected"
                                                )
                                            }
                                        },
                                        "current_value": 0,
                                        "labels": ["None", "Home", "Away", "Sleep"],
                                        "options": [
                                            {"label": "None", "value": 0},
                                            {"label": "Home", "value": 1},
                                            {"label": "Away", "value": 2},
                                            {"label": "Sleep", "value": 3},
                                        ],
                                        "title": "Preset",
                                        "type": "preset_selected",
                                        "values": [0, 1, 2, 3],
                                    },
                                    {
                                        "_links": {
                                            "self": {
                                                "href": (
                                                    "https://www.mynexia.com/mobile"
                                                    "/xxl_zones/83260991/zone_mode"
                                                )
                                            }
                                        },
                                        "current_value": "OFF",
                                        "labels": ["Auto", "Cooling", "Heating", "Off"],
                                        "options": [
                                            {"label": "Auto", "value": "AUTO"},
                                            {"label": "Cooling", "value": "COOL"},
                                            {"label": "Heating", "value": "HEAT"},
                                            {"label": "Off", "value": "OFF"},
                                        ],
                                        "title": "Zone Mode",
                                        "type": "zone_mode",
                                        "values": ["AUTO", "COOL", "HEAT", "OFF"],
                                    },
                                    {
                                        "_links": {
                                            "self": {
                                                "href": (
                                                    "https://www.mynexia.com/mobile"
                                                    "/xxl_zones/83260991/run_mode"
                                                )
                                            }
                                        },
                                        "current_value": "permanent_hold",
                                        "labels": [
                                            "Permanent Hold",
                                            "Run Schedule",
                                        ],
                                        "options": [
                                            {
                                                "label": "Permanent Hold",
                                                "value": "permanent_hold",
                                            },
                                            {
                                                "label": "Run Schedule",
                                                "value": "run_schedule",
                                            },
                                        ],
                                        "title": "Run Mode",
                                        "type": "run_mode",
                                        "values": ["permanent_hold", "run_schedule"],
                                    },
                                    {
                                        "_links": {
                                            "self": {
                                                "href": (
                                                    "https://www.mynexia.com/mobile"
                                                    "/xxl_zones/83260991"
                                                    "/scheduling_enabled"
                                                )
                                            }
                                        },
                                        "current_value": True,
                                        "labels": ["ON", "OFF"],
                                        "options": [
                                            {"label": "ON", "value": True},
                                            {"label": "OFF", "value": False},
                                        ],
                                        "title": "Scheduling",
                                        "type": "scheduling_enabled",
                                        "values": [True, False],
                                    },
                                ],
                                "temperature": 77,
                                "type": "xxl_zone",
                                "zone_status": "",
                            },
                            {
                                "_links": {
                                    "self": {
                                        "href": (
                                            "https://www.mynexia.com/mobile"
                                            "/xxl_zones/83260994"
                                        )
                                    }
                                },
                                "cooling_setpoint": 81,
                                "current_zone_mode": "AUTO",
                                "features": [
                                    {
                                        "actions": {
                                            "set_cool_setpoint": {
                                                "href": (
                                                    "https://www.mynexia.com/mobile"
                                                    "/xxl_zones/83260994/setpoints"
                                                )
                                            },
                                            "set_heat_setpoint": {
                                                "href": (
                                                    "https://www.mynexia.com/mobile"
                                                    "/xxl_zones/83260994/setpoints"
                                                )
                                            },
                                        },
                                        "name": "thermostat",
                                        "scale": "f",
                                        "setpoint_cool": 81,
                                        "setpoint_cool_max": 99,
                                        "setpoint_cool_min": 60,
                                        "setpoint_delta": 3,
                                        "setpoint_heat": 63,
                                        "setpoint_heat_max": 90,
                                        "setpoint_heat_min": 55,
                                        "setpoint_increment": 1.0,
                                        "status": "",
                                        "status_icon": None,
                                        "system_status": "System Idle",
                                        "temperature": 74,
                                    },
                                    {
                                        "is_connected": True,
                                        "name": "connection",
                                        "signal_strength": "unknown",
                                    },
                                    {
                                        "actions": {
                                            "update_thermostat_mode": {
                                                "href": (
                                                    "https://www.mynexia.com/mobile"
                                                    "/xxl_zones/83260994/zone_mode"
                                                ),
                                                "method": "POST",
                                            }
                                        },
                                        "display_value": "Auto",
                                        "label": "Zone Mode",
                                        "name": "thermostat_mode",
                                        "options": [
                                            {
                                                "header": True,
                                                "id": "thermostat_mode",
                                                "label": "Zone Mode",
                                                "value": "thermostat_mode",
                                            },
                                            {"label": "Auto", "value": "AUTO"},
                                            {"label": "Cooling", "value": "COOL"},
                                            {"label": "Heating", "value": "HEAT"},
                                            {"label": "Off", "value": "OFF"},
                                        ],
                                        "value": "AUTO",
                                    },
                                    {
                                        "actions": {
                                            "update_thermostat_run_mode": {
                                                "href": (
                                                    "https://www.mynexia.com/mobile"
                                                    "/xxl_zones/83260994/run_mode"
                                                ),
                                                "method": "POST",
                                            }
                                        },
                                        "display_value": "Hold",
                                        "label": "Run Mode",
                                        "name": "thermostat_run_mode",
                                        "options": [
                                            {
                                                "header": True,
                                                "id": "thermostat_run_mode",
                                                "label": "Run Mode",
                                                "value": "thermostat_run_mode",
                                            },
                                            {
                                                "id": "info_text",
                                                "info": True,
                                                "label": (
                                                    "Follow or override the schedule."
                                                ),
                                                "value": "info_text",
                                            },
                                            {
                                                "label": "Permanent Hold",
                                                "value": "permanent_hold",
                                            },
                                            {
                                                "label": "Run Schedule",
                                                "value": "run_schedule",
                                            },
                                        ],
                                        "value": "permanent_hold",
                                    },
                                    {
                                        "actions": {
                                            "enable_scheduling": {
                                                "data": {"value": True},
                                                "href": (
                                                    "https://www.mynexia.com/mobile"
                                                    "/xxl_zones/83260994"
                                                    "/scheduling_enabled"
                                                ),
                                                "method": "POST",
                                            },
                                            "get_active_schedule": {
                                                "href": (
                                                    "https://www.mynexia.com/mobile"
                                                    "/thermostat_schedules"
                                                    "/get_active_schedule"
                                                    "?device_identifier"
                                                    "=XxlZone-83260994"
                                                ),
                                                "method": "POST",
                                            },
                                            "get_default_schedule": {
                                                "href": (
                                                    "https://www.mynexia.com/mobile"
                                                    "/thermostat_schedules"
                                                    "/get_default_schedule"
                                                    "?device_identifier"
                                                    "=XxlZone-83260994"
                                                ),
                                                "method": "GET",
                                            },
                                            "set_active_schedule": {
                                                "href": (
                                                    "https://www.mynexia.com/mobile"
                                                    "/thermostat_schedules"
                                                    "/set_active_schedule"
                                                    "?device_identifier"
                                                    "=XxlZone-83260994"
                                                ),
                                                "method": "POST",
                                            },
                                        },
                                        "can_add_remove_periods": True,
                                        "collection_url": (
                                            "https://www.mynexia.com/mobile/schedules"
                                            "?device_identifier=XxlZone-83260994"
                                            "&house_id=123456"
                                        ),
                                        "enabled": True,
                                        "max_period_name_length": 10,
                                        "max_periods_per_day": 4,
                                        "name": "schedule",
                                        "setpoint_increment": 1,
                                    },
                                ],
                                "heating_setpoint": 63,
                                "icon": {
                                    "modifiers": ["temperature-74"],
                                    "name": "thermostat",
                                },
                                "id": 83260994,
                                "name": "Mid Bedroom",
                                "operating_state": "",
                                "setpoints": {"cool": 81, "heat": 63},
                                "settings": [
                                    {
                                        "_links": {
                                            "self": {
                                                "href": (
                                                    "https://www.mynexia.com/mobile"
                                                    "/xxl_zones/83260994"
                                                    "/preset_selected"
                                                )
                                            }
                                        },
                                        "current_value": 0,
                                        "labels": ["None", "Home", "Away", "Sleep"],
                                        "options": [
                                            {"label": "None", "value": 0},
                                            {"label": "Home", "value": 1},
                                            {"label": "Away", "value": 2},
                                            {"label": "Sleep", "value": 3},
                                        ],
                                        "title": "Preset",
                                        "type": "preset_selected",
                                        "values": [0, 1, 2, 3],
                                    },
                                    {
                                        "_links": {
                                            "self": {
                                                "href": (
                                                    "https://www.mynexia.com/mobile"
                                                    "/xxl_zones/83260994/zone_mode"
                                                )
                                            }
                                        },
                                        "current_value": "AUTO",
                                        "labels": ["Auto", "Cooling", "Heating", "Off"],
                                        "options": [
                                            {"label": "Auto", "value": "AUTO"},
                                            {"label": "Cooling", "value": "COOL"},
                                            {"label": "Heating", "value": "HEAT"},
                                            {"label": "Off", "value": "OFF"},
                                        ],
                                        "title": "Zone Mode",
                                        "type": "zone_mode",
                                        "values": ["AUTO", "COOL", "HEAT", "OFF"],
                                    },
                                    {
                                        "_links": {
                                            "self": {
                                                "href": (
                                                    "https://www.mynexia.com/mobile"
                                                    "/xxl_zones/83260994/run_mode"
                                                )
                                            }
                                        },
                                        "current_value": "permanent_hold",
                                        "labels": [
                                            "Permanent Hold",
                                            "Run Schedule",
                                        ],
                                        "options": [
                                            {
                                                "label": "Permanent Hold",
                                                "value": "permanent_hold",
                                            },
                                            {
                                                "label": "Run Schedule",
                                                "value": "run_schedule",
                                            },
                                        ],
                                        "title": "Run Mode",
                                        "type": "run_mode",
                                        "values": ["permanent_hold", "run_schedule"],
                                    },
                                    {
                                        "_links": {
                                            "self": {
                                                "href": (
                                                    "https://www.mynexia.com/mobile"
                                                    "/xxl_zones/83260994"
                                                    "/scheduling_enabled"
                                                )
                                            }
                                        },
                                        "current_value": True,
                                        "labels": ["ON", "OFF"],
                                        "options": [
                                            {"label": "ON", "value": True},
                                            {"label": "OFF", "value": False},
                                        ],
                                        "title": "Scheduling",
                                        "type": "scheduling_enabled",
                                        "values": [True, False],
                                    },
                                ],
                                "temperature": 74,
                                "type": "xxl_zone",
                                "zone_status": "",
                            },
                            {
                                "_links": {
                                    "self": {
                                        "href": (
                                            "https://www.mynexia.com/mobile"
                                            "/xxl_zones/83260997"
                                        )
                                    }
                                },
                                "cooling_setpoint": 81,
                                "current_zone_mode": "AUTO",
                                "features": [
                                    {
                                        "actions": {
                                            "set_cool_setpoint": {
                                                "href": (
                                                    "https://www.mynexia.com/mobile"
                                                    "/xxl_zones/83260997/setpoints"
                                                )
                                            },
                                            "set_heat_setpoint": {
                                                "href": (
                                                    "https://www.mynexia.com/mobile"
                                                    "/xxl_zones/83260997/setpoints"
                                                )
                                            },
                                        },
                                        "name": "thermostat",
                                        "scale": "f",
                                        "setpoint_cool": 81,
                                        "setpoint_cool_max": 99,
                                        "setpoint_cool_min": 60,
                                        "setpoint_delta": 3,
                                        "setpoint_heat": 63,
                                        "setpoint_heat_max": 90,
                                        "setpoint_heat_min": 55,
                                        "setpoint_increment": 1.0,
                                        "status": "",
                                        "status_icon": None,
                                        "system_status": "System Idle",
                                        "temperature": 75,
                                    },
                                    {
                                        "is_connected": True,
                                        "name": "connection",
                                        "signal_strength": "unknown",
                                    },
                                    {
                                        "actions": {
                                            "update_thermostat_mode": {
                                                "href": (
                                                    "https://www.mynexia.com/mobile"
                                                    "/xxl_zones/83260997/zone_mode"
                                                ),
                                                "method": "POST",
                                            }
                                        },
                                        "display_value": "Auto",
                                        "label": "Zone Mode",
                                        "name": "thermostat_mode",
                                        "options": [
                                            {
                                                "header": True,
                                                "id": "thermostat_mode",
                                                "label": "Zone Mode",
                                                "value": "thermostat_mode",
                                            },
                                            {"label": "Auto", "value": "AUTO"},
                                            {"label": "Cooling", "value": "COOL"},
                                            {"label": "Heating", "value": "HEAT"},
                                            {"label": "Off", "value": "OFF"},
                                        ],
                                        "value": "AUTO",
                                    },
                                    {
                                        "actions": {
                                            "update_thermostat_run_mode": {
                                                "href": (
                                                    "https://www.mynexia.com/mobile"
                                                    "/xxl_zones/83260997/run_mode"
                                                ),
                                                "method": "POST",
                                            }
                                        },
                                        "display_value": "Hold",
                                        "label": "Run Mode",
                                        "name": "thermostat_run_mode",
                                        "options": [
                                            {
                                                "header": True,
                                                "id": "thermostat_run_mode",
                                                "label": "Run Mode",
                                                "value": "thermostat_run_mode",
                                            },
                                            {
                                                "id": "info_text",
                                                "info": True,
                                                "label": (
                                                    "Follow or override the schedule."
                                                ),
                                                "value": "info_text",
                                            },
                                            {
                                                "label": "Permanent Hold",
                                                "value": "permanent_hold",
                                            },
                                            {
                                                "label": "Run Schedule",
                                                "value": "run_schedule",
                                            },
                                        ],
                                        "value": "permanent_hold",
                                    },
                                    {
                                        "actions": {
                                            "enable_scheduling": {
                                                "data": {"value": True},
                                                "href": (
                                                    "https://www.mynexia.com/mobile"
                                                    "/xxl_zones/83260997"
                                                    "/scheduling_enabled"
                                                ),
                                                "method": "POST",
                                            },
                                            "get_active_schedule": {
                                                "href": (
                                                    "https://www.mynexia.com/mobile"
                                                    "/thermostat_schedules"
                                                    "/get_active_schedule"
                                                    "?device_identifier"
                                                    "=XxlZone-83260997"
                                                ),
                                                "method": "POST",
                                            },
                                            "get_default_schedule": {
                                                "href": (
                                                    "https://www.mynexia.com/mobile"
                                                    "/thermostat_schedules"
                                                    "/get_default_schedule"
                                                    "?device_identifier"
                                                    "=XxlZone-83260997"
                                                ),
                                                "method": "GET",
                                            },
                                            "set_active_schedule": {
                                                "href": (
                                                    "https://www.mynexia.com/mobile"
                                                    "/thermostat_schedules"
                                                    "/set_active_schedule"
                                                    "?device_identifier"
                                                    "=XxlZone-83260997"
                                                ),
                                                "method": "POST",
                                            },
                                        },
                                        "can_add_remove_periods": True,
                                        "collection_url": (
                                            "https://www.mynexia.com/mobile/schedules"
                                            "?device_identifier=XxlZone-83260997"
                                            "&house_id=123456"
                                        ),
                                        "enabled": True,
                                        "max_period_name_length": 10,
                                        "max_periods_per_day": 4,
                                        "name": "schedule",
                                        "setpoint_increment": 1,
                                    },
                                ],
                                "heating_setpoint": 63,
                                "icon": {
                                    "modifiers": ["temperature-75"],
                                    "name": "thermostat",
                                },
                                "id": 83260997,
                                "name": "West Bedroom",
                                "operating_state": "",
                                "setpoints": {"cool": 81, "heat": 63},
                                "settings": [
                                    {
                                        "_links": {
                                            "self": {
                                                "href": (
                                                    "https://www.mynexia.com/mobile"
                                                    "/xxl_zones/83260997/preset_selected"
                                                )
                                            }
                                        },
                                        "current_value": 0,
                                        "labels": ["None", "Home", "Away", "Sleep"],
                                        "options": [
                                            {"label": "None", "value": 0},
                                            {"label": "Home", "value": 1},
                                            {"label": "Away", "value": 2},
                                            {"label": "Sleep", "value": 3},
                                        ],
                                        "title": "Preset",
                                        "type": "preset_selected",
                                        "values": [0, 1, 2, 3],
                                    },
                                    {
                                        "_links": {
                                            "self": {
                                                "href": (
                                                    "https://www.mynexia.com/mobile"
                                                    "/xxl_zones/83260997/zone_mode"
                                                )
                                            }
                                        },
                                        "current_value": "AUTO",
                                        "labels": ["Auto", "Cooling", "Heating", "Off"],
                                        "options": [
                                            {"label": "Auto", "value": "AUTO"},
                                            {"label": "Cooling", "value": "COOL"},
                                            {"label": "Heating", "value": "HEAT"},
                                            {"label": "Off", "value": "OFF"},
                                        ],
                                        "title": "Zone Mode",
                                        "type": "zone_mode",
                                        "values": ["AUTO", "COOL", "HEAT", "OFF"],
                                    },
                                    {
                                        "_links": {
                                            "self": {
                                                "href": (
                                                    "https://www.mynexia.com/mobile"
                                                    "/xxl_zones/83260997/run_mode"
                                                )
                                            }
                                        },
                                        "current_value": "permanent_hold",
                                        "labels": [
                                            "Permanent Hold",
                                            "Run Schedule",
                                        ],
                                        "options": [
                                            {
                                                "label": "Permanent Hold",
                                                "value": "permanent_hold",
                                            },
                                            {
                                                "label": "Run Schedule",
                                                "value": "run_schedule",
                                            },
                                        ],
                                        "title": "Run Mode",
                                        "type": "run_mode",
                                        "values": ["permanent_hold", "run_schedule"],
                                    },
                                    {
                                        "_links": {
                                            "self": {
                                                "href": (
                                                    "https://www.mynexia.com/mobile"
                                                    "/xxl_zones/83260997/scheduling_enabled"
                                                )
                                            }
                                        },
                                        "current_value": True,
                                        "labels": ["ON", "OFF"],
                                        "options": [
                                            {"label": "ON", "value": True},
                                            {"label": "OFF", "value": False},
                                        ],
                                        "title": "Scheduling",
                                        "type": "scheduling_enabled",
                                        "values": [True, False],
                                    },
                                ],
                                "temperature": 75,
                                "type": "xxl_zone",
                                "zone_status": "",
                            },
                        ],
                        "name": "group",
                    },
                    {
                        "actions": {
                            "update_thermostat_fan_mode": {
                                "href": (
                                    "https://www.mynexia.com/mobile"
                                    "/xxl_thermostats/2059652/fan_mode"
                                ),
                                "method": "POST",
                            }
                        },
                        "display_value": "Auto",
                        "label": "Fan Mode",
                        "name": "thermostat_fan_mode",
                        "options": [
                            {
                                "header": True,
                                "id": "thermostat_fan_mode",
                                "label": "Fan Mode",
                                "value": "thermostat_fan_mode",
                            },
                            {"label": "Auto", "value": "auto"},
                            {"label": "On", "value": "on"},
                            {"label": "Circulate", "value": "circulate"},
                        ],
                        "status_icon": {"modifiers": [], "name": "thermostat_fan_off"},
                        "value": "auto",
                    },
                    {"compressor_speed": 0.0, "name": "thermostat_compressor_speed"},
                    {
                        "actions": {
                            "get_monthly_runtime_history": {
                                "href": (
                                    "https://www.mynexia.com/mobile/runtime_history"
                                    "/2059652?report_type=monthly"
                                ),
                                "method": "GET",
                            },
                            "get_runtime_history": {
                                "href": (
                                    "https://www.mynexia.com/mobile/runtime_history"
                                    "/2059652?report_type=daily"
                                ),
                                "method": "GET",
                            },
                        },
                        "name": "runtime_history",
                    },
                ],
                "has_indoor_humidity": True,
                "has_outdoor_temperature": True,
                "icon": [
                    {"modifiers": ["temperature-77"], "name": "thermostat"},
                    {"modifiers": ["temperature-74"], "name": "thermostat"},
                    {"modifiers": ["temperature-75"], "name": "thermostat"},
                ],
                "id": 2059652,
                "indoor_humidity": "37",
                "last_updated_at": "2020-03-11T15:15:53.000-05:00",
                "name": "Upstairs West Wing",
                "name_editable": True,
                "outdoor_temperature": "87",
                "settings": [
                    {
                        "_links": {
                            "self": {
                                "href": (
                                    "https://www.mynexia.com/mobile"
                                    "/xxl_thermostats/2059652/fan_mode"
                                )
                            }
                        },
                        "current_value": "auto",
                        "labels": ["Auto", "On", "Circulate"],
                        "options": [
                            {"label": "Auto", "value": "auto"},
                            {"label": "On", "value": "on"},
                            {"label": "Circulate", "value": "circulate"},
                        ],
                        "title": "Fan Mode",
                        "type": "fan_mode",
                        "values": ["auto", "on", "circulate"],
                    },
                    {
                        "_links": {
                            "self": {
                                "href": (
                                    "https://www.mynexia.com/mobile"
                                    "/xxl_thermostats/2059652/fan_speed"
                                )
                            }
                        },
                        "current_value": 0.35,
                        "labels": [
                            "35%",
                            "40%",
                            "45%",
                            "50%",
                            "55%",
                            "60%",
                            "65%",
                            "70%",
                            "75%",
                            "80%",
                            "85%",
                            "90%",
                            "95%",
                            "100%",
                        ],
                        "options": [
                            {"label": "35%", "value": 0.35},
                            {"label": "40%", "value": 0.4},
                            {"label": "45%", "value": 0.45},
                            {"label": "50%", "value": 0.5},
                            {"label": "55%", "value": 0.55},
                            {"label": "60%", "value": 0.6},
                            {"label": "65%", "value": 0.65},
                            {"label": "70%", "value": 0.7},
                            {"label": "75%", "value": 0.75},
                            {"label": "80%", "value": 0.8},
                            {"label": "85%", "value": 0.85},
                            {"label": "90%", "value": 0.9},
                            {"label": "95%", "value": 0.95},
                            {"label": "100%", "value": 1.0},
                        ],
                        "title": "Fan Speed",
                        "type": "fan_speed",
                        "values": [
                            0.35,
                            0.4,
                            0.45,
                            0.5,
                            0.55,
                            0.6,
                            0.65,
                            0.7,
                            0.75,
                            0.8,
                            0.85,
                            0.9,
                            0.95,
                            1.0,
                        ],
                    },
                    {
                        "_links": {
                            "self": {
                                "href": (
                                    "https://www.mynexia.com/mobile"
                                    "/xxl_thermostats/2059652"
                                    "/fan_circulation_time"
                                )
                            }
                        },
                        "current_value": 30,
                        "labels": [
                            "10 minutes",
                            "15 minutes",
                            "20 minutes",
                            "25 minutes",
                            "30 minutes",
                            "35 minutes",
                            "40 minutes",
                            "45 minutes",
                            "50 minutes",
                            "55 minutes",
                        ],
                        "options": [
                            {"label": "10 minutes", "value": 10},
                            {"label": "15 minutes", "value": 15},
                            {"label": "20 minutes", "value": 20},
                            {"label": "25 minutes", "value": 25},
                            {"label": "30 minutes", "value": 30},
                            {"label": "35 minutes", "value": 35},
                            {"label": "40 minutes", "value": 40},
                            {"label": "45 minutes", "value": 45},
                            {"label": "50 minutes", "value": 50},
                            {"label": "55 minutes", "value": 55},
                        ],
                        "title": "Fan Circulation Time",
                        "type": "fan_circulation_time",
                        "values": [10, 15, 20, 25, 30, 35, 40, 45, 50, 55],
                    },
                    {
                        "_links": {
                            "self": {
                                "href": (
                                    "https://www.mynexia.com/mobile"
                                    "/xxl_thermostats/2059652/air_cleaner_mode"
                                )
                            }
                        },
                        "current_value": "auto",
                        "labels": ["Auto", "Quick", "Allergy"],
                        "options": [
                            {"label": "Auto", "value": "auto"},
                            {"label": "Quick", "value": "quick"},
                            {"label": "Allergy", "value": "allergy"},
                        ],
                        "title": "Air Cleaner Mode",
                        "type": "air_cleaner_mode",
                        "values": ["auto", "quick", "allergy"],
                    },
                    {
                        "_links": {
                            "self": {
                                "href": (
                                    "https://www.mynexia.com/mobile"
                                    "/xxl_thermostats/2059652/dehumidify"
                                )
                            }
                        },
                        "current_value": 0.5,
                        "labels": ["35%", "40%", "45%", "50%", "55%", "60%", "65%"],
                        "options": [
                            {"label": "35%", "value": 0.35},
                            {"label": "40%", "value": 0.4},
                            {"label": "45%", "value": 0.45},
                            {"label": "50%", "value": 0.5},
                            {"label": "55%", "value": 0.55},
                            {"label": "60%", "value": 0.6},
                            {"label": "65%", "value": 0.65},
                        ],
                        "title": "Cooling Dehumidify Set Point",
                        "type": "dehumidify",
                        "values": [0.35, 0.4, 0.45, 0.5, 0.55, 0.6, 0.65],
                    },
                    {
                        "_links": {
                            "self": {
                                "href": (
                                    "https://www.mynexia.com/mobile"
                                    "/xxl_thermostats/2059652/scale"
                                )
                            }
                        },
                        "current_value": "f",
                        "labels": ["F", "C"],
                        "options": [
                            {"label": "F", "value": "f"},
                            {"label": "C", "value": "c"},
                        ],
                        "title": "Temperature Scale",
                        "type": "scale",
                        "values": ["f", "c"],
                    },
                ],
                "status_secondary": None,
                "status_tertiary": None,
                "system_status": "System Idle",
                "type": "xxl_thermostat",
                "zones": [
                    {
                        "_links": {
                            "self": {
                                "href": (
                                    "https://www.mynexia.com/mobile/xxl_zones/83260991"
                                )
                            }
                        },
                        "cooling_setpoint": 80,
                        "current_zone_mode": "OFF",
                        "features": [
                            {
                                "actions": {},
                                "name": "thermostat",
                                "scale": "f",
                                "setpoint_cool_max": 99,
                                "setpoint_cool_min": 60,
                                "setpoint_delta": 3,
                                "setpoint_heat_max": 90,
                                "setpoint_heat_min": 55,
                                "setpoint_increment": 1.0,
                                "status": "",
                                "status_icon": None,
                                "system_status": "System Idle",
                                "temperature": 77,
                            },
                            {
                                "is_connected": True,
                                "name": "connection",
                                "signal_strength": "unknown",
                            },
                            {
                                "actions": {
                                    "update_thermostat_mode": {
                                        "href": (
                                            "https://www.mynexia.com/mobile"
                                            "/xxl_zones/83260991/zone_mode"
                                        ),
                                        "method": "POST",
                                    }
                                },
                                "display_value": "Off",
                                "label": "Zone Mode",
                                "name": "thermostat_mode",
                                "options": [
                                    {
                                        "header": True,
                                        "id": "thermostat_mode",
                                        "label": "Zone Mode",
                                        "value": "thermostat_mode",
                                    },
                                    {"label": "Auto", "value": "AUTO"},
                                    {"label": "Cooling", "value": "COOL"},
                                    {"label": "Heating", "value": "HEAT"},
                                    {"label": "Off", "value": "OFF"},
                                ],
                                "value": "OFF",
                            },
                            {
                                "actions": {
                                    "update_thermostat_run_mode": {
                                        "href": (
                                            "https://www.mynexia.com/mobile"
                                            "/xxl_zones/83260991/run_mode"
                                        ),
                                        "method": "POST",
                                    }
                                },
                                "display_value": "Hold",
                                "label": "Run Mode",
                                "name": "thermostat_run_mode",
                                "options": [
                                    {
                                        "header": True,
                                        "id": "thermostat_run_mode",
                                        "label": "Run Mode",
                                        "value": "thermostat_run_mode",
                                    },
                                    {
                                        "id": "info_text",
                                        "info": True,
                                        "label": "Follow or override the schedule.",
                                        "value": "info_text",
                                    },
                                    {
                                        "label": "Permanent Hold",
                                        "value": "permanent_hold",
                                    },
                                    {"label": "Run Schedule", "value": "run_schedule"},
                                ],
                                "value": "permanent_hold",
                            },
                            {
                                "actions": {
                                    "enable_scheduling": {
                                        "data": {"value": True},
                                        "href": (
                                            "https://www.mynexia.com/mobile"
                                            "/xxl_zones/83260991/scheduling_enabled"
                                        ),
                                        "method": "POST",
                                    },
                                    "get_active_schedule": {
                                        "href": (
                                            "https://www.mynexia.com/mobile"
                                            "/thermostat_schedules/get_active_schedule"
                                            "?device_identifier=XxlZone-83260991"
                                        ),
                                        "method": "POST",
                                    },
                                    "get_default_schedule": {
                                        "href": (
                                            "https://www.mynexia.com/mobile"
                                            "/thermostat_schedules/get_default_schedule"
                                            "?device_identifier=XxlZone-83260991"
                                        ),
                                        "method": "GET",
                                    },
                                    "set_active_schedule": {
                                        "href": (
                                            "https://www.mynexia.com/mobile"
                                            "/thermostat_schedules/set_active_schedule"
                                            "?device_identifier=XxlZone-83260991"
                                        ),
                                        "method": "POST",
                                    },
                                },
                                "can_add_remove_periods": True,
                                "collection_url": (
                                    "https://www.mynexia.com/mobile/schedules"
                                    "?device_identifier=XxlZone-83260991"
                                    "&house_id=123456"
                                ),
                                "enabled": True,
                                "max_period_name_length": 10,
                                "max_periods_per_day": 4,
                                "name": "schedule",
                                "setpoint_increment": 1,
                            },
                        ],
                        "heating_setpoint": 63,
                        "icon": {"modifiers": ["temperature-77"], "name": "thermostat"},
                        "id": 83260991,
                        "name": "Hallway",
                        "operating_state": "",
                        "setpoints": {"cool": 80, "heat": 63},
                        "settings": [
                            {
                                "_links": {
                                    "self": {
                                        "href": (
                                            "https://www.mynexia.com/mobile"
                                            "/xxl_zones/83260991/preset_selected"
                                        )
                                    }
                                },
                                "current_value": 0,
                                "labels": ["None", "Home", "Away", "Sleep"],
                                "options": [
                                    {"label": "None", "value": 0},
                                    {"label": "Home", "value": 1},
                                    {"label": "Away", "value": 2},
                                    {"label": "Sleep", "value": 3},
                                ],
                                "title": "Preset",
                                "type": "preset_selected",
                                "values": [0, 1, 2, 3],
                            },
                            {
                                "_links": {
                                    "self": {
                                        "href": (
                                            "https://www.mynexia.com/mobile"
                                            "/xxl_zones/83260991/zone_mode"
                                        )
                                    }
                                },
                                "current_value": "OFF",
                                "labels": ["Auto", "Cooling", "Heating", "Off"],
                                "options": [
                                    {"label": "Auto", "value": "AUTO"},
                                    {"label": "Cooling", "value": "COOL"},
                                    {"label": "Heating", "value": "HEAT"},
                                    {"label": "Off", "value": "OFF"},
                                ],
                                "title": "Zone Mode",
                                "type": "zone_mode",
                                "values": ["AUTO", "COOL", "HEAT", "OFF"],
                            },
                            {
                                "_links": {
                                    "self": {
                                        "href": (
                                            "https://www.mynexia.com/mobile"
                                            "/xxl_zones/83260991/run_mode"
                                        )
                                    }
                                },
                                "current_value": "permanent_hold",
                                "labels": ["Permanent Hold", "Run Schedule"],
                                "options": [
                                    {
                                        "label": "Permanent Hold",
                                        "value": "permanent_hold",
                                    },
                                    {"label": "Run Schedule", "value": "run_schedule"},
                                ],
                                "title": "Run Mode",
                                "type": "run_mode",
                                "values": ["permanent_hold", "run_schedule"],
                            },
                            {
                                "_links": {
                                    "self": {
                                        "href": (
                                            "https://www.mynexia.com/mobile"
                                            "/xxl_zones/83260991/scheduling_enabled"
                                        )
                                    }
                                },
                                "current_value": True,
                                "labels": ["ON", "OFF"],
                                "options": [
                                    {"label": "ON", "value": True},
                                    {"label": "OFF", "value": False},
                                ],
                                "title": "Scheduling",
                                "type": "scheduling_enabled",
                                "values": [True, False],
                            },
                        ],
                        "temperature": 77,
                        "type": "xxl_zone",
                        "zone_status": "",
                    },
                    {
                        "_links": {
                            "self": {
                                "href": (
                                    "https://www.mynexia.com/mobile/xxl_zones/83260994"
                                )
                            }
                        },
                        "cooling_setpoint": 81,
                        "current_zone_mode": "AUTO",
                        "features": [
                            {
                                "actions": {
                                    "set_cool_setpoint": {
                                        "href": (
                                            "https://www.mynexia.com/mobile/xxl_zones"
                                            "/83260994/setpoints"
                                        )
                                    },
                                    "set_heat_setpoint": {
                                        "href": (
                                            "https://www.mynexia.com/mobile/xxl_zones"
                                            "/83260994/setpoints"
                                        )
                                    },
                                },
                                "name": "thermostat",
                                "scale": "f",
                                "setpoint_cool": 81,
                                "setpoint_cool_max": 99,
                                "setpoint_cool_min": 60,
                                "setpoint_delta": 3,
                                "setpoint_heat": 63,
                                "setpoint_heat_max": 90,
                                "setpoint_heat_min": 55,
                                "setpoint_increment": 1.0,
                                "status": "",
                                "status_icon": None,
                                "system_status": "System Idle",
                                "temperature": 74,
                            },
                            {
                                "is_connected": True,
                                "name": "connection",
                                "signal_strength": "unknown",
                            },
                            {
                                "actions": {
                                    "update_thermostat_mode": {
                                        "href": (
                                            "https://www.mynexia.com/mobile/xxl_zones"
                                            "/83260994/zone_mode"
                                        ),
                                        "method": "POST",
                                    }
                                },
                                "display_value": "Auto",
                                "label": "Zone Mode",
                                "name": "thermostat_mode",
                                "options": [
                                    {
                                        "header": True,
                                        "id": "thermostat_mode",
                                        "label": "Zone Mode",
                                        "value": "thermostat_mode",
                                    },
                                    {"label": "Auto", "value": "AUTO"},
                                    {"label": "Cooling", "value": "COOL"},
                                    {"label": "Heating", "value": "HEAT"},
                                    {"label": "Off", "value": "OFF"},
                                ],
                                "value": "AUTO",
                            },
                            {
                                "actions": {
                                    "update_thermostat_run_mode": {
                                        "href": (
                                            "https://www.mynexia.com/mobile/xxl_zones"
                                            "/83260994/run_mode"
                                        ),
                                        "method": "POST",
                                    }
                                },
                                "display_value": "Hold",
                                "label": "Run Mode",
                                "name": "thermostat_run_mode",
                                "options": [
                                    {
                                        "header": True,
                                        "id": "thermostat_run_mode",
                                        "label": "Run Mode",
                                        "value": "thermostat_run_mode",
                                    },
                                    {
                                        "id": "info_text",
                                        "info": True,
                                        "label": "Follow or override the schedule.",
                                        "value": "info_text",
                                    },
                                    {
                                        "label": "Permanent Hold",
                                        "value": "permanent_hold",
                                    },
                                    {"label": "Run Schedule", "value": "run_schedule"},
                                ],
                                "value": "permanent_hold",
                            },
                            {
                                "actions": {
                                    "enable_scheduling": {
                                        "data": {"value": True},
                                        "href": (
                                            "https://www.mynexia.com/mobile/xxl_zones"
                                            "/83260994/scheduling_enabled"
                                        ),
                                        "method": "POST",
                                    },
                                    "get_active_schedule": {
                                        "href": (
                                            "https://www.mynexia.com/mobile"
                                            "/thermostat_schedules"
                                            "/get_active_schedule"
                                            "?device_identifier=XxlZone-83260994"
                                        ),
                                        "method": "POST",
                                    },
                                    "get_default_schedule": {
                                        "href": (
                                            "https://www.mynexia.com/mobile"
                                            "/thermostat_schedules"
                                            "/get_default_schedule"
                                            "?device_identifier=XxlZone-83260994"
                                        ),
                                        "method": "GET",
                                    },
                                    "set_active_schedule": {
                                        "href": (
                                            "https://www.mynexia.com/mobile"
                                            "/thermostat_schedules"
                                            "/set_active_schedule"
                                            "?device_identifier=XxlZone-83260994"
                                        ),
                                        "method": "POST",
                                    },
                                },
                                "can_add_remove_periods": True,
                                "collection_url": (
                                    "https://www.mynexia.com/mobile/schedules"
                                    "?device_identifier=XxlZone-83260994"
                                    "&house_id=123456"
                                ),
                                "enabled": True,
                                "max_period_name_length": 10,
                                "max_periods_per_day": 4,
                                "name": "schedule",
                                "setpoint_increment": 1,
                            },
                        ],
                        "heating_setpoint": 63,
                        "icon": {"modifiers": ["temperature-74"], "name": "thermostat"},
                        "id": 83260994,
                        "name": "Mid Bedroom",
                        "operating_state": "",
                        "setpoints": {"cool": 81, "heat": 63},
                        "settings": [
                            {
                                "_links": {
                                    "self": {
                                        "href": (
                                            "https://www.mynexia.com/mobile/xxl_zones"
                                            "/83260994/preset_selected"
                                        )
                                    }
                                },
                                "current_value": 0,
                                "labels": ["None", "Home", "Away", "Sleep"],
                                "options": [
                                    {"label": "None", "value": 0},
                                    {"label": "Home", "value": 1},
                                    {"label": "Away", "value": 2},
                                    {"label": "Sleep", "value": 3},
                                ],
                                "title": "Preset",
                                "type": "preset_selected",
                                "values": [0, 1, 2, 3],
                            },
                            {
                                "_links": {
                                    "self": {
                                        "href": (
                                            "https://www.mynexia.com/mobile/xxl_zones"
                                            "/83260994/zone_mode"
                                        )
                                    }
                                },
                                "current_value": "AUTO",
                                "labels": ["Auto", "Cooling", "Heating", "Off"],
                                "options": [
                                    {"label": "Auto", "value": "AUTO"},
                                    {"label": "Cooling", "value": "COOL"},
                                    {"label": "Heating", "value": "HEAT"},
                                    {"label": "Off", "value": "OFF"},
                                ],
                                "title": "Zone Mode",
                                "type": "zone_mode",
                                "values": ["AUTO", "COOL", "HEAT", "OFF"],
                            },
                            {
                                "_links": {
                                    "self": {
                                        "href": (
                                            "https://www.mynexia.com/mobile/xxl_zones"
                                            "/83260994/run_mode"
                                        )
                                    }
                                },
                                "current_value": "permanent_hold",
                                "labels": ["Permanent Hold", "Run Schedule"],
                                "options": [
                                    {
                                        "label": "Permanent Hold",
                                        "value": "permanent_hold",
                                    },
                                    {"label": "Run Schedule", "value": "run_schedule"},
                                ],
                                "title": "Run Mode",
                                "type": "run_mode",
                                "values": ["permanent_hold", "run_schedule"],
                            },
                            {
                                "_links": {
                                    "self": {
                                        "href": (
                                            "https://www.mynexia.com/mobile/xxl_zones"
                                            "/83260994/scheduling_enabled"
                                        )
                                    }
                                },
                                "current_value": True,
                                "labels": ["ON", "OFF"],
                                "options": [
                                    {"label": "ON", "value": True},
                                    {"label": "OFF", "value": False},
                                ],
                                "title": "Scheduling",
                                "type": "scheduling_enabled",
                                "values": [True, False],
                            },
                        ],
                        "temperature": 74,
                        "type": "xxl_zone",
                        "zone_status": "",
                    },
                    {
                        "_links": {
                            "self": {
                                "href": (
                                    "https://www.mynexia.com/mobile/xxl_zones/83260997"
                                )
                            }
                        },
                        "cooling_setpoint": 81,
                        "current_zone_mode": "AUTO",
                        "features": [
                            {
                                "actions": {
                                    "set_cool_setpoint": {
                                        "href": (
                                            "https://www.mynexia.com/mobile/xxl_zones"
                                            "/83260997/setpoints"
                                        )
                                    },
                                    "set_heat_setpoint": {
                                        "href": (
                                            "https://www.mynexia.com/mobile/xxl_zones"
                                            "/83260997/setpoints"
                                        )
                                    },
                                },
                                "name": "thermostat",
                                "scale": "f",
                                "setpoint_cool": 81,
                                "setpoint_cool_max": 99,
                                "setpoint_cool_min": 60,
                                "setpoint_delta": 3,
                                "setpoint_heat": 63,
                                "setpoint_heat_max": 90,
                                "setpoint_heat_min": 55,
                                "setpoint_increment": 1.0,
                                "status": "",
                                "status_icon": None,
                                "system_status": "System Idle",
                                "temperature": 75,
                            },
                            {
                                "is_connected": True,
                                "name": "connection",
                                "signal_strength": "unknown",
                            },
                            {
                                "actions": {
                                    "update_thermostat_mode": {
                                        "href": (
                                            "https://www.mynexia.com/mobile/xxl_zones"
                                            "/83260997/zone_mode"
                                        ),
                                        "method": "POST",
                                    }
                                },
                                "display_value": "Auto",
                                "label": "Zone Mode",
                                "name": "thermostat_mode",
                                "options": [
                                    {
                                        "header": True,
                                        "id": "thermostat_mode",
                                        "label": "Zone Mode",
                                        "value": "thermostat_mode",
                                    },
                                    {"label": "Auto", "value": "AUTO"},
                                    {"label": "Cooling", "value": "COOL"},
                                    {"label": "Heating", "value": "HEAT"},
                                    {"label": "Off", "value": "OFF"},
                                ],
                                "value": "AUTO",
                            },
                            {
                                "actions": {
                                    "update_thermostat_run_mode": {
                                        "href": (
                                            "https://www.mynexia.com/mobile"
                                            "/xxl_zones/83260997/run_mode"
                                        ),
                                        "method": "POST",
                                    }
                                },
                                "display_value": "Hold",
                                "label": "Run Mode",
                                "name": "thermostat_run_mode",
                                "options": [
                                    {
                                        "header": True,
                                        "id": "thermostat_run_mode",
                                        "label": "Run Mode",
                                        "value": "thermostat_run_mode",
                                    },
                                    {
                                        "id": "info_text",
                                        "info": True,
                                        "label": "Follow or override the schedule.",
                                        "value": "info_text",
                                    },
                                    {
                                        "label": "Permanent Hold",
                                        "value": "permanent_hold",
                                    },
                                    {"label": "Run Schedule", "value": "run_schedule"},
                                ],
                                "value": "permanent_hold",
                            },
                            {
                                "actions": {
                                    "enable_scheduling": {
                                        "data": {"value": True},
                                        "href": (
                                            "https://www.mynexia.com/mobile/xxl_zones"
                                            "/83260997/scheduling_enabled"
                                        ),
                                        "method": "POST",
                                    },
                                    "get_active_schedule": {
                                        "href": (
                                            "https://www.mynexia.com/mobile"
                                            "/thermostat_schedules"
                                            "/get_active_schedule"
                                            "?device_identifier=XxlZone-83260997"
                                        ),
                                        "method": "POST",
                                    },
                                    "get_default_schedule": {
                                        "href": (
                                            "https://www.mynexia.com/mobile"
                                            "/thermostat_schedules"
                                            "/get_default_schedule"
                                            "?device_identifier=XxlZone-83260997"
                                        ),
                                        "method": "GET",
                                    },
                                    "set_active_schedule": {
                                        "href": (
                                            "https://www.mynexia.com/mobile"
                                            "/thermostat_schedules"
                                            "/set_active_schedule"
                                            "?device_identifier=XxlZone-83260997"
                                        ),
                                        "method": "POST",
                                    },
                                },
                                "can_add_remove_periods": True,
                                "collection_url": (
                                    "https://www.mynexia.com/mobile/schedules"
                                    "?device_identifier=XxlZone-83260997"
                                    "&house_id=123456"
                                ),
                                "enabled": True,
                                "max_period_name_length": 10,
                                "max_periods_per_day": 4,
                                "name": "schedule",
                                "setpoint_increment": 1,
                            },
                        ],
                        "heating_setpoint": 63,
                        "icon": {"modifiers": ["temperature-75"], "name": "thermostat"},
                        "id": 83260997,
                        "name": "West Bedroom",
                        "operating_state": "",
                        "setpoints": {"cool": 81, "heat": 63},
                        "settings": [
                            {
                                "_links": {
                                    "self": {
                                        "href": (
                                            "https://www.mynexia.com/mobile/xxl_zones"
                                            "/83260997/preset_selected"
                                        )
                                    }
                                },
                                "current_value": 0,
                                "labels": ["None", "Home", "Away", "Sleep"],
                                "options": [
                                    {"label": "None", "value": 0},
                                    {"label": "Home", "value": 1},
                                    {"label": "Away", "value": 2},
                                    {"label": "Sleep", "value": 3},
                                ],
                                "title": "Preset",
                                "type": "preset_selected",
                                "values": [0, 1, 2, 3],
                            },
                            {
                                "_links": {
                                    "self": {
                                        "href": (
                                            "https://www.mynexia.com/mobile/xxl_zones"
                                            "/83260997/zone_mode"
                                        )
                                    }
                                },
                                "current_value": "AUTO",
                                "labels": ["Auto", "Cooling", "Heating", "Off"],
                                "options": [
                                    {"label": "Auto", "value": "AUTO"},
                                    {"label": "Cooling", "value": "COOL"},
                                    {"label": "Heating", "value": "HEAT"},
                                    {"label": "Off", "value": "OFF"},
                                ],
                                "title": "Zone Mode",
                                "type": "zone_mode",
                                "values": ["AUTO", "COOL", "HEAT", "OFF"],
                            },
                            {
                                "_links": {
                                    "self": {
                                        "href": (
                                            "https://www.mynexia.com/mobile/xxl_zones"
                                            "/83260997/run_mode"
                                        )
                                    }
                                },
                                "current_value": "permanent_hold",
                                "labels": ["Permanent Hold", "Run Schedule"],
                                "options": [
                                    {
                                        "label": "Permanent Hold",
                                        "value": "permanent_hold",
                                    },
                                    {"label": "Run Schedule", "value": "run_schedule"},
                                ],
                                "title": "Run Mode",
                                "type": "run_mode",
                                "values": ["permanent_hold", "run_schedule"],
                            },
                            {
                                "_links": {
                                    "self": {
                                        "href": (
                                            "https://www.mynexia.com/mobile/xxl_zones"
                                            "/83260997/scheduling_enabled"
                                        )
                                    }
                                },
                                "current_value": True,
                                "labels": ["ON", "OFF"],
                                "options": [
                                    {"label": "ON", "value": True},
                                    {"label": "OFF", "value": False},
                                ],
                                "title": "Scheduling",
                                "type": "scheduling_enabled",
                                "values": [True, False],
                            },
                        ],
                        "temperature": 75,
                        "type": "xxl_zone",
                        "zone_status": "",
                    },
                ],
            },
        ],
        "entry": {"brand": None, "title": "Mock Title"},
    }
