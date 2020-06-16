"""Helper functions for the Crownstone integration"""
import asyncio
import threading

from crownstone_uart import CrownstoneUart


class UartManager(threading.Thread):
    def __init__(self) -> None:
        self.loop = asyncio.new_event_loop()
        self.uart_instance = CrownstoneUart(self.loop)
        threading.Thread.__init__(self)

    def run(self) -> None:
        self.loop.run_until_complete(self.initialize_usb())

    async def initialize_usb(self) -> None:
        await self.uart_instance.initialize_usb()

    def stop(self) -> None:
        self.uart_instance.stop()
