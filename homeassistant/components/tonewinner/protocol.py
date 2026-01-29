"""Tonewinner RS232 Protocol Handler."""

from __future__ import annotations

from dataclasses import dataclass
import logging
import re

_LOGGER = logging.getLogger(__name__)

# Protocol constants
COMMAND_START = "##"
COMMAND_TERMINATOR = "*"
RESPONSE_OK = "OK"
RESPONSE_ERROR = "ERR"

# Device Categories
# These commands should work across all Tonewinner AV devices (AT-500, AD-7300, etc.)


@dataclass
class Mode:
    """A sound mode for devices, with its corresponding name and label."""

    command: str
    label: str


class TonewinnerCommands:
    """All available RS232 commands for Tonewinner devices."""

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
        # There's a bug in firmware V1.02.0796 where the unit reports "DITECT"
        # instead of "DIRECT"
        "DITECT": Mode(command="DIRECT", label="Direct"),
        "PURE": Mode(command="PURE", label="Pure"),
        "STEREO": Mode(command="STEREO", label="Stereo"),
        "ALLSTEREO": Mode(command="ALLSTEREO", label="All Stereo"),
        # There's a bug in firmware V1.02.0796 where the unit reports "ALLSTREO"
        # instead of "ALLSTEREO"
        "ALLSTREO": Mode(command="ALLSTEREO", label="All Stereo"),
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
    # 1-2 digit，min 1	Set input as designated NO. input
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


class TonewinnerProtocol:
    """Protocol handler for Tonewinner RS232 communication."""

    @staticmethod
    def build_command(command_code: str) -> str:
        """Build a complete command string with terminator."""
        _LOGGER.debug("Building command for: '%s'", command_code)
        result = f"{COMMAND_START}{command_code}{COMMAND_TERMINATOR}"
        _LOGGER.debug("Built command: '%s'", result)
        return result

    @staticmethod
    def build_volume_command(volume_level: float) -> str:
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
        vol_hex = f"{vol_value}"
        return f"{TonewinnerCommands.VOLUME_SET_PREFIX} {vol_hex}"

    @staticmethod
    def parse_power_status(response: str) -> bool | None:
        """Parse power status from device response."""
        _LOGGER.debug("Parsing power status from: '%s'", response)
        if not response or not response.startswith("POWER"):
            _LOGGER.debug("Not a power response")
            return None

        # Response format: POWER ON or POWER OFF
        is_on = response[6:8] == "ON"
        _LOGGER.debug("Power status parsed: %s", "ON" if is_on else "OFF")
        return is_on

    @staticmethod
    def parse_volume_status(response: str) -> float | None:
        """Parse volume level from device response (0-80)."""
        _LOGGER.debug("Parsing volume from: '%s'", response)
        if not response or not response.startswith("VOL"):
            _LOGGER.debug("Not a volume response")
            return None

        try:
            # Response format: VOL XX.X where XX.X is 0-80 in 0.5 steps
            vol = response[4:8]
            vol_value = float(vol)
            return min(80.0, (vol_value / 80) * 80)
        except (ValueError, IndexError):
            _LOGGER.error("Invalid volume response: %s", response)
            return None

    @staticmethod
    def parse_mute_status(response: str) -> bool | None:
        """Parse mute status from device response."""
        _LOGGER.debug("Parsing mute from: '%s'", response)
        if not response or not response.startswith("MUTE"):
            _LOGGER.debug("Not a mute response")
            return None

        is_muted = response[5:7] == "ON"
        _LOGGER.debug("Mute status parsed: %s", "ON" if is_muted else "OFF")
        return is_muted

    @staticmethod
    def parse_input_source(response: str) -> tuple[str, str | None] | None:
        """Parse current input source from response."""
        _LOGGER.debug("Parsing input source from: '%s'", response)
        if not response or not response.startswith("SI"):
            _LOGGER.debug("Not an input source response")
            return None

        source = response[6:]
        _LOGGER.debug("Input source raw data: '%s'", source)

        # Strip `V=(<video>\w+) A=(<audio>\w+)$` from the end using regex, extracting their params to log
        match = re.search(r"(?P<name>.+) V=(?P<video>\w+) A=(?P<audio>\w+)$", source)
        if match:
            source_name = match.group("name")
            video_source = match.group("video")
            audio_source = match.group("audio")
            _LOGGER.debug(
                "Input source: %s (Video source: %s, Audio source: %s)",
                source_name,
                video_source,
                audio_source,
            )
            return source_name, audio_source

        # If no match for V= A= format, try just returning the source name directly
        # Some responses may just be "SI CO1" or similar
        source_stripped = source.strip()
        if source_stripped:
            _LOGGER.debug("Input source (simple format): %s", source_stripped)
            return source_stripped, None

        _LOGGER.debug("Invalid input source format: %s", source)
        return None

    @staticmethod
    def parse_sound_mode(response: str) -> str | None:
        """Parse current sound mode from response."""
        _LOGGER.debug("Parsing sound mode from: '%s'", response)
        if not response or not response.startswith("MODE"):
            _LOGGER.debug("Not a sound mode response")
            return None

        mode_code = response[5:]
        _LOGGER.debug("Sound mode code: '%s'", mode_code)
        mode = TonewinnerCommands.MODES.get(mode_code)
        result = mode.label if mode else f"Unknown ({mode_code})"
        _LOGGER.debug("Sound mode parsed: %s", result)
        return result

    @staticmethod
    def is_valid_response(response: str) -> bool:
        """Check if response is a valid protocol response."""
        if not response:
            return False

        ## TODO figure out better parsing here maybe
        return True
