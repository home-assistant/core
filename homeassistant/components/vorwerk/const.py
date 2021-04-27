"""Constants for Vorwerk integration."""
from datetime import timedelta

VORWERK_DOMAIN = "vorwerk"

VORWERK_ROBOTS = "robots"
VORWERK_ROBOT_API = "robot_api"
VORWERK_ROBOT_COORDINATOR = "robot_coordinator"

VORWERK_ROBOT_NAME = "name"
VORWERK_ROBOT_SERIAL = "serial"
VORWERK_ROBOT_SECRET = "secret"
VORWERK_ROBOT_TRAITS = "traits"
VORWERK_ROBOT_ENDPOINT = "endpoint"

VORWERK_PLATFORMS = ["vacuum"]

# The client_id is the same for all users.
VORWERK_CLIENT_ID = "KY4YbVAvtgB7lp8vIbWQ7zLk3hssZlhR"

MIN_TIME_BETWEEN_UPDATES = timedelta(minutes=1)

ATTR_NAVIGATION = "navigation"
ATTR_CATEGORY = "category"
ATTR_ZONE = "zone"

ROBOT_STATE_INVALID = 0
ROBOT_STATE_IDLE = 1
ROBOT_STATE_BUSY = 2
ROBOT_STATE_PAUSE = 3
ROBOT_STATE_ERROR = 4

ROBOT_ACTION_INVALID = 0
ROBOT_ACTION_HOUSE_CLEANING = 1
ROBOT_ACTION_SPOT_CLEANING = 2
ROBOT_ACTION_MANUAL_CLEANING = 3
ROBOT_ACTION_DOCKING = 4
ROBOT_ACTION_USER_MENU = 5
ROBOT_ACTION_SUSPENDED_CLEANING = 6
ROBOT_ACTION_UPDATING = 7
ROBOT_ACTION_COPY_LOGS = 8
ROBOT_ACTION_RECOVERING_LOCATION = 9
ROBOT_ACTION_IEC_TEST = 10
ROBOT_ACTION_MAP_CLEANING = 11
ROBOT_ACTION_EXPLORING_MAP = 12
ROBOT_ACTION_ACQUIRING_MAP_IDS = 13
ROBOT_ACTION_UPLOADING_MAP = 14
ROBOT_ACTION_SUSPENDED_EXPLORATION = 15

ROBOT_CLEANING_ACTIONS = [
    ROBOT_ACTION_HOUSE_CLEANING,
    ROBOT_ACTION_SPOT_CLEANING,
    ROBOT_ACTION_MANUAL_CLEANING,
    ROBOT_ACTION_SUSPENDED_CLEANING,
    ROBOT_ACTION_MAP_CLEANING,
    ROBOT_ACTION_EXPLORING_MAP,
    ROBOT_ACTION_SUSPENDED_EXPLORATION,
]

ACTION = {
    ROBOT_ACTION_INVALID: "Invalid",
    ROBOT_ACTION_HOUSE_CLEANING: "House Cleaning",
    ROBOT_ACTION_SPOT_CLEANING: "Spot Cleaning",
    ROBOT_ACTION_MANUAL_CLEANING: "Manual Cleaning",
    ROBOT_ACTION_DOCKING: "Docking",
    ROBOT_ACTION_USER_MENU: "User Menu Active",
    ROBOT_ACTION_SUSPENDED_CLEANING: "Suspended Cleaning",
    ROBOT_ACTION_UPDATING: "Updating",
    ROBOT_ACTION_COPY_LOGS: "Copying logs",
    ROBOT_ACTION_RECOVERING_LOCATION: "Recovering Location",
    ROBOT_ACTION_IEC_TEST: "IEC test",
    ROBOT_ACTION_MAP_CLEANING: "Map cleaning",
    ROBOT_ACTION_EXPLORING_MAP: "Exploring map (creating a persistent map)",
    ROBOT_ACTION_ACQUIRING_MAP_IDS: "Acquiring Persistent Map IDs",
    ROBOT_ACTION_UPLOADING_MAP: "Creating & Uploading Map",
    ROBOT_ACTION_SUSPENDED_EXPLORATION: "Suspended Exploration",
}

MODE = {1: "Eco", 2: "Turbo"}

ERRORS = {
    "ui_error_battery_battundervoltlithiumsafety": "Replace battery",
    "ui_error_battery_critical": "Replace battery",
    "ui_error_battery_invalidsensor": "Replace battery",
    "ui_error_battery_lithiumadapterfailure": "Replace battery",
    "ui_error_battery_mismatch": "Replace battery",
    "ui_error_battery_nothermistor": "Replace battery",
    "ui_error_battery_overtemp": "Replace battery",
    "ui_error_battery_overvolt": "Replace battery",
    "ui_error_battery_undercurrent": "Replace battery",
    "ui_error_battery_undertemp": "Replace battery",
    "ui_error_battery_undervolt": "Replace battery",
    "ui_error_battery_unplugged": "Replace battery",
    "ui_error_brush_stuck": "Brush stuck",
    "ui_error_brush_overloaded": "Brush overloaded",
    "ui_error_bumper_stuck": "Bumper stuck",
    "ui_error_check_battery_switch": "Check battery",
    "ui_error_corrupt_scb": "Call customer service corrupt board",
    "ui_error_deck_debris": "Deck debris",
    "ui_error_dflt_app": "Check MyKobold app",
    "ui_error_disconnect_chrg_cable": "Disconnected charge cable",
    "ui_error_disconnect_usb_cable": "Disconnected USB cable",
    "ui_error_dust_bin_missing": "Dust bin missing",
    "ui_error_dust_bin_full": "Dust bin full",
    "ui_error_dust_bin_emptied": "Dust bin emptied",
    "ui_error_hardware_failure": "Hardware failure",
    "ui_error_ldrop_stuck": "Clear my path",
    "ui_error_lds_jammed": "Clear my path",
    "ui_error_lds_bad_packets": "Check MyKobold app",
    "ui_error_lds_disconnected": "Check MyKobold app",
    "ui_error_lds_missed_packets": "Check MyKobold app",
    "ui_error_lwheel_stuck": "Clear my path",
    "ui_error_navigation_backdrop_frontbump": "Clear my path",
    "ui_error_navigation_backdrop_leftbump": "Clear my path",
    "ui_error_navigation_backdrop_wheelextended": "Clear my path",
    "ui_error_navigation_noprogress": "Clear my path",
    "ui_error_navigation_origin_unclean": "Clear my path",
    "ui_error_navigation_pathproblems": "Cannot return to base",
    "ui_error_navigation_pinkycommsfail": "Clear my path",
    "ui_error_navigation_falling": "Clear my path",
    "ui_error_navigation_noexitstogo": "Clear my path",
    "ui_error_navigation_nomotioncommands": "Clear my path",
    "ui_error_navigation_rightdrop_leftbump": "Clear my path",
    "ui_error_navigation_undockingfailed": "Clear my path",
    "ui_error_picked_up": "Picked up",
    "ui_error_qa_fail": "Check MyKobold app",
    "ui_error_rdrop_stuck": "Clear my path",
    "ui_error_reconnect_failed": "Reconnect failed",
    "ui_error_rwheel_stuck": "Clear my path",
    "ui_error_stuck": "Stuck!",
    "ui_error_unable_to_return_to_base": "Unable to return to base",
    "ui_error_unable_to_see": "Clean vacuum sensors",
    "ui_error_vacuum_slip": "Clear my path",
    "ui_error_vacuum_stuck": "Clear my path",
    "ui_error_warning": "Error check app",
    "batt_base_connect_fail": "Battery failed to connect to base",
    "batt_base_no_power": "Battery base has no power",
    "batt_low": "Battery low",
    "batt_on_base": "Battery on base",
    "clean_tilt_on_start": "Clean the tilt on start",
    "dustbin_full": "Dust bin full",
    "dustbin_missing": "Dust bin missing",
    "gen_picked_up": "Picked up",
    "hw_fail": "Hardware failure",
    "hw_tof_sensor_sensor": "Hardware sensor disconnected",
    "lds_bad_packets": "Bad packets",
    "lds_deck_debris": "Debris on deck",
    "lds_disconnected": "Disconnected",
    "lds_jammed": "Jammed",
    "lds_missed_packets": "Missed packets",
    "maint_brush_stuck": "Brush stuck",
    "maint_brush_overload": "Brush overloaded",
    "maint_bumper_stuck": "Bumper stuck",
    "maint_customer_support_qa": "Contact customer support",
    "maint_vacuum_stuck": "Vacuum is stuck",
    "maint_vacuum_slip": "Vacuum is stuck",
    "maint_left_drop_stuck": "Vacuum is stuck",
    "maint_left_wheel_stuck": "Vacuum is stuck",
    "maint_right_drop_stuck": "Vacuum is stuck",
    "maint_right_wheel_stuck": "Vacuum is stuck",
    "not_on_charge_base": "Not on the charge base",
    "nav_robot_falling": "Clear my path",
    "nav_no_path": "Clear my path",
    "nav_path_problem": "Clear my path",
    "nav_backdrop_frontbump": "Clear my path",
    "nav_backdrop_leftbump": "Clear my path",
    "nav_backdrop_wheelextended": "Clear my path",
    "nav_mag_sensor": "Clear my path",
    "nav_no_exit": "Clear my path",
    "nav_no_movement": "Clear my path",
    "nav_rightdrop_leftbump": "Clear my path",
    "nav_undocking_failed": "Clear my path",
}

ALERTS = {
    "ui_alert_dust_bin_full": "Please empty dust bin",
    "ui_alert_recovering_location": "Returning to start",
    "ui_alert_battery_chargebasecommerr": "Battery error",
    "ui_alert_busy_charging": "Busy charging",
    "ui_alert_charging_base": "Base charging",
    "ui_alert_charging_power": "Charging power",
    "ui_alert_connect_chrg_cable": "Connect charge cable",
    "ui_alert_info_thank_you": "Thank you",
    "ui_alert_invalid": "Invalid check app",
    "ui_alert_old_error": "Old error",
    "ui_alert_swupdate_fail": "Update failed",
    "dustbin_full": "Please empty dust bin",
    "maint_brush_change": "Change the brush",
    "maint_filter_change": "Change the filter",
    "clean_completed_to_start": "Cleaning completed",
    "nav_floorplan_not_created": "No floorplan found",
    "nav_floorplan_load_fail": "Failed to load floorplan",
    "nav_floorplan_localization_fail": "Failed to load floorplan",
    "clean_incomplete_to_start": "Cleaning incomplete",
    "log_upload_failed": "Logs failed to upload",
}
