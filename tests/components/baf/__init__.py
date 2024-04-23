"""Tests for the Big Ass Fans integration."""

import asyncio

from aiobafi6 import Device

MOCK_UUID = "1234"
MOCK_NAME = "Living Room Fan"


class MockBAFDevice(Device):
    """A simple mock for a BAF Device."""

    def __init__(self, async_wait_available_side_effect=None):
        """Init simple mock."""
        self._async_wait_available_side_effect = async_wait_available_side_effect

    @property
    def dns_sd_uuid(self):
        """Mock the unique id."""
        return MOCK_UUID

    @property
    def name(self):
        """Mock the name of the device."""
        return MOCK_NAME

    async def async_wait_available(self):
        """Mock async_wait_available."""
        if self._async_wait_available_side_effect:
            raise self._async_wait_available_side_effect

    def async_run(self):
        """Mock async_run."""
        return asyncio.Future()
