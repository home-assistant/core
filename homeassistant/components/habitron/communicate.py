"""Communicate class for Habitron system integration."""

import ipaddress
import logging
from typing import Any, cast

from habitron_client import (
    HabitronClient,
    HabitronTimeoutError,
    Router,
    async_refresh_system,
    get_host_ip,
    get_own_ip,
)

from homeassistant.components import network
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.loader import async_get_integration

from .const import DOMAIN

DATA_FILES_ADDON_DIR = "/addon_configs/"
DEF_TOKEN_FILE = "def_token.set"


class HbtnComm:
    """Habitron communication wrapper class mapping to Home Assistant."""

    def __init__(self, hass: HomeAssistant, config: ConfigEntry) -> None:
        """Init CommTest for connection test."""
        self._name: str = "HbtnComm"
        self._host_conf: str = config.data["habitron_host"]
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
        # Empty model until ``set_router`` stores the built one.
        self._rtr: Router = Router()
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
        return self._rtr

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
                # get_own_ip is a plain blocking socket call, so it runs in the
                # executor. get_host_ip resolves the name itself with async DNS,
                # so it must be awaited directly -- handing it to the executor
                # would only build the coroutine and assign that, unrun, to
                # self._host.
                self._host = await self._hass.async_add_executor_job(get_own_ip)
            else:
                self._host = await get_host_ip(self._host_conf)
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
            software = cast("dict[str, Any]", info["software"])
            # The SmartHub reports its own ingress slug only when it runs as the
            # Home Assistant add-on; an external/standalone unit reports the
            # literal sentinel "none" (or omits the slug). Deriving is_addon from
            # this target-reported value is correct even when *this* HA is
            # supervised but the target hub is external — unlike the local
            # SUPERVISOR_TOKEN, which only describes this HA.
            slug = software.get("slug", "")
            self.is_addon = slug not in ("", "none")
            self.slugname = slug if self.is_addon else ""
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
        self.crc = await async_refresh_system(
            self.client, self.router, last_crc=self.crc
        )
        return self.crc

    async def send_devregid(self, mod_nmbr: int, devreg_id: str) -> None:
        """Send device registry id to module."""
        await self.client.send_devregid(mod_nmbr, devreg_id)
