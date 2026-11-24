"""Tests for the Hi-Link HLK-SW16 integration."""

import asyncio


class MockSW16Client:
    """Class to mock the SW16Client client."""

    def __init__(self, fail) -> None:
        """Initialise client with failure modes."""
        self.fail = fail
        self.disconnect_callback = None
        self.in_transaction = False
        self.active_transaction = None

    async def setup(self):
        """Mock successful setup."""
        fut = asyncio.Future()
        fut.set_result(True)
        return fut

    async def status(self):
        """Mock status based on failure mode."""
        self.in_transaction = True
        self.active_transaction = asyncio.Future()
        if self.fail:
            if self.disconnect_callback:
                self.disconnect_callback()
            return await self.active_transaction
        self.active_transaction.set_result(True)
        return self.active_transaction

    def stop(self):
        """Mock client stop."""
        self.in_transaction = False
        self.active_transaction = None


async def create_mock_hlk_sw16_connection(fail):
    """Create a mock HLK-SW16 client."""
    client = MockSW16Client(fail)
    await client.setup()
    return client
