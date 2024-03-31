"""Support for configurable supported data values for the ScreenLogic integration."""

from screenlogicpy.const.data import DEVICE, VALUE

ENTITY_MIGRATIONS = {
    "chem_alarm": {
        "new_key": VALUE.ACTIVE_ALERT,
        "old_name": "Chemistry Alarm",
        "new_name": "Active Alert",
    },
    "chem_calcium_harness": {
        "new_key": VALUE.CALCIUM_HARDNESS,
    },
    "calcium_harness": {
        "new_key": VALUE.CALCIUM_HARDNESS,
    },
    "chem_current_orp": {
        "new_key": VALUE.ORP_NOW,
        "old_name": "Current ORP",
        "new_name": "ORP Now",
    },
    "chem_current_ph": {
        "new_key": VALUE.PH_NOW,
        "old_name": "Current pH",
        "new_name": "pH Now",
    },
    "chem_cya": {
        "new_key": VALUE.CYA,
    },
    "chem_orp_dosing_state": {
        "new_key": VALUE.ORP_DOSING_STATE,
    },
    "chem_orp_last_dose_time": {
        "new_key": VALUE.ORP_LAST_DOSE_TIME,
    },
    "chem_orp_last_dose_volume": {
        "new_key": VALUE.ORP_LAST_DOSE_VOLUME,
    },
    "chem_orp_setpoint": {
        "new_key": VALUE.ORP_SETPOINT,
    },
    "chem_orp_supply_level": {
        "new_key": VALUE.ORP_SUPPLY_LEVEL,
    },
    "chem_ph_dosing_state": {
        "new_key": VALUE.PH_DOSING_STATE,
    },
    "chem_ph_last_dose_time": {
        "new_key": VALUE.PH_LAST_DOSE_TIME,
    },
    "chem_ph_last_dose_volume": {
        "new_key": VALUE.PH_LAST_DOSE_VOLUME,
    },
    "chem_ph_probe_water_temp": {
        "new_key": VALUE.PH_PROBE_WATER_TEMP,
    },
    "chem_ph_setpoint": {
        "new_key": VALUE.PH_SETPOINT,
    },
    "chem_ph_supply_level": {
        "new_key": VALUE.PH_SUPPLY_LEVEL,
    },
    "chem_salt_tds_ppm": {
        "new_key": VALUE.SALT_TDS_PPM,
    },
    "chem_total_alkalinity": {
        "new_key": VALUE.TOTAL_ALKALINITY,
    },
    "currentGPM": {
        "new_key": VALUE.GPM_NOW,
        "old_name": "Current GPM",
        "new_name": "GPM Now",
        "device": DEVICE.PUMP,
    },
    "currentRPM": {
        "new_key": VALUE.RPM_NOW,
        "old_name": "Current RPM",
        "new_name": "RPM Now",
        "device": DEVICE.PUMP,
    },
    "currentWatts": {
        "new_key": VALUE.WATTS_NOW,
        "old_name": "Current Watts",
        "new_name": "Watts Now",
        "device": DEVICE.PUMP,
    },
    "orp_alarm": {
        "new_key": VALUE.ORP_LOW_ALARM,
        "old_name": "ORP Alarm",
        "new_name": "ORP LOW Alarm",
    },
    "ph_alarm": {
        "new_key": VALUE.PH_HIGH_ALARM,
        "old_name": "pH Alarm",
        "new_name": "pH HIGH Alarm",
    },
    "scg_status": {
        "new_key": VALUE.STATE,
        "old_name": "SCG Status",
        "new_name": "Chlorinator",
        "device": DEVICE.SCG,
    },
    "scg_level1": {
        "new_key": VALUE.POOL_SETPOINT,
        "old_name": "Pool SCG Level",
        "new_name": "Pool Chlorinator Setpoint",
    },
    "scg_level2": {
        "new_key": VALUE.SPA_SETPOINT,
        "old_name": "Spa SCG Level",
        "new_name": "Spa Chlorinator Setpoint",
    },
    "scg_salt_ppm": {
        "new_key": VALUE.SALT_PPM,
        "old_name": "SCG Salt",
        "new_name": "Chlorinator Salt",
        "device": DEVICE.SCG,
    },
    "scg_super_chlor_timer": {
        "new_key": VALUE.SUPER_CHLOR_TIMER,
        "old_name": "SCG Super Chlorination Timer",
        "new_name": "Super Chlorination Timer",
    },
}
