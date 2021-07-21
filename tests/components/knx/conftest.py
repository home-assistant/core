"""Conftest for the KNX integration."""
from __future__ import annotations

import asyncio
from unittest.mock import DEFAULT, AsyncMock, Mock, patch

import pytest
from xknx import XKNX
from xknx.dpt import DPTArray, DPTBinary
from xknx.telegram import Telegram, TelegramDirection
from xknx.telegram.address import GroupAddress, IndividualAddress
from xknx.telegram.apci import APCI, GroupValueRead, GroupValueResponse, GroupValueWrite

from homeassistant.components.knx.const import DOMAIN as KNX_DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component


class KNXTestKit:
    """Test helper for the KNX integration."""

    def __init__(self, hass: HomeAssistant):
        """Init KNX test helper class."""
        self.hass: HomeAssistant = hass
        self.xknx: XKNX
        # outgoing telegrams will be put in the Queue instead of sent to the interface
        # telegrams to an InternalGroupAddress won't be queued here
        self._outgoing_telegrams: asyncio.Queue = asyncio.Queue()

    async def setup_integration(self, config):
        """Create the KNX integration."""

        def knx_ip_interface_mock():
            """Create a xknx knx ip interface mock."""
            mock = Mock()
            mock.start = AsyncMock()
            mock.stop = AsyncMock()
            mock.send_telegram = AsyncMock(side_effect=self._outgoing_telegrams.put)
            return mock

        def fish_xknx(*args, **kwargs):
            """Get the XKNX object from the constructor call."""
            self.xknx = args[0]
            # disable rate limiter for tests (before StateUpdater starts)
            self.xknx.rate_limit = 0
            return DEFAULT

        with patch(
            "xknx.xknx.KNXIPInterface",
            return_value=knx_ip_interface_mock(),
            side_effect=fish_xknx,
        ):
            await async_setup_component(self.hass, KNX_DOMAIN, {KNX_DOMAIN: config})
            await self.hass.async_block_till_done()

    ########################
    # Telegram counter tests
    ########################

    def _list_remaining_telegrams(self) -> str:
        """Return a string containing remaining outgoing telegrams in test Queue. One per line."""
        remaining_telegrams = []
        while not self._outgoing_telegrams.empty():
            remaining_telegrams.append(self._outgoing_telegrams.get_nowait())
        return "\n".join(map(str, remaining_telegrams))

    async def assert_no_telegram(self) -> None:
        """Assert if every telegram in test Queue was checked."""
        await self.hass.async_block_till_done()
        assert self._outgoing_telegrams.empty(), (
            f"Found remaining unasserted Telegrams: {self._outgoing_telegrams.qsize()}\n"
            f"{self._list_remaining_telegrams()}"
        )

    async def assert_telegram_count(self, count: int) -> None:
        """Assert outgoing telegram count in test Queue."""
        await self.hass.async_block_till_done()
        actual_count = self._outgoing_telegrams.qsize()
        assert actual_count == count, (
            f"Outgoing telegrams: {actual_count} - Expected: {count}\n"
            f"{self._list_remaining_telegrams()}"
        )

    ####################
    # APCI Service tests
    ####################

    async def _assert_telegram(
        self,
        group_address: str,
        payload: int | tuple[int, ...] | None,
        apci_type: type[APCI],
    ) -> None:
        """Assert outgoing telegram. One by one in timely order."""
        await self.hass.async_block_till_done()
        try:
            telegram = self._outgoing_telegrams.get_nowait()
        except asyncio.QueueEmpty:
            raise AssertionError(
                f"No Telegram found. Expected: {apci_type.__name__} -"
                f" {group_address} - {payload}"
            )

        assert isinstance(
            telegram.payload, apci_type
        ), f"APCI type mismatch in {telegram} - Expected: {apci_type.__name__}"

        assert (
            str(telegram.destination_address) == group_address
        ), f"Group address mismatch in {telegram} - Expected: {group_address}"

        if payload is not None:
            assert (
                telegram.payload.value.value == payload  # type: ignore
            ), f"Payload mismatch in {telegram} - Expected: {payload}"

    async def assert_read(self, group_address: str) -> None:
        """Assert outgoing GroupValueRead telegram. One by one in timely order."""
        await self._assert_telegram(group_address, None, GroupValueRead)

    async def assert_response(
        self, group_address: str, payload: int | tuple[int, ...]
    ) -> None:
        """Assert outgoing GroupValueResponse telegram. One by one in timely order."""
        await self._assert_telegram(group_address, payload, GroupValueResponse)

    async def assert_write(
        self, group_address: str, payload: int | tuple[int, ...]
    ) -> None:
        """Assert outgoing GroupValueWrite telegram. One by one in timely order."""
        await self._assert_telegram(group_address, payload, GroupValueWrite)

    ####################
    # Incoming telegrams
    ####################

    @staticmethod
    def _payload_value(payload: int | tuple[int, ...]) -> DPTArray | DPTBinary:
        """Prepare payload value for GroupValueWrite or GroupValueResponse."""
        if isinstance(payload, int):
            return DPTBinary(payload)
        return DPTArray(payload)

    async def _receive_telegram(self, group_address: str, payload: APCI) -> None:
        """Inject incoming KNX telegram."""
        self.xknx.telegrams.put_nowait(
            Telegram(
                destination_address=GroupAddress(group_address),
                direction=TelegramDirection.INCOMING,
                payload=payload,
                source_address=IndividualAddress("1.2.3"),
            )
        )
        await self.hass.async_block_till_done()

    async def receive_read(
        self,
        group_address: str,
    ) -> None:
        """Inject incoming GroupValueRead telegram."""
        await self._receive_telegram(group_address, GroupValueRead())

    async def receive_response(
        self, group_address: str, payload: int | tuple[int, ...]
    ) -> None:
        """Inject incoming GroupValueResponse telegram."""
        payload_value = self._payload_value(payload)
        await self._receive_telegram(group_address, GroupValueResponse(payload_value))

    async def receive_write(
        self, group_address: str, payload: int | tuple[int, ...]
    ) -> None:
        """Inject incoming GroupValueWrite telegram."""
        payload_value = self._payload_value(payload)
        await self._receive_telegram(group_address, GroupValueWrite(payload_value))


@pytest.fixture
async def knx(request, hass):
    """Create a KNX TestKit instance."""
    knx_test_kit = KNXTestKit(hass)
    yield knx_test_kit
    await knx_test_kit.assert_no_telegram()
