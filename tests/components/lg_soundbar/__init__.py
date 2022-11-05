"""Tests for the lg_soundbar component."""
from __future__ import annotations

from collections.abc import Callable
from typing import Any
from unittest.mock import DEFAULT, MagicMock

from homeassistant.components.lg_soundbar.const import DEFAULT_PORT
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant

MOCK_CONFIG = {CONF_HOST: "127.0.0.1", CONF_PORT: DEFAULT_PORT}
MOCK_ENTITY_ID = "mock_entity_id"
MOCK_MP_ENTITY_ID = "media_player.lg_soundbar_" + MOCK_ENTITY_ID
MOCK_TEMESCAL_EQUALISERS = [
    "Standard",
    "Bass",
    "Flat",
    "Boost",
    "Treble and Bass",
    "User",
    "Music",
    "Cinema",
    "Night",
    "News",
    "Voice",
    "ia_sound",
    "Adaptive Sound Control",
    "Movie",
    "Bass Blast",
    "Dolby Atmos",
    "DTS Virtual X",
    "Bass Boost Plus",
    "DTS X",
    "AI Sound Pro",
    "Clear Voice",
    "Sports",
    "Game",
]
MOCK_TEMESCAL_FUNCTIONS = [
    "Wi-Fi",
    "Bluetooth",
    "Portable",
    "Aux",
    "Optical",
    "CP",
    "HDMI",
    "ARC",
    "Spotify",
    "Optical2",
    "HDMI2",
    "HDMI3",
    "LG TV",
    "Mic",
    "Chromecast",
    "Optical/HDMI ARC",
    "LG Optical",
    "FM",
    "USB",
    "USB2",
    "E-ARC",
]

TEMESCAL_ATTR_UUID = "s_uuid"
TEMESCAL_ATTR_USERNAME = "s_user_name"

TEMESCAL_EQ_VIEW_INFO = "EQ_VIEW_INFO"
TEMESCAL_FUNC_VIEW_INFO = "FUNC_VIEW_INFO"
TEMESCAL_MAC_INFO_DEV = "MAC_INFO_DEV"
TEMESCAL_PRODUCT_INFO = "PRODUCT_INFO"
TEMESCAL_SETTING_VIEW_INFO = "SETTING_VIEW_INFO"
TEMESCAL_SPK_LIST_VIEW_INFO = "SPK_LIST_VIEW_INFO"

TEMESCAL_RESPONSES = {
    TEMESCAL_EQ_VIEW_INFO: {
        "i_curr_eq": 19,
        "i_bass": 5,
        "i_treble": 10,
        "ai_eq_list": [19, 0, 6, 7, 20, 21, 22, 14, 5, 15, 23, 24, 25],
        "merdian_eq_list": [6],
    },
    TEMESCAL_FUNC_VIEW_INFO: {
        "b_connect": True,
        "i_curr_func": 15,
        "s_bt_name": "d",
        "s_spk_bt_name": "bt name",
        "ai_func_list": [0, 1, 15, 6, 19],
    },
    TEMESCAL_PRODUCT_INFO: {
        "i_network_type": 1,
        "i_model_no": 0,
        "i_model_type": 0,
        "s_model_name": "S90QY",
        "s_product_id": "P017",
        "s_product_name": "WiFi Speaker",
        "s_uuid": MOCK_ENTITY_ID,
        "b_admin_mode": False,
    },
    TEMESCAL_SETTING_VIEW_INFO: {
        "b_drc": True,
        "b_auto_vol": True,
        "b_auto_power": True,
        "b_tv_remote": True,
        "b_night_time": False,
        "b_rear": True,
        "b_enable_imax": True,
        "b_support_diag": True,
        "b_neuralx": True,
        "b_enable_dialog": False,
        "b_set_device_name": True,
        "b_support_avsmrm": True,
        "b_avsmrm_status": False,
        "b_soundbarmode": False,
        "b_wow_connect": False,
        "b_nighttime_enable": True,
        "i_av_sync": 0,
        "i_woofer_level": 12,
        "i_woofer_min": -15,
        "i_woofer_max": 6,
        "i_rear_level": 9,
        "i_rear_min": -6,
        "i_rear_max": 6,
        "i_top_level": 8,
        "i_top_min": -6,
        "i_top_max": 6,
        "i_center_level": 12,
        "i_center_min": -6,
        "i_center_max": 6,
        "i_side_level": 8,
        "i_side_min": -6,
        "i_side_max": 6,
        "i_dialog_level": 0,
        "i_dialog_min": 0,
        "i_dialog_max": 6,
        "i_curr_eq": 19,
        "i_calibration_status": 3,
        "s_user_name": "LG sound bar",
        "s_ipv4_addr": "127.0.0.1",
        "s_ipv6_addr": "",
    },
    TEMESCAL_SPK_LIST_VIEW_INFO: {
        "i_vol": 10,
        "i_vol_min": 0,
        "i_vol_max": 40,
        "i_curr_func": 15,
        "b_mute": False,
        "b_support_avsmrm": True,
        "b_avsmrm_status": False,
        "b_spotify_connect": False,
        "b_func_pictogram": True,
        "b_soundbarmode": False,
        "b_wow_connect": False,
        "i_calibration_status": 3,
        "i_year": 22,
        "i_model_option": 1,
        "i_color_option": 0,
        "b_update": False,
        "b_powerstatus": False,
        "b_display_volume_text": True,
        "s_user_name": "LG sound bar",
        "s_audio_source": "NO SIGNAL",
    },
}


def _msg_to_temescal_func(msg: str, mock: MagicMock) -> MagicMock:
    """Map LG soundbar API messages to the mocked function that responds to the message."""
    return {
        TEMESCAL_EQ_VIEW_INFO: mock.get_eq,
        TEMESCAL_FUNC_VIEW_INFO: mock.get_func,
        TEMESCAL_MAC_INFO_DEV: mock.get_mac_info,
        TEMESCAL_PRODUCT_INFO: mock.get_product_info,
        TEMESCAL_SETTING_VIEW_INFO: mock.get_settings,
        TEMESCAL_SPK_LIST_VIEW_INFO: mock.get_info,
    }.get(msg)


def setup_mock_temescal(
    hass: HomeAssistant,
    mock_temescal: MagicMock,
    msg_dicts: dict[str, dict[str, Any]] = None,
):
    """Set up a mock of the temescal object to craft our expected responses."""
    tmock = mock_temescal.temescal
    instance = tmock.return_value

    def create_temescal_response(msg: str, data: dict | None = None) -> dict[str, Any]:
        response: dict[str, Any] = {"msg": msg}
        if data is not None:
            response["data"] = data
        return response

    def temescal_side_effect(
        addr: str, port: int, callback: Callable[[dict[str, Any]], None]
    ):
        def _hass_add_job(
            func: MagicMock,
            msg: str,
            response: dict[str, Any],
        ):
            func.side_effect = lambda: hass.add_job(
                callback, create_temescal_response(msg=msg, data=response)
            )

        for key in msg_dicts.keys():
            func = _msg_to_temescal_func(key, instance)
            if func is not None:
                _hass_add_job(func, key, msg_dicts[key])
        return DEFAULT

    mock_temescal.equalisers = MOCK_TEMESCAL_EQUALISERS
    mock_temescal.functions = MOCK_TEMESCAL_FUNCTIONS
    tmock.side_effect = temescal_side_effect
