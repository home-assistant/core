"""Test the Gardena Bluetooth config flow."""

import asyncio
from collections.abc import Awaitable, Callable
from unittest.mock import Mock

from gardena_bluetooth.exceptions import CharacteristicNotFound
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant import config_entries
from homeassistant.components.gardena_bluetooth.const import DOMAIN
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import (
    MISSING_MANUFACTURER_DATA_SERVICE_INFO,
    MISSING_PRODUCT_SERVICE_INFO,
    MISSING_SERVICE_SERVICE_INFO,
    UNSUPPORTED_GROUP_SERVICE_INFO,
    WATER_TIMER_SERVICE_INFO,
    WATER_TIMER_UNNAMED_SERVICE_INFO,
)

from tests.common import MockConfigEntry
from tests.components.bluetooth import inject_bluetooth_service_info

pytestmark = pytest.mark.usefixtures("mock_setup_entry")


async def test_user_selection(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
) -> None:
    """Test we can select a device."""

    inject_bluetooth_service_info(hass, WATER_TIMER_SERVICE_INFO)
    inject_bluetooth_service_info(hass, WATER_TIMER_UNNAMED_SERVICE_INFO)
    await hass.async_block_till_done(wait_background_tasks=True)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result == snapshot

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={"address": "00000000-0000-0000-0000-000000000001"},
    )
    assert result == snapshot

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={},
    )
    assert result == snapshot


async def test_user_selection_replaces_ignored(hass: HomeAssistant) -> None:
    """Test setup from service info cache replaces an ignored entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=WATER_TIMER_SERVICE_INFO.address,
    )
    entry.source = config_entries.SOURCE_IGNORE
    entry.add_to_hass(hass)

    inject_bluetooth_service_info(hass, WATER_TIMER_SERVICE_INFO)
    await hass.async_block_till_done(wait_background_tasks=True)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_ADDRESS: WATER_TIMER_SERVICE_INFO.address},
    )

    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_failed_connect(
    hass: HomeAssistant,
    mock_client: Mock,
    snapshot: SnapshotAssertion,
) -> None:
    """Test we can select a device."""

    inject_bluetooth_service_info(hass, WATER_TIMER_SERVICE_INFO)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result == snapshot

    mock_client.read_char.side_effect = CharacteristicNotFound("something went wrong")

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={"address": "00000000-0000-0000-0000-000000000001"},
    )
    assert result == snapshot

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={},
    )
    assert result == snapshot


async def test_no_valid_devices(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
) -> None:
    """Test no valid candidates."""

    inject_bluetooth_service_info(hass, MISSING_MANUFACTURER_DATA_SERVICE_INFO)
    inject_bluetooth_service_info(hass, MISSING_SERVICE_SERVICE_INFO)
    inject_bluetooth_service_info(hass, UNSUPPORTED_GROUP_SERVICE_INFO)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result.get("type") == "abort"
    assert result.get("reason") == "no_devices_found"


async def test_timeout_manufacturer_data(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    scan_step: Callable[[], Awaitable[None]],
    manufacturer_request_event: asyncio.Event,
) -> None:
    """Test the flow aborts with no_devices_found when manufacturer data times out and only partial info is available."""

    inject_bluetooth_service_info(hass, MISSING_PRODUCT_SERVICE_INFO)

    # The injected advertisement starts a bluetooth discovery flow which also
    # calls async_get_manufacturer_data. Drain it first so it doesn't race
    # with the user flow's own request.
    await manufacturer_request_event.wait()
    await scan_step()
    await hass.async_block_till_done(wait_background_tasks=True)
    manufacturer_request_event.clear()

    async with asyncio.TaskGroup() as tg:
        task = tg.create_task(
            hass.config_entries.flow.async_init(
                DOMAIN, context={"source": config_entries.SOURCE_USER}
            )
        )
        await manufacturer_request_event.wait()
        await scan_step()
        result = await task

    assert result.get("type") == "abort"
    assert result.get("reason") == "no_devices_found"


async def test_no_devices_at_all(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
) -> None:
    """Test missing device."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result.get("type") == "abort"
    assert result.get("reason") == "no_devices_found"


async def test_bluetooth(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
) -> None:
    """Test bluetooth device discovery."""

    # Inject the service info will trigger the flow to start
    inject_bluetooth_service_info(hass, WATER_TIMER_SERVICE_INFO)
    await hass.async_block_till_done(wait_background_tasks=True)

    result = next(iter(hass.config_entries.flow.async_progress_by_handler(DOMAIN)))

    assert result == snapshot

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={},
    )
    assert result == snapshot


async def test_bluetooth_invalid(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
) -> None:
    """Test bluetooth device discovery with invalid data."""

    inject_bluetooth_service_info(hass, UNSUPPORTED_GROUP_SERVICE_INFO)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=UNSUPPORTED_GROUP_SERVICE_INFO,
    )
    assert result == snapshot
