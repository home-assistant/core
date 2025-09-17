from homeassistant import config_entries
import voluptuous as vol
import logging
from bleak import BleakScanner, BleakClient
import subprocess
import asyncio
import re

_LOGGER = logging.getLogger(__name__)

DOMAIN = "ryse"
PAIRING_MODE_FLAG = 0x01  # LE Limited Discoverable Mode (standard pairing mode)

# Hardcoded UUIDs
HARDCODED_UUIDS = {
    "rx_uuid": "a72f2801-b0bd-498b-b4cd-4a3901388238",
    "tx_uuid": "a72f2802-b0bd-498b-b4cd-4a3901388238",
}


def close_process(process):
    process.stdin.close()
    process.stdout.close()
    process.stderr.close()
    process.wait()


async def run_command(command):
    """Run a bluetoothctl command and return the output."""
    proc = await asyncio.create_subprocess_exec(
        "bluetoothctl",
        *command.split(),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=10.0)
        return {"stdout": stdout, "stderr": stderr, "returncode": proc.returncode}
    except asyncio.TimeoutError:
        proc.kill()
        await proc.wait()
        raise TimeoutError(f"bluetoothctl command timed out: {command}")
    except Exception as e:
        proc.kill()
        await proc.wait()
        raise RuntimeError(f"Command failed: {command} - {str(e)}")


def start_bluetoothctl():
    """Start bluetoothctl as an interactive process."""
    return subprocess.Popen(
        ["bluetoothctl"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1024,
    )


async def send_command_in_process(process, command, delay=2):
    """Send a command to the bluetoothctl process and wait for a response."""
    process.stdin.write(f"{command}\n")
    process.stdin.flush()
    await asyncio.sleep(delay)


async def is_device_connected(address):
    """Check if a Bluetooth device is connected by its MAC address."""
    cmdout = await run_command("devices Connected")
    target_address = address.lower().encode()

    for line in cmdout["stdout"].splitlines():
        # Check if line starts with "Device" followed by MAC address
        if line.lower().startswith(b"device " + target_address):
            return True
    return False


async def is_device_bonded(address):
    """Check if a Bluetooth device is bonded by its MAC address."""
    cmdout = await run_command("devices Bonded")
    target_address = address.lower().encode()

    for line in cmdout["stdout"].splitlines():
        # Check if line starts with "Device" followed by MAC address
        if line.lower().startswith(b"device " + target_address):
            return True
    return False


async def is_device_paired(address):
    """Check if a Bluetooth device is paired by its MAC address."""
    cmdout = await run_command("devices Paired")
    target_address = address.lower().encode()

    for line in cmdout["stdout"].splitlines():
        # Check if line starts with "Device" followed by MAC address
        if line.lower().startswith(b"device " + target_address):
            return True
    return False


async def get_first_manufacturer_data_byte(mac_address: str) -> int:
    """
    Returns the first byte of ManufacturerData.Value for a BLE device using bluetoothctl.
    Returns None if not found.
    """
    # Run bluetoothctl info and capture output
    cmd = ["bluetoothctl", "info", mac_address]
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    # Wait for completion (timeout: 10 sec)
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=10)
    except asyncio.TimeoutError:
        proc.kill()
        await proc.wait()
        _LOGGER.error("bluetoothctl command timed out")
        return None

    # Parse output
    lines = stdout.decode().splitlines()

    for i, line in enumerate(lines):
        if "ManufacturerData.Value" in line:
            # The next line contains the hex bytes (e.g., "cc 64 62 64")
            if (i + 1) < len(lines):
                hex_str = re.search(r"([0-9a-fA-F]{2})", lines[i + 1].strip())
                if hex_str:
                    return int(hex_str.group(1), 16)
    return None


class RyseBLEDeviceConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for RYSE BLE Device."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        if user_input is not None:
            return await self.async_step_scan()

        # Show confirmation popup
        return self.async_show_form(
            step_id="user",
            description_placeholders={
                "info": "Press OK to start scanning for RYSE BLE devices."
            },
            data_schema=vol.Schema({}),  # Empty schema means no input field
            last_step=False,
        )

    async def async_step_scan(self, user_input=None):
        """Handle the BLE device scanning step."""
        if user_input is not None:
            # Extract device name and address from the selected option
            selected_device = next(
                (
                    name
                    for addr, name in self.device_options.items()
                    if addr == user_input["device_address"]
                ),
                None,
            )
            if not selected_device:
                return self.async_abort(reason="Invalid selected device!")

            device_name = selected_device.split(" (")[
                0
            ]  # Extract device name before "("
            device_address = user_input["device_address"]

            try:
                _LOGGER.debug(
                    "Attempting to pair with BLE device: %s (%s)",
                    device_name,
                    device_address,
                )

                max_retries = 3
                retry_count = 0
                while retry_count < max_retries:
                    try:
                        # Start bluetoothctl in interactive mode
                        process = start_bluetoothctl()
                        await send_command_in_process(
                            process, f"trust {device_address}", delay=1
                        )
                        await send_command_in_process(
                            process, f"connect {device_address}", delay=2
                        )
                        await send_command_in_process(process, f"yes", delay=7)
                        idc = await is_device_connected(device_address)
                        idp = await is_device_paired(device_address)
                        if idc and not idp:
                            await send_command_in_process(
                                process, f"pair {device_address}", delay=7
                            )
                        await send_command_in_process(process, "exit", delay=1)
                        close_process(process)

                        idc = await is_device_connected(device_address)
                        idb = await is_device_bonded(device_address)
                        idp = await is_device_paired(device_address)

                        if idc and idb and idp:
                            _LOGGER.debug(
                                f"Connected, Paired and Bonded to {device_address}"
                            )
                            break
                        else:
                            _LOGGER.error(
                                f"Failed to connect and bond(attempt {retry_count + 1})"
                            )
                            _LOGGER.error(
                                f"Connected? {idc} \t Paired? {idp} \t Bonded? {idb}"
                            )
                            retry_count += 1
                            if retry_count >= max_retries:
                                return False
                            await asyncio.sleep(3)  # Wait before retrying
                    except Exception as e:
                        _LOGGER.error(
                            f"Connection error (attempt {retry_count + 1}): {e}"
                        )
                        retry_count += 1
                        if retry_count >= max_retries:
                            return False
                        await asyncio.sleep(3)  # Wait before retrying

                _LOGGER.debug(
                    "Successfully Connected and Bonded with BLE device: %s (%s)",
                    device_name,
                    device_address,
                )

                # Create entry after successful pairing
                return self.async_create_entry(
                    title=f"RYSE gear {device_name}",
                    data={
                        "address": device_address,
                        **HARDCODED_UUIDS,
                    },
                )

            except Exception as e:
                _LOGGER.error(
                    "Error during pairing process for BLE device: %s (%s): %s",
                    device_name,
                    device_address,
                    e,
                )
                return self.async_abort(reason="Pairing failed!")

        # Scan for BLE devices
        devices = await BleakScanner.discover()

        # Debug: Log all discovered devices
        for device in devices:
            _LOGGER.debug(
                "Device Name: %s - Device Address: %s", device.name, device.address
            )

        # Get existing entries to exclude already configured devices
        existing_entries = self._async_current_entries()
        existing_addresses = {entry.data["address"] for entry in existing_entries}

        self.device_options = {}

        for device in devices:
            if not device.name:
                continue  # Ignore unnamed devices
            if device.address in existing_addresses:
                _LOGGER.debug(
                    "Skipping already configured device: %s (%s)",
                    device.name,
                    device.address,
                )
                continue  # Skip already configured devices

            manufacturer_data = device.details["props"].get("ManufacturerData", {})
            raw_data = manufacturer_data.get(0x0409)  # 0x0409 == 1033
            if raw_data is not None:
                btctlMfgdata0 = await get_first_manufacturer_data_byte(device.address)
                _LOGGER.debug(
                    "Found RYSE Device in Pairing mode: %s - address: %s - btctlMfgdata0 %02X",
                    device.name,
                    device.address,
                    btctlMfgdata0,
                )
                # Check if the pairing mode flag (0x40) is in the first byte
                if (
                    len(raw_data) > 0
                    and btctlMfgdata0 is not None
                    and (btctlMfgdata0 & 0x40)
                ):
                    self.device_options[device.address] = (
                        f"{device.name} ({device.address})"
                    )

        if not self.device_options:
            _LOGGER.warning("No BLE devices found in pairing mode (0x40).")
            return self.async_abort(reason="No RYSE devices found in pairing mode!")

        # Show device selection form
        return self.async_show_form(
            step_id="scan",
            data_schema=vol.Schema(
                {
                    vol.Required("device_address"): vol.In(self.device_options),
                }
            ),
            description_placeholders={"info": "Select a RYSE BLE device to pair."},
        )
