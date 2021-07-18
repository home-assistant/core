"""Conftest for the KNX integration."""
from __future__ import annotations

from unittest.mock import AsyncMock, Mock, patch

import pytest
from xknx import XKNX
from xknx.telegram import Telegram

from homeassistant.components.knx.const import DOMAIN as KNX_DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component


class KNXTestKit:
    """Test helper for the KNX integration."""

    def __init__(self, hass: HomeAssistant):
        """Init KNX test helper class."""
        self.hass: HomeAssistant = hass
        self.xknx: XKNX

    async def setup_integration(self, config):
        """Create the KNX integration."""

        def knx_ip_interface_mock():
            """Create a knx ip interface mock."""
            mock = Mock()
            mock.start = AsyncMock()
            mock.stop = AsyncMock()
            mock.send_telegram = AsyncMock()
            return mock

        with patch(
            "xknx.xknx.KNXIPInterface",
            return_value=knx_ip_interface_mock(),
        ):
            await async_setup_component(self.hass, KNX_DOMAIN, {KNX_DOMAIN: config})
            await self.hass.async_block_till_done()
            self.xknx = self.hass.data[KNX_DOMAIN].xknx
            # disable rate limiter for tests
            self.xknx.rate_limit = 0

    def _pop_telegram(self, expected_telegram: str) -> Telegram:
        """Pop oldest outgoing telegram from interface Mock."""
        try:
            return self.xknx.knxip_interface.send_telegram.call_args_list.pop(0)[0][0]
        except IndexError:
            raise AssertionError(f"No Telegram found. Expected: {expected_telegram}")
        finally:
            if not self.xknx.knxip_interface.send_telegram.call_args_list:
                self.xknx.knxip_interface.reset_mock()

    def _list_remaining_telegrams(self) -> str:
        """Return a string containing remaining outgoing telegrams in Mock. One per line."""
        if not self.xknx.knxip_interface.send_telegram.call_args_list:
            return ""
        remaining_telegrams = [
            call[0][0]
            for call in self.xknx.knxip_interface.send_telegram.call_args_list
        ]
        return "\n".join(map(str, remaining_telegrams))

    async def assert_telegram_count(self, count: int):
        """Assert outgoing telegram count since last Mock reset."""
        await self.hass.async_block_till_done()
        actual_count = self.xknx.knxip_interface.send_telegram.call_count
        assert (
            actual_count == count
        ), f"Outgoing telegrams: {actual_count} - Expected: {count}"

    async def assert_write(
        self, group_address: str, payload: list[int, tuple[int, ...]]
    ):
        """Assert outgoing GroupValueWrite telegram. One by one in timely order."""
        await self.hass.async_block_till_done()
        telegram = self._pop_telegram(f"GroupValueWrite {group_address} - {payload}")

        assert (
            str(telegram.destination_address) == group_address
        ), f"Group address mismatch in {telegram} - Expected: {group_address}"
        assert (
            telegram.payload.value.value == payload
        ), f"Payload mismatch in {telegram} - Expected: {payload}"

    async def assert_no_telegram(self):
        """Assert if every telegram was checked by `assert_telegram`. Reset Mocks."""
        await self.hass.async_block_till_done()
        try:
            if telegram_count := len(
                self.xknx.knxip_interface.send_telegram.call_args_list
            ):
                raise AssertionError(
                    f"Found remaining unasserted Telegrams: {telegram_count}\n"
                    f"{self._list_remaining_telegrams()}"
                )
        finally:
            self.xknx.knxip_interface.reset_mock()


@pytest.fixture
async def knx(hass):
    """Create a KNX TestKit instance."""
    knx_test_kit = KNXTestKit(hass)
    yield knx_test_kit
    await knx_test_kit.assert_no_telegram()
