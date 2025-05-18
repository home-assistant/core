"""Conftest for the KNX integration."""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import DEFAULT, AsyncMock, Mock, patch

import pytest
from xknx import XKNX
from xknx.core import XknxConnectionState, XknxConnectionType
from xknx.dpt import DPTArray, DPTBinary
from xknx.io import DEFAULT_MCAST_GRP, DEFAULT_MCAST_PORT
from xknx.telegram import Telegram, TelegramDirection
from xknx.telegram.address import GroupAddress, IndividualAddress
from xknx.telegram.apci import APCI, GroupValueRead, GroupValueResponse, GroupValueWrite

from homeassistant.components.knx.const import (
    CONF_KNX_AUTOMATIC,
    CONF_KNX_CONNECTION_TYPE,
    CONF_KNX_DEFAULT_RATE_LIMIT,
    CONF_KNX_DEFAULT_STATE_UPDATER,
    CONF_KNX_INDIVIDUAL_ADDRESS,
    CONF_KNX_MCAST_GRP,
    CONF_KNX_MCAST_PORT,
    CONF_KNX_RATE_LIMIT,
    CONF_KNX_STATE_UPDATER,
    DEFAULT_ROUTING_IA,
    DOMAIN as KNX_DOMAIN,
)
from homeassistant.components.knx.project import STORAGE_KEY as KNX_PROJECT_STORAGE_KEY
from homeassistant.components.knx.storage.config_store import (
    STORAGE_KEY as KNX_CONFIG_STORAGE_KEY,
)
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.typing import ConfigType
from homeassistant.setup import async_setup_component

from . import KnxEntityGenerator

from tests.common import MockConfigEntry, load_json_object_fixture
from tests.typing import WebSocketGenerator

FIXTURE_PROJECT_DATA = load_json_object_fixture("project.json", KNX_DOMAIN)


class KNXTestKit:
    """Test helper for the KNX integration."""

    INDIVIDUAL_ADDRESS = "1.2.3"

    def __init__(
        self,
        hass: HomeAssistant,
        mock_config_entry: MockConfigEntry,
        hass_storage: dict[str, Any],
    ) -> None:
        """Init KNX test helper class."""
        self.hass: HomeAssistant = hass
        self.mock_config_entry: MockConfigEntry = mock_config_entry
        self.hass_storage: dict[str, Any] = hass_storage
        self.xknx: XKNX
        # outgoing telegrams will be put in the List instead of sent to the interface
        # telegrams to an InternalGroupAddress won't be queued here
        self._outgoing_telegrams: list[Telegram] = []

    def assert_state(self, entity_id: str, state: str, **attributes) -> None:
        """Assert the state of an entity."""
        test_state = self.hass.states.get(entity_id)
        assert test_state.state == state
        for attribute, value in attributes.items():
            assert test_state.attributes.get(attribute) == value

    async def setup_integration(
        self,
        yaml_config: ConfigType | None = None,
        config_store_fixture: str | None = None,
        add_entry_to_hass: bool = True,
    ) -> None:
        """Create the KNX integration."""

        async def patch_xknx_start():
            """Patch `xknx.start` for unittests."""
            self.xknx.cemi_handler.send_telegram = AsyncMock(
                side_effect=self._outgoing_telegrams.append
            )
            # after XKNX.__init__() to not overwrite it by the config entry again
            # before StateUpdater starts to avoid slow down of tests
            self.xknx.rate_limit = 0
            # set XknxConnectionState.CONNECTED to avoid `unavailable` entities at startup
            # and start StateUpdater. This would be awaited on normal startup too.
            self.xknx.connection_manager.connection_state_changed(
                state=XknxConnectionState.CONNECTED,
                connection_type=XknxConnectionType.TUNNEL_TCP,
            )

        def knx_ip_interface_mock():
            """Create a xknx knx ip interface mock."""
            mock = Mock()
            mock.start = AsyncMock(side_effect=patch_xknx_start)
            mock.stop = AsyncMock()
            mock.gateway_info = AsyncMock()
            return mock

        def fish_xknx(*args, **kwargs):
            """Get the XKNX object from the constructor call."""
            self.xknx = args[0]
            return DEFAULT

        if config_store_fixture:
            self.hass_storage[KNX_CONFIG_STORAGE_KEY] = load_json_object_fixture(
                config_store_fixture, KNX_DOMAIN
            )

        if add_entry_to_hass:
            self.mock_config_entry.add_to_hass(self.hass)

        knx_config = {KNX_DOMAIN: yaml_config or {}}
        with patch(
            "xknx.xknx.knx_interface_factory",
            return_value=knx_ip_interface_mock(),
            side_effect=fish_xknx,
        ):
            await async_setup_component(self.hass, KNX_DOMAIN, knx_config)
            await self.hass.async_block_till_done()

    ########################
    # Telegram counter tests
    ########################

    def _list_remaining_telegrams(self) -> str:
        """Return a string containing remaining outgoing telegrams in test List."""
        return "\n".join(map(str, self._outgoing_telegrams))

    async def assert_no_telegram(self) -> None:
        """Assert if every telegram in test List was checked."""
        await self.hass.async_block_till_done()
        remaining_telegram_count = len(self._outgoing_telegrams)
        assert not remaining_telegram_count, (
            f"Found remaining unasserted Telegrams: {remaining_telegram_count}\n"
            f"{self._list_remaining_telegrams()}"
        )

    async def assert_telegram_count(self, count: int) -> None:
        """Assert outgoing telegram count in test List."""
        await self.hass.async_block_till_done()
        actual_count = len(self._outgoing_telegrams)
        assert actual_count == count, (
            f"Outgoing telegrams: {actual_count} - Expected: {count}\n"
            f"{self._list_remaining_telegrams()}"
        )

    ####################
    # APCI Service tests
    ####################

    async def assert_telegram(
        self,
        group_address: str,
        payload: int | tuple[int, ...] | None,
        apci_type: type[APCI],
        ignore_order: bool = False,
    ) -> None:
        """Assert outgoing telegram. Optionally in timely order."""
        await self.xknx.telegrams.join()
        if not self._outgoing_telegrams:
            raise AssertionError(
                f"No Telegram found. Expected: {apci_type.__name__} -"
                f" {group_address} - {payload}"
            )
        _expected_ga = GroupAddress(group_address)

        if ignore_order:
            for telegram in self._outgoing_telegrams:
                if (
                    telegram.destination_address == _expected_ga
                    and isinstance(telegram.payload, apci_type)
                    and (payload is None or telegram.payload.value.value == payload)
                ):
                    self._outgoing_telegrams.remove(telegram)
                    return
            raise AssertionError(
                f"Telegram not found. Expected: {apci_type.__name__} -"
                f" {group_address} - {payload}"
                f"\nUnasserted telegrams:\n{self._list_remaining_telegrams()}"
            )

        telegram = self._outgoing_telegrams.pop(0)
        assert isinstance(telegram.payload, apci_type), (
            f"APCI type mismatch in {telegram} - Expected: {apci_type.__name__}"
        )
        assert telegram.destination_address == _expected_ga, (
            f"Group address mismatch in {telegram} - Expected: {group_address}"
        )
        if payload is not None:
            assert (
                telegram.payload.value.value == payload  # type: ignore[attr-defined]
            ), f"Payload mismatch in {telegram} - Expected: {payload}"

    async def assert_read(
        self,
        group_address: str,
        response: int | tuple[int, ...] | None = None,
        ignore_order: bool = False,
    ) -> None:
        """Assert outgoing GroupValueRead telegram. Optionally in timely order.

        Optionally inject incoming GroupValueResponse telegram after reception.
        """
        await self.assert_telegram(group_address, None, GroupValueRead, ignore_order)
        if response is not None:
            await self.receive_response(group_address, response)

    async def assert_response(
        self,
        group_address: str,
        payload: int | tuple[int, ...],
        ignore_order: bool = False,
    ) -> None:
        """Assert outgoing GroupValueResponse telegram. Optionally in timely order."""
        await self.assert_telegram(
            group_address, payload, GroupValueResponse, ignore_order
        )

    async def assert_write(
        self,
        group_address: str,
        payload: int | tuple[int, ...],
        ignore_order: bool = False,
    ) -> None:
        """Assert outgoing GroupValueWrite telegram. Optionally in timely order."""
        await self.assert_telegram(
            group_address, payload, GroupValueWrite, ignore_order
        )

    ####################
    # Incoming telegrams
    ####################

    @staticmethod
    def _payload_value(payload: int | tuple[int, ...]) -> DPTArray | DPTBinary:
        """Prepare payload value for GroupValueWrite or GroupValueResponse."""
        if isinstance(payload, int):
            return DPTBinary(payload)
        return DPTArray(payload)

    async def _receive_telegram(
        self,
        group_address: str,
        payload: APCI,
        source: str | None = None,
    ) -> None:
        """Inject incoming KNX telegram."""
        self.xknx.telegrams.put_nowait(
            Telegram(
                destination_address=GroupAddress(group_address),
                direction=TelegramDirection.INCOMING,
                payload=payload,
                source_address=IndividualAddress(source or self.INDIVIDUAL_ADDRESS),
            )
        )
        await self.xknx.telegrams.join()
        await self.hass.async_block_till_done()

    async def receive_read(self, group_address: str, source: str | None = None) -> None:
        """Inject incoming GroupValueRead telegram."""
        await self._receive_telegram(
            group_address,
            GroupValueRead(),
            source=source,
        )

    async def receive_response(
        self,
        group_address: str,
        payload: int | tuple[int, ...],
        source: str | None = None,
    ) -> None:
        """Inject incoming GroupValueResponse telegram."""
        payload_value = self._payload_value(payload)
        await self._receive_telegram(
            group_address,
            GroupValueResponse(payload_value),
            source=source,
        )
        await asyncio.sleep(0)  # advance loop to allow StateUpdater to process

    async def receive_write(
        self,
        group_address: str,
        payload: int | tuple[int, ...],
        source: str | None = None,
    ) -> None:
        """Inject incoming GroupValueWrite telegram."""
        payload_value = self._payload_value(payload)
        await self._receive_telegram(
            group_address,
            GroupValueWrite(payload_value),
            source=source,
        )


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        title="KNX",
        domain=KNX_DOMAIN,
        data={
            CONF_KNX_CONNECTION_TYPE: CONF_KNX_AUTOMATIC,
            CONF_KNX_RATE_LIMIT: CONF_KNX_DEFAULT_RATE_LIMIT,
            CONF_KNX_STATE_UPDATER: CONF_KNX_DEFAULT_STATE_UPDATER,
            CONF_KNX_MCAST_PORT: DEFAULT_MCAST_PORT,
            CONF_KNX_MCAST_GRP: DEFAULT_MCAST_GRP,
            CONF_KNX_INDIVIDUAL_ADDRESS: DEFAULT_ROUTING_IA,
        },
    )


@pytest.fixture
async def knx(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    hass_storage: dict[str, Any],
):
    """Create a KNX TestKit instance."""
    knx_test_kit = KNXTestKit(hass, mock_config_entry, hass_storage)
    yield knx_test_kit
    await knx_test_kit.assert_no_telegram()


@pytest.fixture
def load_knxproj(hass_storage: dict[str, Any]) -> None:
    """Mock KNX project data."""
    hass_storage[KNX_PROJECT_STORAGE_KEY] = {
        "version": 1,
        "data": FIXTURE_PROJECT_DATA,
    }


@pytest.fixture
async def create_ui_entity(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    hass_ws_client: WebSocketGenerator,
    hass_storage: dict[str, Any],
) -> KnxEntityGenerator:
    """Return a helper to create KNX entities via WS.

    The KNX integration must be set up before using the helper.
    """
    ws_client = await hass_ws_client(hass)

    async def _create_ui_entity(
        platform: Platform,
        knx_data: dict[str, Any],
        entity_data: dict[str, Any] | None = None,
    ) -> er.RegistryEntry:
        """Create a KNX entity from WS with given configuration."""
        if entity_data is None:
            entity_data = {"name": "Test"}

        await ws_client.send_json_auto_id(
            {
                "type": "knx/create_entity",
                "platform": platform,
                "data": {
                    "entity": entity_data,
                    "knx": knx_data,
                },
            }
        )
        res = await ws_client.receive_json()
        assert res["success"], res
        assert res["result"]["success"] is True, res["result"]
        entity_id = res["result"]["entity_id"]

        entity = entity_registry.async_get(entity_id)
        assert entity
        return entity

    return _create_ui_entity
