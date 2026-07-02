"""Mertik Maxitrol WiFi fireplace controller."""

import asyncio
import logging
import socket
import time

_LOGGER = logging.getLogger(__name__)

COMMAND_PREFIX = "0233303330333033303830"
STATUS_PREFIXES = ("303030300003", "030300000003")
TCP_PORT = 2000
SOCKET_TIMEOUT = 3
RECV_BUFFER = 4096

CMD_STATUS = "303303"
CMD_APP_MODE = "303103"
CMD_STANDBY = "3136303003"
CMD_IGNITE = "314103"
CMD_GUARD_FLAME_OFF = "313003"
CMD_AUX_ON = "32303031030a"
CMD_AUX_OFF = "32303030030a"
CMD_LIGHT_ON = "3330303103"
CMD_LIGHT_OFF = "3330303003"
CMD_SET_ECO = "4233303103"
CMD_SET_MANUAL = "423003"
CMD_FLAME_PREFIX = "3136"
CMD_FLAME_SUFFIX = "03"
CMD_BRIGHTNESS_PREFIX = "33304645"
CMD_BRIGHTNESS_SUFFIX = "03"
CMD_THERMOSTAT_PREFIX = "4231"
CMD_THERMOSTAT_SUFFIX = "03"

BRIGHTNESS_CODE_MAX = "4642"
BRIGHTNESS_CODE_MIN = "3633"

FLAME_HEIGHT_STEPS = [
    "3830",
    "3842",
    "3937",
    "4132",
    "4145",
    "4239",
    "4335",
    "4430",
    "4443",
    "4537",
    "4633",
    "4646",
]

STATUS_ON_FLAG = slice(14, 16)
STATUS_BITS = slice(16, 20)
STATUS_FLAME_HEIGHT = slice(18, 20)
# [22:24] = 0x04 in every observed packet (constant, purpose unknown).
# [24:26] = mode/state indicator — 0x00 manual, 0x20 thermostatic active.
#           NOT the fault code: 0x20 ≠ F04 (which would need to be 0x04).
# Fault codes likely arrive in a separate packet type that does not match
# STATUS_PREFIXES. To identify it: enable DEBUG logging, trigger F16
# (handset out of range for 1.5 h), then look for unusual "no status packet"
# entries in the log that appear when the app shows the error code.
STATUS_MODE_BYTE = slice(24, 26)
STATUS_HANDSET_FAULT = slice(28, 30)  # 0x00=OK, 0x06=F44 (handset disconnected)
STATUS_INTERNAL_TEMP = slice(30, 32)  # near-firebox sensor, ~10°C, not useful
STATUS_AMBIENT_TEMP = slice(34, 36)  # actual room temperature

# Maps raw handset-fault byte values to Mertik F-code numbers.
# The byte at STATUS_HANDSET_FAULT (position [28:30]) encodes handset errors
# using device-internal values that don't equal the public F-code numbers.
HANDSET_FAULT_TO_FCODE: dict[int, int] = {
    0x06: 44,  # F44: handset not in range or low battery
}

FLAME_OFF_THRESHOLD = 123

BIT_SHUTTING_DOWN = 7
BIT_GUARD_FLAME = 8
BIT_IGNITING = 11
BIT_AUX_ON = 9


class Mertik:
    def __init__(self, ip: str) -> None:
        self.ip = ip
        self._ambient_temperature = 0.0

        # Flame height and aux are tracked locally from commands.
        # The device's status packet flame field always reports the
        # post-ignition baseline (0x8F=step2) regardless of what
        # set_flame_height() commands have been sent. The aux bit
        # is unreliable due to delayed responses from the handshake
        # commands corrupting the recv() sequence.
        self.flameHeight = 0  # local command-tracked value
        self._local_aux = False  # local command-tracked aux state

        # These come from the status packet (reliable)
        self.on = False
        self.flame_on = False
        self._shutting_down = False
        self._guard_flame_on = False
        self._igniting = False
        self._prev_flame_on = False
        self._handset_fault = 0  # 0 = OK, 0x06 = F44 (handset not connected)

        self.client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.client.settimeout(SOCKET_TIMEOUT)
        self.client.connect((self.ip, TCP_PORT))
        self._startup_sequence()

    @classmethod
    async def async_connect(cls, ip: str) -> "Mertik":
        """Create a Mertik instance and open the TCP connection via executor."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, cls, ip)

    def _startup_sequence(self) -> None:
        """APP mode startup sequence.

        CMD_GUARD_FLAME_OFF is NOT sent at startup. When it was included,
        it put the device into a state where the status packet flame field
        was stuck at the post-ignition baseline (0x8F) regardless of
        set_flame_height() commands, breaking flame height feedback.

        CMD_50FF00 / CMD_50FF01 / CMD_C2 are also NOT sent - they time out
        and their delayed responses corrupt subsequent recv() calls.

        Safety note: to ensure the fire is off after an HA restart, add
        an HA automation triggered by the 'Home Assistant Start' event
        that calls the Fireplace switch turn_off service.
        """
        self._send_command(CMD_STATUS)
        self._send_command(CMD_APP_MODE)

    @property
    def is_on(self) -> bool:
        return self.on

    @property
    def is_flame_on(self) -> bool:
        return self.flame_on

    @property
    def is_aux_on(self) -> bool:
        """Aux state tracked locally from commands (status bit unreliable)."""
        return self._local_aux and self.flame_on

    @property
    def is_shutting_down(self) -> bool:
        return self._shutting_down

    @property
    def is_igniting(self) -> bool:
        return self._igniting

    @property
    def fault_code(self) -> int:
        """Return the active fault as an F-code number (e.g. 44 for F44), or 0."""
        return HANDSET_FAULT_TO_FCODE.get(self._handset_fault, 0)

    @property
    def is_handset_connected(self) -> bool:
        return self._handset_fault == 0

    @property
    def ambient_temperature(self) -> float:
        return self._ambient_temperature

    def standBy(self) -> None:
        self._send_command(CMD_STANDBY)
        self._local_aux = False
        self.flameHeight = 0

    def aux_on(self) -> None:
        self._send_command(CMD_AUX_ON)
        self._local_aux = True

    def aux_off(self) -> None:
        self._send_command(CMD_AUX_OFF)
        self._local_aux = False

    def ignite_fireplace(self) -> None:
        """Ignite and immediately send aux_on.

        Both burners light physically at ignition. We send aux_on straight
        after so that:
        1. The Rear Burner switch shows On (accurate physical state)
        2. The user can then turn aux off if they only want the front burner
        """
        self._send_command(CMD_IGNITE)
        self._local_aux = True  # set locally before aux_on command
        self._send_command(CMD_AUX_ON)
        self.flameHeight = 1  # reset flame to step 1 at ignition

    def refresh_status(self) -> None:
        self._send_command(CMD_STATUS)

    async def close(self) -> None:
        try:
            self.client.close()
        except OSError:
            pass

    def guard_flame_off(self) -> None:
        self._send_command(CMD_GUARD_FLAME_OFF)
        self._local_aux = False
        self.flameHeight = 0

    def light_on(self) -> None:
        self._send_command(CMD_LIGHT_ON)

    def light_off(self) -> None:
        self._send_command(CMD_LIGHT_OFF)

    def set_light_brightness(self, brightness: int) -> None:
        normalized = (brightness - 1) / 254 * 100
        if normalized == 100:
            device_code = BRIGHTNESS_CODE_MAX
        elif normalized == 0:
            device_code = BRIGHTNESS_CODE_MIN
        else:
            level = 36 + round(normalized / 100 * 8)
            if level >= 40:
                level += 1
            device_code = f"{level:02d}{level:02d}"
        self._send_command(
            f"{CMD_BRIGHTNESS_PREFIX}{device_code}{CMD_BRIGHTNESS_SUFFIX}"
        )

    def set_eco(self) -> None:
        self._send_command(CMD_SET_ECO)

    def set_manual(self) -> None:
        self._send_command(CMD_SET_MANUAL)

    def set_thermostat(self, temp_celsius: float) -> None:
        snapped = round(temp_celsius * 2) / 2.0
        snapped = max(5.0, min(36.0, snapped))
        half_degrees = int(snapped * 2)
        hex_chars = f"{half_degrees:02X}"
        self._send_command(f"{CMD_THERMOSTAT_PREFIX}{hex_chars}{CMD_THERMOSTAT_SUFFIX}")

    def get_flame_height(self) -> int:
        """Return locally tracked flame height (command-based, not status-based).

        The status packet flame field always reports the post-ignition
        baseline value (0x8F = step 2) regardless of set_flame_height()
        commands. Physical flame changes are confirmed by device beep and
        ACK responses. We track the requested value locally.
        """
        return self.flameHeight

    def set_flame_height(self, flame_height: int) -> None:
        """Set flame to step 1-13. Updates local tracker on ACK."""
        idx = max(0, min(11, int(flame_height) - 1))
        step_code = FLAME_HEIGHT_STEPS[idx]
        self._send_command(f"{CMD_FLAME_PREFIX}{step_code}{CMD_FLAME_SUFFIX}")
        # Update local tracker - command confirmed by device ACK
        self.flameHeight = int(flame_height)
        self.refresh_status()

    def _hex_to_bin(self, hex_str: str) -> str:
        return format(int(hex_str, 16), "b").zfill(len(hex_str) * 4)

    def _bit_at(self, hex_str: str, index: int) -> bool:
        return self._hex_to_bin(hex_str)[index : index + 1] == "1"

    def _reconnect(self) -> None:
        """Reconnect and re-run startup sequence."""
        _LOGGER.warning("Reconnecting to %s:%s", self.ip, TCP_PORT)
        try:
            self.client.close()
        except Exception:
            pass
        time.sleep(1)
        self.client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.client.settimeout(SOCKET_TIMEOUT)
        self.client.connect((self.ip, TCP_PORT))
        self._startup_sequence()

    def _send_command(self, msg: str) -> None:
        """Send a command and consume its response.

        Always reads the response, keeping the TCP buffer in sync.
        Searches for a status packet anywhere in the received data.
        """
        payload = bytearray.fromhex(COMMAND_PREFIX + msg)
        try:
            self.client.send(payload)
        except socket.error:
            _LOGGER.warning("Send failed, reconnecting to %s", self.ip)
            self._reconnect()
            try:
                self.client.send(payload)
            except socket.error as err:
                _LOGGER.error("Send failed after reconnect: %s", err)
                return

        try:
            data = self.client.recv(RECV_BUFFER)
        except socket.timeout:
            _LOGGER.debug("No response to command %s (timeout)", msg)
            return

        if not data:
            _LOGGER.warning("Empty response, reconnecting to %s", self.ip)
            self._reconnect()
            try:
                self.client.send(payload)
                data = self.client.recv(RECV_BUFFER)
            except (socket.error, socket.timeout):
                return

        _LOGGER.debug("RAW RESPONSE hex=%s", data.hex())
        self._parse_any_status(data)

    def _parse_any_status(self, data: bytes) -> None:
        """Find and parse a status packet anywhere in received data."""
        text = data.decode("ascii", errors="replace")
        for prefix in STATUS_PREFIXES:
            idx = text.find(prefix)
            if idx != -1:
                self._process_status(text[idx:])
                return
        _LOGGER.debug("Response contains no status packet: %s", data.hex())

    def _process_status(self, status_str: str) -> None:
        _LOGGER.debug("STATUS PACKET (len=%d): %s", len(status_str), status_str)

        if len(status_str) < 32:
            return

        # ON/OFF flag (reliable)
        on_flag = status_str[STATUS_ON_FLAG]
        if on_flag == "FF":
            self.on = True
        elif on_flag == "00":
            self.on = False

        # Flame-on from status (used for is_on/is_flame_on)
        # NOTE: flame height is NOT read from status - it's tracked locally.
        try:
            raw_flame = int(status_str[STATUS_FLAME_HEIGHT], 16)
            self._prev_flame_on = self.flame_on
            new_flame_on = raw_flame > FLAME_OFF_THRESHOLD
            self.flame_on = new_flame_on

            # Only reset local trackers on the FALLING EDGE (True -> False).
            # During ignition the device sends transitional packets with
            # flame_raw < threshold even though the fire is starting.
            # Resetting on every False reading would clear _local_aux and
            # flameHeight set by ignite_fireplace() before they take effect.
            if self._prev_flame_on and not new_flame_on:
                # Fire confirmed off (was on, now off)
                self._local_aux = False
                self.flameHeight = 0
            # Do NOT read flameHeight from raw_flame - status always reports
            # post-ignition baseline (0x8F) regardless of set_flame_height().
        except ValueError:
            pass

        # Status bits (shutting down, guard, igniting only - not aux)
        try:
            status_bits = status_str[STATUS_BITS]
            self._shutting_down = self._bit_at(status_bits, BIT_SHUTTING_DOWN)
            self._guard_flame_on = self._bit_at(status_bits, BIT_GUARD_FLAME)
            self._igniting = self._bit_at(status_bits, BIT_IGNITING)
            # AUX bit NOT read here - tracked locally via aux_on()/aux_off()
        except (ValueError, IndexError):
            pass

        # [24:26] = mode byte — 0x00 manual, 0x20 thermostatic active.
        # [28:30] = handset fault — 0x00=OK, 0x06=F44 (handset not connected).
        _LOGGER.debug(
            "Status extras — mode_byte=%s unknown[26:28]=%s handset_fault=%s internal_temp=%s",
            status_str[24:26],
            status_str[26:28],
            status_str[28:30],
            status_str[30:32],
        )
        try:
            self._handset_fault = int(status_str[STATUS_HANDSET_FAULT], 16)
        except (ValueError, IndexError):
            pass

        # Temperature (reliable)
        try:
            raw_temp = int(status_str[STATUS_AMBIENT_TEMP], 16)
            if raw_temp > 0:
                self._ambient_temperature = raw_temp / 10
        except (ValueError, IndexError):
            pass
