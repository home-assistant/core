"""Communicate class for Habitron system integration."""

import asyncio
import ipaddress
import logging
import os
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

import anyio
from habitron_client import (
    HabitronClient,
    HabitronTimeoutError,
    Module,
    Router,
    apply_event,
    async_refresh_system,
    format_block_output,
    get_host_ip,
    get_own_ip,
)

from homeassistant.components import network
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.loader import async_get_integration

from .const import DOMAIN

if TYPE_CHECKING:
    from .smart_hub import SmartHub

DATA_FILES_ADDON_DIR = "/addon_configs/"
DEF_TOKEN_FILE = "def_token.set"


class HbtnComm:
    """Habitron communication wrapper class mapping to Home Assistant."""

    def __init__(
        self, hass: HomeAssistant, config: ConfigEntry, smhub: SmartHub
    ) -> None:
        """Init CommTest for connection test."""
        self._name: str = "HbtnComm"
        self._host_conf: str = config.data["habitron_host"]
        self.smhub: SmartHub = smhub
        self.logger = logging.getLogger(__name__)

        if self.is_valid_ipv4(self._host_conf):
            self._host = self._host_conf
        else:
            # Hostname/"local" resolution happens in ``async_setup`` to keep
            # blocking DNS off the event loop. The client is constructed
            # there once the resolved host is known.
            self._host = ""

        self.logger.debug(
            "Initializing hub, host conf: %s, initial ip: %s",
            self._host_conf,
            self._host,
        )
        self._port: int = 7777

        # Persistent client. Constructed + connected in ``async_setup`` so the
        # blocking DNS lookup that may be needed for the host stays off the
        # event loop.
        self._client: HabitronClient | None = None

        self._hass: HomeAssistant = hass
        self._config: ConfigEntry = config
        self._hostname: str = ""
        self._hostip: str = self._host
        self._mac: str = ""
        self._hwtype: str = ""
        self._version: str = ""
        self._network_ip: str = ""

        # CRC change-detection key for the bus status stream (the coordinator
        # tick). Other read streams (firmware, single-module status, …) keep
        # their own per-target CRC in ``_stream_crc`` so they cannot clobber
        # this one — sharing a single field made unrelated reads invalidate each
        # other's dedup (extra reads, occasionally a missed status change).
        self.crc: int = 0
        self._stream_crc: dict[str, int] = {}
        self._rtr: Router
        self.update_suspended: bool = False
        self._last_status: bytes = b""  # last compact status, for change detection
        self.is_addon: bool = True  # will be set in get_smhub_info()
        self.slugname: str = ""
        self.info: dict[str, str] = {}
        self.grp_modes: dict[int, int] = {}
        # Integration version reported to the hub. Resolved from the loader in
        # ``async_setup`` (core manifests carry no version, so it stays 0.0.0
        # there); kept off the private ``hass.data`` internals.
        self._hbtn_version: str = "0.0.0"

    @property
    def client(self) -> HabitronClient:
        """Return the connected HabitronClient instance.

        ``async_setup`` constructs and connects the client; calling any wire
        method before then is a programming error.
        """
        if self._client is None:
            raise RuntimeError(
                "HabitronClient is not connected; call async_setup() first"
            )
        return self._client

    @property
    def router(self) -> Router:
        """Return the parsed router model."""
        if not hasattr(self, "_rtr"):
            return self.smhub.router
        return self._rtr

    def _module_by_addr(self, mod_addr: int) -> Module | None:
        """Return the model module with the given full address (or None)."""
        for module in self.router.modules:
            if module.addr == mod_addr:
                return module
        return None

    @property
    def com_ip(self) -> str:
        """IP of SmartHub."""
        return self._hostip

    @property
    def com_port(self) -> int:
        """Port for SmartHub."""
        return self._port

    @property
    def com_mac(self) -> str:
        """Mac address for SmartHub."""
        return self._mac

    @property
    def com_version(self) -> str:
        """Firmware version of SmartHub."""
        return self._version

    @property
    def hbtn_version(self) -> str:
        """Habitron integration version reported to the hub."""
        return self._hbtn_version

    @property
    def com_hwtype(self) -> str:
        """Hardware platform type of SmartHub."""
        return self._hwtype

    @property
    def hostname(self) -> str:
        """Hostname of SmartHub."""
        return self._hostname

    async def async_setup(self) -> None:
        """Resolve the hub host and probe reachability.

        The client uses a fresh socket per command, so ``connect()`` only opens
        and closes a probe socket to fail fast on an unreachable host; no
        connection is kept open afterwards.
        """
        if not self._host:
            if self._host_conf == "local":
                self._host = await self._hass.async_add_executor_job(get_own_ip)
            else:
                self._host = await self._hass.async_add_executor_job(
                    get_host_ip, self._host_conf
                )
        self._network_ip = await network.async_get_source_ip(
            self._hass, target_ip=self._host
        )
        self.logger.info("Resolved network ip: %s", self._network_ip)
        integration = await async_get_integration(self._hass, DOMAIN)
        if integration.version is not None:
            self._hbtn_version = str(integration.version)
        self._client = HabitronClient(self._host, self._port)
        await self._client.connect()

    async def async_close(self) -> None:
        """Release the bus client on entry unload.

        With per-command sockets there is no long-lived connection to tear
        down; this drops the client reference and lets it close any probe
        socket it may still hold.
        """
        if self._client is not None:
            await self._client.close()
            self._client = None

    def is_valid_ipv4(self, ip_string: str) -> bool:
        """Check if a string is a valid IPv4 address."""
        try:
            ipaddress.IPv4Address(ip_string)
        except ValueError:
            return False
        else:
            return True

    def _convert_mod_id(self, mod_id: int) -> int:
        """Helper to calculate module address."""
        return int(mod_id - 100)

    async def send_network_info(self, tok: str) -> None:
        """Send home assistant ipv4."""
        await self.client.send_network_info(
            self._network_ip,
            tok.encode("utf-8"),
            bytes.fromhex(self._mac.replace(":", "").replace("-", "")),
            is_addon=self.is_addon,
            version=self._hbtn_version,
        )
        self.logger.debug("Sent network info to hub - ip: %s", self._network_ip)

    async def reinit_hub(self, mode: int) -> bytes:
        """Restart event server on hub."""
        resp = await self.client.reinit_hub(mode)
        self.logger.info("Re-initialized hub with mode %s", mode)
        return resp

    def set_router(self, rtr: Router) -> None:
        """Register the router model instance."""
        self._rtr = rtr

    async def get_smhub_version(self) -> bytes:
        """Query of SmartHub firmware."""
        return await self.client.get_smhub_version()

    async def get_smhub_info(self) -> dict[str, Any]:
        """Get basic infos of SmartHub."""
        try:
            info = await self.client.get_smhub_info()
            self.info = cast("dict[str, Any]", info)
            self._version = info["software"]["version"]
            self._hwtype = info["hardware"]["platform"]["type"]
            self._hostip = info["hardware"]["network"]["ip"]
            self._hostname = info["hardware"]["network"]["host"]
            self._mac = info["hardware"]["network"]["lan mac"]
            self.is_addon = os.getenv("SUPERVISOR_TOKEN") is not None
            software = cast("dict[str, Any]", info["software"])
            self.slugname = software.get("slug", "") if self.is_addon else ""
            self.logger.debug("SmartHub slugname: %s", self.slugname)
        except HabitronTimeoutError as exc:
            self.logger.error("Timeout connecting to SmartHub at %s", self._host)
            raise HabitronTimeoutError(f"Hub at {self._host} not responding") from exc
        except Exception as exc:
            self.logger.error("Error during SmartHub info fetch: %s", exc)
            raise
        else:
            return cast("dict[str, Any]", info)

    async def get_smhub_update(self) -> dict[str, Any]:
        """Get current sensor and status values."""
        return cast(
            "dict[str, Any]",
            await self.client.get_smhub_update(self._hbtn_version),
        )

    async def get_smr(self) -> bytes:
        """Get router SMR information."""
        return await self.client.get_smr()

    async def async_get_router_status(self) -> bytes:
        """Get router status."""
        return await self.client.get_router_status()

    async def async_get_router_modules(self) -> bytes:
        """Get summary of all Habitron modules of a router."""
        return await self.client.get_router_modules()

    async def get_global_descriptions(self) -> bytes:
        """Get descriptions of commands, etc."""
        return await self.client.get_global_descriptions()

    async def async_get_error_status(self) -> bytes:
        """Get error byte for each module."""
        return await self.client.get_error_status()

    async def async_start_mirror(self) -> None:
        """Start mirror on specified router."""
        await self.client.start_mirror()

    async def async_stop_mirror(self) -> None:
        """Start mirror on specified router."""
        await self.client.stop_mirror()

    async def async_system_update(self) -> int:
        """Poll the bus and update the model in place via the library.

        Delegates to ``async_refresh_system``, which fetches the compact status,
        and—on a CRC change—applies the router status and distributes the status
        to the modules (firing per-member listeners). Returns the status CRC,
        used by the coordinator as its change-detection key
        (``always_update=False``). While suspended the last CRC is returned so
        the tick counts as "unchanged".
        """
        if self.update_suspended:
            # disable update to avoid conflict with SmartConfig or other communication
            return self.crc
        # Refresh the hub-level diagnostics (CPU/memory/...) alongside the bus.
        await self.smhub.update()
        self.crc = await async_refresh_system(
            self.client, self.router, last_crc=self.crc
        )
        return self.crc

    async def async_set_group_mode(self, grp_no: int, new_mode: int) -> None:
        """Set mode for given group."""
        await self.client.set_group_mode(grp_no, new_mode)

    async def async_set_daytime_mode(self, grp_no: int, new_mode: int) -> None:
        """Set mode for given group."""
        mode = 0x42 if new_mode == 1 else 0x43 if new_mode == 2 else None
        if not mode:
            return
        await self.client.set_group_mode(grp_no, mode)

    async def async_set_alarm_mode(self, grp_no: int, alarm_mode: bool) -> None:
        """Set mode for given group."""
        mode = 0x40 if alarm_mode else 0x41
        await self.client.set_group_mode(grp_no, mode)

    async def async_set_log_level(self, hdlr: int, level: int) -> None:
        """Set new logging level."""
        await self.client.set_log_level(hdlr, level)

    async def async_set_output(self, mod_id: int, nmbr: int, val: int) -> None:
        """Send turn_on/turn_off command."""
        await self.client.set_output(self._convert_mod_id(mod_id), nmbr, bool(val))

    async def async_set_led_outp(self, mod_id: int, nmbr: int, val: int) -> None:
        """Translate led nmbr to output nmbr and send on/off command."""
        mod = self._module_by_addr(mod_id)
        if mod is None:
            self.logger.warning("async_set_led_outp: unknown mod_id %s", mod_id)
            return
        await self.async_set_output(mod_id, nmbr + len(mod.outputs), val)

    async def async_set_dimmval(self, mod_id: int, nmbr: int, val: int) -> None:
        """Send value to dimm output."""
        await self.client.set_dimmval(self._convert_mod_id(mod_id), nmbr, val)

    async def async_set_rgb_output(self, mod_id: int, nmbr: int, val: int) -> None:
        """Turn RGB light on/off."""
        await self.client.set_rgb_output(self._convert_mod_id(mod_id), nmbr, bool(val))

    async def async_set_rgbval(self, mod_id: int, nmbr: int, val: list[int]) -> None:
        """Send value to dimm output."""
        await self.client.set_rgbval(self._convert_mod_id(mod_id), nmbr, val)

    async def async_set_shutterpos(self, mod_id: int, nmbr: int, val: int) -> None:
        """Send value to dimm output."""
        await self.client.set_shutterpos(self._convert_mod_id(mod_id), nmbr, val)

    async def async_set_blindtilt(self, mod_id: int, nmbr: int, val: int) -> None:
        """Send value to dimm output."""
        await self.client.set_blindtilt(self._convert_mod_id(mod_id), nmbr, val)

    async def async_set_flag(self, mod_id: int, nmbr: int, val: int) -> None:
        """Send flag on/flag off command."""
        await self.client.set_flag(self._convert_mod_id(mod_id), nmbr, bool(val))

    async def async_inc_dec_counter(self, mod_id: int, nmbr: int, val: int) -> None:
        """Send flag on/flag off command."""
        await self.client.inc_dec_counter(self._convert_mod_id(mod_id), nmbr, val)

    async def async_set_setpoint(self, mod_id: int, nmbr: int, val: int) -> None:
        """Send two byte value for setpoint definition."""
        await self.client.set_setpoint(self._convert_mod_id(mod_id), nmbr, val)

    async def async_set_analog_val(self, mod_id: int, nmbr: int, val: int) -> None:
        """Send byte value for analog output definition."""
        await self.async_set_dimmval(mod_id, 3, val)  # analog output is dimm output 3

    async def async_set_climate_mode(self, mod_id: int, cmode: int, ctl12: int) -> None:
        """Set climate mode for given module."""
        await self.client.set_climate_mode(self._convert_mod_id(mod_id), cmode, ctl12)

    async def async_call_dir_command(self, mod_id: int, nmbr: int) -> None:
        """Call of direct command of nmbr."""
        await self.client.call_dir_command(self._convert_mod_id(mod_id), nmbr)

    async def async_call_vis_command(self, mod_id: int, nmbr: int) -> None:
        """Call of visualization command of nmbr."""
        await self.client.call_vis_command(self._convert_mod_id(mod_id), nmbr)

    async def async_call_coll_command(self, nmbr: int) -> None:
        """Call collective command of nmbr."""
        await self.client.call_coll_command(nmbr)

    async def get_compact_status(self) -> bytes:
        """Get compact status for all modules, if changed crc."""
        resp_bytes, crc = await self.client.get_compact_status()
        if crc == self._stream_crc.get("compact"):
            return b""
        self._stream_crc["compact"] = crc
        return resp_bytes

    async def get_module_status(self, mod_id: int) -> bytes:
        """Get compact status for all modules, if changed crc."""
        resp_bytes, crc = await self.client.get_module_status(
            self._convert_mod_id(mod_id)
        )
        key = f"modstat:{mod_id}"
        if crc == self._stream_crc.get(key):
            return b""
        self._stream_crc[key] = crc
        return resp_bytes

    async def async_get_module_definitions(self, mod_id: int) -> bytes:
        """Get summary of Habitron module: names, commands, etc."""
        return await self.client.get_module_definitions(self._convert_mod_id(mod_id))

    async def async_get_module_settings(self, mod_id: int) -> bytes:
        """Get settings of Habitron module."""
        return await self.client.get_module_settings(self._convert_mod_id(mod_id))

    async def save_module_status(self, mod_id: int) -> None:
        """Get module module status and saves it to file."""
        data = await self.get_module_status(mod_id)
        file_name = f"Module_{mod_id}.mstat"
        await self.save_config_data(file_name, format_block_output(data))

    async def save_router_status(self) -> None:
        """Get module mirror status and saves it to file."""
        data = await self.async_get_router_status()
        file_name = "Router_1.rstat"
        await self.save_config_data(file_name, format_block_output(data))

    async def save_smc_file(self, mod_id: int) -> None:
        """Get module definitions (.smc) and save them to file.

        The library formats the raw definition block (and validates its framing)
        so the integration only writes the resulting text.
        """
        smc = await self.client.get_module_definitions_smc(self._convert_mod_id(mod_id))
        await self.save_config_data(f"Module_{mod_id}.smc", smc)

    async def save_smg_file(self, mod_id: int) -> None:
        """Get module settings (smg) and saves them to file."""
        data = await self.async_get_module_settings(mod_id)
        file_name = f"Module_{mod_id}.smg"
        str_data = "".join(f"{byt};" for byt in data)
        await self.save_config_data(file_name, str_data)

    async def save_smr_file(self) -> None:
        """Get router settings (smr) and saves them to file."""
        data = await self.get_smr()
        file_name = "Router_1.smr"
        str_data = "".join(f"{byt};" for byt in data)
        await self.save_config_data(file_name, str_data)

    async def save_config_data(self, file_name: str, str_data: str) -> None:
        """Save config info to a writable, HA-managed location."""
        data_dir = Path(self._hass.config.path(DOMAIN))
        await self._hass.async_add_executor_job(data_dir.mkdir, 0o755, True, True)
        file_path = data_dir / file_name
        async with await anyio.open_file(
            file_path, "w", encoding="ascii", errors="surrogateescape"
        ) as hbtn_file:
            await hbtn_file.write(str_data)

    async def send_message(self, mod_id: int, msg_id: int) -> None:
        """Send message to module."""
        await self.client.send_message(self._convert_mod_id(mod_id), msg_id)

    async def send_message_text(self, mod_id: int, text: str) -> None:
        """Show a free-text message on a module (empty text clears it)."""
        await self.client.send_message_text(self._convert_mod_id(mod_id), text)

    async def send_sms(self, mod_id: int, msg_id: int, ct_id: int) -> None:
        """Send sms message to module."""
        await self.client.send_sms(self._convert_mod_id(mod_id), msg_id, ct_id)

    async def hub_restart(self) -> None:
        """Restart hub."""
        await self.client.hub_restart()

    async def hub_reboot(self) -> None:
        """Reboot hub."""
        await self.client.hub_reboot()

    async def module_restart(self, mod_nmbr: int) -> None:
        """Restart a single module or all with arg 0xFF or router if arg 0."""
        await self.client.module_restart(mod_nmbr)

    async def restart_fwd_tbl(self) -> None:
        """Restart forwarding table of router."""
        await self.client.restart_fwd_tbl()

    async def handle_firmware(self, mod_nmbr: int) -> bytes:
        """Handle router/module firmware update file status."""
        resp_bytes, crc = await self.client.handle_firmware(mod_nmbr)
        key = f"fw:{mod_nmbr}"
        if crc == self._stream_crc.get(key):
            return b""
        self._stream_crc[key] = crc
        return resp_bytes

    async def update_firmware(self, mod_nmbr: int) -> bytes:
        """Start router/module firmware updates."""
        resp_bytes, crc = await self.client.update_firmware(mod_nmbr)
        key = f"fwupd:{mod_nmbr}"
        if crc == self._stream_crc.get(key):
            return b""
        self._stream_crc[key] = crc
        return resp_bytes

    async def async_power_cycle_channel(self, channel: int) -> None:
        """Power down a router channel and set power on again."""
        await self.client.power_cycle_channel_down(channel)
        await asyncio.sleep(2)
        await self.client.power_cycle_channel_up(channel)

    async def send_devregid(self, mod_nmbr: int, devreg_id: str) -> None:
        """Send device registry id to module."""
        await self.client.send_devregid(mod_nmbr, devreg_id)

    async def update_entity(
        self,
        hub_id: str,
        mod_id: int,
        evnt: int,
        arg1: int,
        arg2: int,
        arg3: int = 0,
        arg4: int = 0,
        arg5: int = 0,
    ) -> None:
        """Event-server handler: feed a SmartHub push event into the model.

        The library's ``apply_event`` updates the matching member and fires its
        listeners (entities write HA state). Event-only behaviour that needs HA
        timing — the finger reset pulse, button device triggers — lives in the
        event platform, which reacts to the member notifications.
        """
        if self._hostip != hub_id:
            return
        apply_event(self.router, mod_id, evnt, arg1, arg2, arg3, arg4, arg5)


# End of communicate definition.
