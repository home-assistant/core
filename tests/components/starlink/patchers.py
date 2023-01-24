"""General Starlink patchers."""
from unittest.mock import patch

from starlink_grpc import ObstructionDict, StatusDict

SETUP_ENTRY_PATCHER = patch(
    "homeassistant.components.starlink.async_setup_entry", return_value=True
)

COORDINATOR_SUCCESS_PATCHER = patch(
    "homeassistant.components.starlink.coordinator.status_data",
    return_value=[
        StatusDict(
            id="some-id",
            hardware_version="rev3_proto2",
            software_version="6ac8c726-f096-45a5-9f02-c026b2a65e78.uterm.release",
            state="CONNECTED",
            uptime=61257,
            snr=None,
            seconds_to_first_nonempty_slot=0.0,
            pop_ping_drop_rate=0.0,
            downlink_throughput_bps=93507.8125,
            uplink_throughput_bps=66261.6171875,
            pop_ping_latency_ms=36.599998474121094,
            alerts=256,
            fraction_obstructed=0.0,
            currently_obstructed=False,
            seconds_obstructed=None,
            obstruction_duration=None,
            obstruction_interval=None,
            direction_azimuth=-178.26171875,
            direction_elevation=69.2221908569336,
            is_snr_above_noise_floor=True,
        ),
        ObstructionDict(
            wedges_fraction_obstructed=[
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                None,
            ],
            raw_wedges_fraction_obstructed=[
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                None,
            ],
            valid_s=60988.0,
        ),
        {
            "alert_motors_stuck": False,
            "alert_thermal_throttle": False,
            "alert_thermal_shutdown": False,
            "alert_mast_not_near_vertical": False,
            "alert_unexpected_location": False,
            "alert_slow_ethernet_speeds": False,
            "alert_roaming": False,
            "alert_install_pending": False,
            "alert_is_heating": True,
            "alert_power_supply_thermal_throttle": False,
            "alert_is_power_save_idle": False,
            "alert_moving_while_not_mobile": False,
            "alert_moving_fast_while_not_aviation": False,
        },
    ],
)

DEVICE_FOUND_PATCHER = patch(
    "homeassistant.components.starlink.config_flow.get_id", return_value="some-valid-id"
)

NO_DEVICE_PATCHER = patch(
    "homeassistant.components.starlink.config_flow.get_id", return_value=None
)
