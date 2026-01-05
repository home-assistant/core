"""ToneWinner RS232 Protocol Handler."""

from __future__ import annotations

from dataclasses import dataclass
import logging

_LOGGER = logging.getLogger(__name__)

# Protocol constants
COMMAND_START = "##"
COMMAND_TERMINATOR = "*"
RESPONSE_OK = "OK"
RESPONSE_ERROR = "ERR"

# Device Categories
# These commands should work across all ToneWinner AV devices (AT-500, AD-7300, etc.)


@dataclass
class Mode:
    """A sound mode for devices, with its corresponding name and label."""

    command: str
    label: str


class ToneWinnerCommands:
    """All available RS232 commands for ToneWinner devices."""

    # Power Commands
    POWER_ON = "POWER ON"
    POWER_OFF = "POWER OFF"
    POWER_QUERY = "POWER ?"

    # Volume Commands
    VOLUME_UP = "VOL UP"
    VOLUME_DOWN = "VOL DN"
    VOLUME_QUERY = "VOL ?"
    VOLUME_SET_PREFIX = "VOL "

    VOLUME_LR_UP = "LR UP"
    VOLUME_LR_DOWN = "LR DN"
    VOLUME_LR_QUERY = "LR ?"
    VOLUME_LR_SET_PREFIX = "LR "

    VOLUME_SUR_UP = "SUR UP"
    VOLUME_SUR_DOWN = "SUR DN"
    VOLUME_SUR_QUERY = "SUR ?"
    VOLUME_SUR_SET_PREFIX = "SUR "

    VOLUME_CEN_UP = "CEN UP"
    VOLUME_CEN_DOWN = "CEN DN"
    VOLUME_CEN_QUERY = "CEN ?"
    VOLUME_CEN_SET_PREFIX = "CEN "

    VOLUME_TOP_UP = "TOP UP"
    VOLUME_TOP_DOWN = "TOP DN"
    VOLUME_TOP_QUERY = "TOP ?"
    VOLUME_TOP_SET_PREFIX = "TOP "

    VOLUME_SUB_UP = "SUB UP"
    VOLUME_SUB_DOWN = "SUB DN"
    VOLUME_SUB_QUERY = "SUB ?"
    VOLUME_SUB_SET_PREFIX = "SUB "

    # Mode Commands

    MODE_UP = "MODE UP"
    MODE_DOWN = "MODE DN"
    MODE_QUERY = "MODE ?"
    MODE_PREFIX = "MODE"
    MODES = {
        "DIRECT": Mode(command="DIRECT", label="Direct"),
        "PURE": Mode(command="PURE", label="Pure"),
        "STEREO": Mode(command="STEREO", label="Stereo"),
        "ALLSTREO": Mode(command="ALLSTREO", label="All Stereo"),
        "PLIIMOVIE": Mode(
            command="PLIIMOVIE", label="Pro Logic IIx Movie (Dolby Upmix)"
        ),
        "PLIIMUSIC": Mode(command="PLIIMUSIC", label="Pro Logic IIx Music"),
        "PLIIHEIGHT": Mode(command="PLIIHEIGHT", label="Pro Logic IIz Height"),
        "PLIIHEIGHTMOVIE": Mode(
            command="PLIIHEIGHTMOVIE", label="Pro Logic IIz Height Movie"
        ),
        "PLIIHEIGHTMUSIC": Mode(
            command="PLIIHEIGHTMUSIC", label="Pro Logic IIz Height Music"
        ),
        "NEO6CINEMA": Mode(command="NEO6CINEMA", label="Neo6:Cinema (DTS Neural)"),
        "NEO6MUSIC": Mode(command="NEO6MUSIC", label="Neo6:Music"),
        "AUTO": Mode(command="AUTO", label="Auto"),
    }

    # Mute Commands
    MUTE_ON = "MUTE ON"
    MUTE_OFF = "MUTE OFF"
    MUTE_QUERY = "MUTE ?"

    # Input Source Commands
    # UP	Set as next input
    # DN	Set as last input
    # ？
    # X
    # **? (* for digit)
    # 1-2 digit，mim 1	Set input as designated NO. input
    # HD*	Set input as designated HDMI port.
    # OP*	Set input as designated opt port.
    # CO*	Set input as designated coaxial port.
    # AN*	Set input as designated analog port.
    # ARC	Set input as HDMI ARC or eARC
    # BT	Set input as bluetooth.
    # TF	Set input as TF card
    # USB	Set input as USB disk.
    # PC	Set input as PC via USB
    INPUT_UP = "SI UP"
    INPUT_DOWN = "SI DN"
    INPUT_QUERY = "SI ?"

    # # Sound Mode Commands
    # SOUND_MODE_STEREO = "LMD00"
    # SOUND_MODE_DIRECT = "LMD01"
    # SOUND_MODE_SURROUND = "LMD02"
    # SOUND_MODE_FILM = "LMD03"
    # SOUND_MODE_MUSIC = "LMD04"
    # SOUND_MODE_GAME = "LMD05"
    # SOUND_MODE_QUERY = "LMDQSTN"

    # # Tone Control
    # BASS_UP = "TBU01"
    # BASS_DOWN = "TBD01"
    # BASS_QUERY = "TBQSTN"
    # TREBLE_UP = "TTU01"
    # TREBLE_DOWN = "TTD01"
    # TREBLE_QUERY = "TTQSTN"

    # # Balance
    # BALANCE_LEFT = "BLT01"
    # BALANCE_RIGHT = "BLR01"
    # BALANCE_CENTER = "BLC01"
    # BALANCE_QUERY = "BLQSTN"

    # # Display/Led Control
    # LED_BRIGHTNESS_UP = "LUU01"
    # LED_BRIGHTNESS_DOWN = "LUD01"
    # LED_BRIGHTNESS_QUERY = "LUQSTN"

    # # Status Queries
    # ALL_STATUS_QUERY = "IFVQTN"  # Returns multiple values

    # # Preset Commands
    # PRESET_LOAD_1 = "PRM01"
    # PRESET_LOAD_2 = "PRM02"
    # PRESET_LOAD_3 = "PRM03"
    # PRESET_SAVE_1 = "PRM11"
    # PRESET_SAVE_2 = "PRM12"
    # PRESET_SAVE_3 = "PRM13"


class ToneWinnerProtocol:
    """Protocol handler for ToneWinner RS232 communication."""

    @staticmethod
    def build_command(command_code: str) -> str:
        """Build a complete command string with terminator."""
        return f"{COMMAND_START}{command_code}{COMMAND_TERMINATOR}"

    @staticmethod
    def build_volume_command(volume_level: int) -> str:
        """Build volume set command.

        Args:
            volume_level: Volume from 0-100 (will be converted to 0-80 hex)

        Returns:
            Complete volume command string
        """
        if not 0 <= volume_level <= 100:
            raise ValueError(f"Volume must be between 0 and 100, got {volume_level}")

        # Convert 0-100 to 0-80 hex
        vol_value = int((volume_level / 100) * 128)
        vol_hex = f"{vol_value:02X}"
        return f"{ToneWinnerCommands.VOLUME_SET_PREFIX}{vol_hex}{COMMAND_TERMINATOR}"

    @staticmethod
    def parse_power_status(response: str) -> bool | None:
        """Parse power status from device response."""
        if not response or not response.startswith("PWR"):
            return None

        # Response format: PWR01 (on) or PWR00 (off)
        return response[3:5] == "01"

    @staticmethod
    def parse_volume_status(response: str) -> float | None:
        """Parse volume level from device response (0-100)."""
        if not response or not response.startswith("MVL"):
            return None

        try:
            # Response format: MVLXX where XX is hex (00-80 = 0-128)
            vol_hex = response[3:5]
            vol_value = int(vol_hex, 16)
            return min(100.0, (vol_value / 128) * 100)
        except (ValueError, IndexError):
            _LOGGER.error("Invalid volume response: %s", response)
            return None

    @staticmethod
    def parse_mute_status(response: str) -> bool | None:
        """Parse mute status from device response."""
        if not response or not response.startswith("AMT"):
            return None

        return response[3:5] == "01"

    @staticmethod
    def parse_input_source(response: str) -> str | None:
        """Parse current input source from response."""
        if not response or not response.startswith("SLI"):
            return None

        source_code = response[3:5]
        source_map = {
            "00": "DVD",
            "01": "Video 1",
            "02": "Video 2",
            "03": "Video 3",
            "04": "Video 4",
            "05": "Video 5",
            "06": "Video 6",
            "07": "Video 7",
            "20": "CD",
            "22": "Tuner",
            "23": "Phono",
            "30": "Multi-channel",
            "40": "USB",
            "41": "Bluetooth",
            "44": "Home Media",
        }
        return source_map.get(source_code, f"Unknown ({source_code})")

    @staticmethod
    def parse_sound_mode(response: str) -> str | None:
        """Parse current sound mode from response."""
        if not response or not response.startswith("LMD"):
            return None

        mode_code = response[3:5]
        mode_map = {
            "00": "Stereo",
            "01": "Direct",
            "02": "Surround",
            "03": "Film",
            "04": "Music",
            "05": "Game",
        }
        return mode_map.get(mode_code, f"Unknown ({mode_code})")

    @staticmethod
    def is_valid_response(response: str) -> bool:
        """Check if response is a valid protocol response."""
        if not response:
            return False

        # Valid responses start with 3-letter command code and have at least 5 chars
        return len(response) >= 5 and response[:3].isalpha()

    @staticmethod
    def extract_numeric_value(response: str, prefix: str) -> int | None:
        """Extract numeric value from response (for bass, treble, balance, etc.)."""
        if not response or not response.startswith(prefix):
            return None

        try:
            # Format: PREFIXXX where XX is hex value
            hex_value = response[len(prefix) : len(prefix) + 2]
            return int(hex_value, 16)
        except (ValueError, IndexError):
            _LOGGER.error("Invalid numeric value in response: %s", response)
            return None


# Mapping of friendly names to command codes for easy access
COMMAND_MAP = {
    "power_on": ToneWinnerCommands.POWER_ON,
    "power_off": ToneWinnerCommands.POWER_OFF,
    "power_query": ToneWinnerCommands.POWER_QUERY,
    "volume_up": ToneWinnerCommands.VOLUME_UP,
    "volume_down": ToneWinnerCommands.VOLUME_DOWN,
    "volume_query": ToneWinnerCommands.VOLUME_QUERY,
    "mute_on": ToneWinnerCommands.MUTE_ON,
    "mute_off": ToneWinnerCommands.MUTE_OFF,
    "mute_query": ToneWinnerCommands.MUTE_QUERY,
    "input_dvd": ToneWinnerCommands.INPUT_DVD,
    "input_video1": ToneWinnerCommands.INPUT_VIDEO1,
    "input_video2": ToneWinnerCommands.INPUT_VIDEO2,
    "input_cd": ToneWinnerCommands.INPUT_CD,
    "input_tuner": ToneWinnerCommands.INPUT_TUNER,
    "input_phono": ToneWinnerCommands.INPUT_PHONO,
    "input_usb": ToneWinnerCommands.INPUT_USB,
    "input_bluetooth": ToneWinnerCommands.INPUT_BLUETOOTH,
    "sound_stereo": ToneWinnerCommands.SOUND_MODE_STEREO,
    "sound_direct": ToneWinnerCommands.SOUND_MODE_DIRECT,
    "sound_surround": ToneWinnerCommands.SOUND_MODE_SURROUND,
    "sound_film": ToneWinnerCommands.SOUND_MODE_FILM,
    "sound_music": ToneWinnerCommands.SOUND_MODE_MUSIC,
    "sound_game": ToneWinnerCommands.SOUND_MODE_GAME,
    "bass_up": ToneWinnerCommands.BASS_UP,
    "bass_down": ToneWinnerCommands.BASS_DOWN,
    "treble_up": ToneWinnerCommands.TREBLE_UP,
    "treble_down": ToneWinnerCommands.TREBLE_DOWN,
    "balance_left": ToneWinnerCommands.BALANCE_LEFT,
    "balance_right": ToneWinnerCommands.BALANCE_RIGHT,
    "balance_center": ToneWinnerCommands.BALANCE_CENTER,
    "led_bright_up": ToneWinnerCommands.LED_BRIGHTNESS_UP,
    "led_bright_down": ToneWinnerCommands.LED_BRIGHTNESS_DOWN,
}
