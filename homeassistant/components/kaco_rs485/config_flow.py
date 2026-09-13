"""Config flow.

`SerialPortSelector` covers both local devices and ESPHome proxies, so no host
or key is stored. Addresses are scanned for rather than asked: they are set in
each inverter's own display menu and nothing announces them.
"""

import asyncio
from typing import Any, override

from kaco_rs485 import AsyncBus, BusError
from kaco_rs485.discovery import ALL_ADDRESSES, Discovered, ScanResult, scan
import voluptuous as vol

from homeassistant.components import usb
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_MODEL, CONF_PORT
from homeassistant.helpers.selector import SerialPortSelector

from .const import CONF_ADDRESSES, CONF_INVERTERS, CONF_SW_VERSION, DOMAIN, LOGGER


def _label(device: Discovered) -> str:
    """Address, plus the reported type when the scan could read one."""
    if not device.inverter_type:
        return str(device.address)
    return f"{device.address} — {device.inverter_type}"


class KacoRs485ConfigFlow(ConfigFlow, domain=DOMAIN):
    """Pick a port, scan it, confirm what was found."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the flow."""
        self._port: str | None = None
        self._result: ScanResult | None = None
        self._scan_task: asyncio.Task[ScanResult | None] | None = None

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Choose the serial port, and check it opens before scanning it."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self._port = await self._stable_path(user_input[CONF_PORT])
            self._scan_task = None
            # No unique id available: xi units return zero bytes for `s`.
            self._async_abort_entries_match({CONF_PORT: self._port})
            try:
                async with AsyncBus(self._port):
                    pass
            except BusError:
                LOGGER.debug("Could not open %s", self._port, exc_info=True)
                errors["base"] = "cannot_connect"
            else:
                return await self.async_step_scan()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_PORT): SerialPortSelector()}),
            errors=errors,
        )

    async def async_step_scan(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Run the bus scan as a background task, showing progress.

        Not inline: every empty address costs a full reply timeout, so a
        sparse bus takes a minute.

        Re-entrant — the task handle is cleared in `async_step_user`, never
        here, or a re-entry would start a second scan.
        """
        assert self._port is not None

        if self._scan_task is None:
            self._scan_task = self.hass.async_create_task(self._scan(self._port))

        if not self._scan_task.done():
            return self.async_show_progress(
                step_id="scan",
                progress_action="scanning",
                progress_task=self._scan_task,
            )

        self._result = self._scan_task.result()
        if self._result is None:
            return self.async_show_progress_done(next_step_id="cannot_connect")

        return self.async_show_progress_done(next_step_id="confirm")

    async def async_step_cannot_connect(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Report a port that could not be opened.

        A step of its own because a progress step may only hand off to another
        step, and `user` would re-scan the same dead port.
        """
        return self.async_abort(reason="cannot_connect")

    async def async_step_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show what the scan found and let the user adjust it."""
        assert self._port is not None
        assert self._result is not None

        supported = self._result.supported

        if not supported:
            if unsupported := self._result.unsupported:
                # It answered; "nothing answered" sends them back for the same.
                return self.async_abort(
                    reason="only_unsupported",
                    description_placeholders={
                        "unsupported": ", ".join(str(d.address) for d in unsupported)
                    },
                )
            # Silence means a wiring fault or dusk, and we cannot tell which.
            return self.async_abort(reason="no_inverters")

        if user_input is not None:
            return self.async_create_entry(
                title=await self._title(self._port),
                data={
                    CONF_PORT: self._port,
                    CONF_ADDRESSES: [d.address for d in supported],
                    CONF_INVERTERS: {
                        str(d.address): {
                            CONF_MODEL: d.inverter_type,
                            CONF_SW_VERSION: d.firmware,
                        }
                        for d in supported
                    },
                },
            )

        # Every inverter found is added. One that should not be polled is
        # disabled afterwards, which drops it from the cycle as well.
        return self.async_show_form(
            step_id="confirm",
            description_placeholders={"found": ", ".join(_label(d) for d in supported)},
        )

    async def _stable_path(self, port: str) -> str:
        """Resolve a local device to its /dev/serial/by-id path.

        `/dev/ttyUSB0` is assigned in probe order, so replugging renumbers it.
        The by-id path encodes the adapter's USB serial and survives that.
        """
        if not port.startswith("/dev/"):
            return port
        try:
            return await self.hass.async_add_executor_job(usb.get_serial_by_id, port)
        except OSError:
            LOGGER.debug("Could not resolve %s to a by-id path", port, exc_info=True)
            return port

    async def _title(self, port: str) -> str:
        """Name the entry after the port's description, not its URL.

        A proxied port is an opaque URL naming another integration's entry id;
        `usb` already knows it as, say, "AtomS3 Lite RS485 (RS-485)".
        """
        try:
            ports = await usb.async_scan_serial_ports(self.hass)
        except OSError:
            LOGGER.debug("Could not scan serial ports to name %s", port, exc_info=True)
            return port

        for candidate in ports:
            if candidate.device == port:
                return candidate.description or port
        return port

    async def _scan(self, port: str) -> ScanResult | None:
        """Probe the whole bus, or return None if the port could not be used.

        Reports rather than raises: a failed progress task leaves Home
        Assistant to decide what to do with the exception.
        """
        LOGGER.debug("Scanning %s for KACO inverters", port)

        def report(done: int, total: int) -> None:
            self.async_update_progress(done / total)

        try:
            async with AsyncBus(port) as bus:
                return await scan(bus, ALL_ADDRESSES, on_progress=report)
        except BusError:
            LOGGER.exception("Scanning %s failed", port)
            return None
