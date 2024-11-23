"""Constants for the jvc_projector integration."""

from jvcprojector import const

NAME = "JVC Projector"
DOMAIN = "jvc_projector"
MANUFACTURER = "JVC"

REMOTE_COMMANDS = {
    "menu": const.REMOTE_MENU,
    "up": const.REMOTE_UP,
    "down": const.REMOTE_DOWN,
    "left": const.REMOTE_LEFT,
    "right": const.REMOTE_RIGHT,
    "ok": const.REMOTE_OK,
    "back": const.REMOTE_BACK,
    "mpc": const.REMOTE_MPC,
    "hide": const.REMOTE_HIDE,
    "info": const.REMOTE_INFO,
    "input": const.REMOTE_INPUT,
    "cmd": const.REMOTE_CMD,
    "advanced_menu": const.REMOTE_ADVANCED_MENU,
    "picture_mode": const.REMOTE_PICTURE_MODE,
    "color_profile": const.REMOTE_COLOR_PROFILE,
    "lens_control": const.REMOTE_LENS_CONTROL,
    "setting_memory": const.REMOTE_SETTING_MEMORY,
    "gamma_settings": const.REMOTE_GAMMA_SETTINGS,
    "hdmi_1": const.REMOTE_HDMI_1,
    "hdmi_2": const.REMOTE_HDMI_2,
    "mode_1": const.REMOTE_MODE_1,
    "mode_2": const.REMOTE_MODE_2,
    "mode_3": const.REMOTE_MODE_3,
    "lens_ap": const.REMOTE_LENS_AP,
    "gamma": const.REMOTE_GAMMA,
    "color_temp": const.REMOTE_COLOR_TEMP,
    "natural": const.REMOTE_NATURAL,
    "cinema": const.REMOTE_CINEMA,
    "anamo": const.REMOTE_ANAMO,
    "3d_format": const.REMOTE_3D_FORMAT,
}
