"""Support for Enocean commucation through modbus."""
# mypy: allow-untyped-defs
import asyncio
import logging
import time

from enocean.communicators.communicator import Communicator, ESP_Version

from homeassistant.core import HomeAssistant

from .modbusenoceanadapter import ModbusEnoceanAdapter


class ModbusEnoceanCommunicator(Communicator):
    """Serial port communicator class for EnOcean radio."""

    logger = logging.getLogger("enocean.communicators.ModbusEnoceanCommunicator")

    def __init__(
        self,
        hass: HomeAssistant,
        adapter: ModbusEnoceanAdapter,
        esp_version: int,
        callback=None,
    ):
        """Initialize modbus enocean communcator."""
        super().__init__(version=esp_version, callback=callback)
        self._adapter = adapter
        self.hass = hass
        self._esp_version = esp_version

    def run(self):
        """Run modbus enocean communcator thread."""
        self.logger.info("ModbusEnoceanCommunicator started")
        # Reuse loop of hass to synchronize calls to modbus adapter
        loop = self.hass.loop
        while not self._stop_flag.is_set():
            # If there's messages in transmit queue
            # send them
            while True:
                packet = self._get_from_send_queue()
                if not packet:
                    break
                try:
                    asyncio.run_coroutine_threadsafe(
                        self._adapter.write(bytearray(packet.build())), loop
                    ).result()
                except Exception:
                    self.stop()

            # Read chars from serial port as hex numbers
            try:
                packet_size = 14 if self._esp_version == ESP_Version.ESP2.value else 16
                packet = asyncio.run_coroutine_threadsafe(
                    self._adapter.read(packet_size), loop
                ).result()
                self._buffer.extend(bytearray(packet))
            except Exception as err:
                self.logger.error("Modbus exception! exception=%s", err)
                self.stop()
            self.parse()
            time.sleep(0)

        self.logger.info("ModbusEnoceanCommunicator stopped")
