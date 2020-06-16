"""Helper functions/classes for Crownstone."""
import asyncio
import threading

from crownstone_uart import CrownstoneUart


class UartManager(threading.Thread):
    """Uart manager that manages usb connections."""

    def __init__(self) -> None:
        """Init with new event loop and instance."""
        self.loop = asyncio.new_event_loop()
        self.uart_instance = CrownstoneUart(self.loop)
        threading.Thread.__init__(self)

    def run(self) -> None:
        """Run this function in the thread."""
        self.loop.run_until_complete(self.initialize_usb())

    async def initialize_usb(self) -> None:
        """
        Manage USB connections.

        This function runs until Home Assistant is stopped.
        """
        await self.uart_instance.initialize_usb()

    def stop(self) -> None:
        """Stop the uart manager."""
        self.uart_instance.stop()
