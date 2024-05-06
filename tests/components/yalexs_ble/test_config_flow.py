"""Test the Yale Access Bluetooth config flow."""
import asyncio
from unittest.mock import AsyncMock, MagicMock, Mock, patch

from bleak import BleakError
import pytest
from yalexs_ble import AuthError, DoorStatus, LockInfo, LockState, LockStatus

from homeassistant import config_entries
from homeassistant.components.yalexs_ble.const import (
    CONF_ALWAYS_CONNECTED,
    CONF_KEY,
    CONF_LOCAL_NAME,
    CONF_SLOT,
    DOMAIN,
)
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import (
    LOCK_DISCOVERY_INFO_UUID_ADDRESS,
    NOT_YALE_DISCOVERY_INFO,
    OLD_FIRMWARE_LOCK_DISCOVERY_INFO,
    YALE_ACCESS_LOCK_DISCOVERY_INFO,
)

from tests.common import MockConfigEntry


def _get_mock_push_lock():
    """Return a mock PushLock."""
    mock_push_lock = Mock()
    mock_push_lock.start = AsyncMock()
    mock_push_lock.start.return_value = MagicMock()
    mock_push_lock.wait_for_first_update = AsyncMock()
    mock_push_lock.stop = AsyncMock()
    mock_push_lock.lock_state = LockState(
        LockStatus.UNLOCKED, DoorStatus.CLOSED, None, None
    )
    mock_push_lock.lock_status = LockStatus.UNLOCKED
    mock_push_lock.door_status = DoorStatus.CLOSED
    mock_push_lock.lock_info = LockInfo("Front Door", "M1XXX012LU", "1.0.0", "1.0.0")
    mock_push_lock.device_info = None
    mock_push_lock.address = YALE_ACCESS_LOCK_DISCOVERY_INFO.address
    return mock_push_lock


@pytest.mark.parametrize("slot", [0, 1, 66])
async def test_user_step_success(hass: HomeAssistant, slot: int) -> None:
    """Test user step success path."""
    with patch(
        "homeassistant.components.yalexs_ble.config_flow.async_discovered_service_info",
        return_value=[NOT_YALE_DISCOVERY_INFO, YALE_ACCESS_LOCK_DISCOVERY_INFO],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.yalexs_ble.config_flow.PushLock.validate",
    ), patch(
        "homeassistant.components.yalexs_ble.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_ADDRESS: YALE_ACCESS_LOCK_DISCOVERY_INFO.address,
                CONF_KEY: "2fd51b8621c6a139eaffbedcb846b60f",
                CONF_SLOT: slot,
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["title"] == YALE_ACCESS_LOCK_DISCOVERY_INFO.name
    assert result2["data"] == {
        CONF_LOCAL_NAME: YALE_ACCESS_LOCK_DISCOVERY_INFO.name,
        CONF_ADDRESS: YALE_ACCESS_LOCK_DISCOVERY_INFO.address,
        CONF_KEY: "2fd51b8621c6a139eaffbedcb846b60f",
        CONF_SLOT: slot,
    }
    assert result2["result"].unique_id == YALE_ACCESS_LOCK_DISCOVERY_INFO.address
    assert len(mock_setup_entry.mock_calls) == 1


async def test_user_step_no_devices_found(hass: HomeAssistant) -> None:
    """Test user step with no devices found."""
    with patch(
        "homeassistant.components.yalexs_ble.config_flow.async_discovered_service_info",
        return_value=[NOT_YALE_DISCOVERY_INFO],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "no_devices_found"


async def test_user_step_no_new_devices_found(hass: HomeAssistant) -> None:
    """Test user step with only existing devices found."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_LOCAL_NAME: YALE_ACCESS_LOCK_DISCOVERY_INFO.name,
            CONF_ADDRESS: YALE_ACCESS_LOCK_DISCOVERY_INFO.address,
            CONF_KEY: "2fd51b8621c6a139eaffbedcb846b60f",
            CONF_SLOT: 66,
        },
        unique_id=YALE_ACCESS_LOCK_DISCOVERY_INFO.address,
    )
    entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.yalexs_ble.config_flow.async_discovered_service_info",
        return_value=[YALE_ACCESS_LOCK_DISCOVERY_INFO],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "no_devices_found"


async def test_user_step_invalid_keys(hass: HomeAssistant) -> None:
    """Test user step with invalid keys tried first."""
    with patch(
        "homeassistant.components.yalexs_ble.config_flow.async_discovered_service_info",
        return_value=[YALE_ACCESS_LOCK_DISCOVERY_INFO],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_ADDRESS: YALE_ACCESS_LOCK_DISCOVERY_INFO.address,
            CONF_KEY: "dog",
            CONF_SLOT: 66,
        },
    )
    assert result2["type"] == FlowResultType.FORM
    assert result2["step_id"] == "user"
    assert result2["errors"] == {CONF_KEY: "invalid_key_format"}

    result3 = await hass.config_entries.flow.async_configure(
        result2["flow_id"],
        {
            CONF_ADDRESS: YALE_ACCESS_LOCK_DISCOVERY_INFO.address,
            CONF_KEY: "qfd51b8621c6a139eaffbedcb846b60f",
            CONF_SLOT: 66,
        },
    )
    assert result3["type"] == FlowResultType.FORM
    assert result3["step_id"] == "user"
    assert result3["errors"] == {CONF_KEY: "invalid_key_format"}

    result4 = await hass.config_entries.flow.async_configure(
        result3["flow_id"],
        {
            CONF_ADDRESS: YALE_ACCESS_LOCK_DISCOVERY_INFO.address,
            CONF_KEY: "2fd51b8621c6a139eaffbedcb846b60f",
            CONF_SLOT: 999,
        },
    )
    assert result4["type"] == FlowResultType.FORM
    assert result4["step_id"] == "user"
    assert result4["errors"] == {CONF_SLOT: "invalid_key_index"}

    with patch(
        "homeassistant.components.yalexs_ble.config_flow.PushLock.validate",
    ), patch(
        "homeassistant.components.yalexs_ble.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result5 = await hass.config_entries.flow.async_configure(
            result4["flow_id"],
            {
                CONF_ADDRESS: YALE_ACCESS_LOCK_DISCOVERY_INFO.address,
                CONF_KEY: "2fd51b8621c6a139eaffbedcb846b60f",
                CONF_SLOT: 66,
            },
        )
        await hass.async_block_till_done()

    assert result5["type"] == FlowResultType.CREATE_ENTRY
    assert result5["title"] == YALE_ACCESS_LOCK_DISCOVERY_INFO.name
    assert result5["data"] == {
        CONF_LOCAL_NAME: YALE_ACCESS_LOCK_DISCOVERY_INFO.name,
        CONF_ADDRESS: YALE_ACCESS_LOCK_DISCOVERY_INFO.address,
        CONF_KEY: "2fd51b8621c6a139eaffbedcb846b60f",
        CONF_SLOT: 66,
    }
    assert result5["result"].unique_id == YALE_ACCESS_LOCK_DISCOVERY_INFO.address
    assert len(mock_setup_entry.mock_calls) == 1


async def test_user_step_cannot_connect(hass: HomeAssistant) -> None:
    """Test user step and we cannot connect."""
    with patch(
        "homeassistant.components.yalexs_ble.config_flow.async_discovered_service_info",
        return_value=[YALE_ACCESS_LOCK_DISCOVERY_INFO],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.yalexs_ble.config_flow.PushLock.validate",
        side_effect=BleakError,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_ADDRESS: YALE_ACCESS_LOCK_DISCOVERY_INFO.address,
                CONF_KEY: "2fd51b8621c6a139eaffbedcb846b60f",
                CONF_SLOT: 66,
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.FORM
    assert result2["step_id"] == "user"
    assert result2["errors"] == {"base": "cannot_connect"}

    with patch(
        "homeassistant.components.yalexs_ble.config_flow.PushLock.validate",
    ), patch(
        "homeassistant.components.yalexs_ble.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {
                CONF_ADDRESS: YALE_ACCESS_LOCK_DISCOVERY_INFO.address,
                CONF_KEY: "2fd51b8621c6a139eaffbedcb846b60f",
                CONF_SLOT: 66,
            },
        )
        await hass.async_block_till_done()

    assert result3["type"] == FlowResultType.CREATE_ENTRY
    assert result3["title"] == YALE_ACCESS_LOCK_DISCOVERY_INFO.name
    assert result3["data"] == {
        CONF_LOCAL_NAME: YALE_ACCESS_LOCK_DISCOVERY_INFO.name,
        CONF_ADDRESS: YALE_ACCESS_LOCK_DISCOVERY_INFO.address,
        CONF_KEY: "2fd51b8621c6a139eaffbedcb846b60f",
        CONF_SLOT: 66,
    }
    assert result3["result"].unique_id == YALE_ACCESS_LOCK_DISCOVERY_INFO.address
    assert len(mock_setup_entry.mock_calls) == 1


async def test_user_step_auth_exception(hass: HomeAssistant) -> None:
    """Test user step with an authentication exception."""
    with patch(
        "homeassistant.components.yalexs_ble.config_flow.async_discovered_service_info",
        return_value=[YALE_ACCESS_LOCK_DISCOVERY_INFO, NOT_YALE_DISCOVERY_INFO],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.yalexs_ble.config_flow.PushLock.validate",
        side_effect=AuthError,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_ADDRESS: YALE_ACCESS_LOCK_DISCOVERY_INFO.address,
                CONF_KEY: "2fd51b8621c6a139eaffbedcb846b60f",
                CONF_SLOT: 66,
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.FORM
    assert result2["step_id"] == "user"
    assert result2["errors"] == {CONF_KEY: "invalid_auth"}

    with patch(
        "homeassistant.components.yalexs_ble.config_flow.PushLock.validate",
    ), patch(
        "homeassistant.components.yalexs_ble.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {
                CONF_ADDRESS: YALE_ACCESS_LOCK_DISCOVERY_INFO.address,
                CONF_KEY: "2fd51b8621c6a139eaffbedcb846b60f",
                CONF_SLOT: 66,
            },
        )
        await hass.async_block_till_done()

    assert result3["type"] == FlowResultType.CREATE_ENTRY
    assert result3["title"] == YALE_ACCESS_LOCK_DISCOVERY_INFO.name
    assert result3["data"] == {
        CONF_LOCAL_NAME: YALE_ACCESS_LOCK_DISCOVERY_INFO.name,
        CONF_ADDRESS: YALE_ACCESS_LOCK_DISCOVERY_INFO.address,
        CONF_KEY: "2fd51b8621c6a139eaffbedcb846b60f",
        CONF_SLOT: 66,
    }
    assert result3["result"].unique_id == YALE_ACCESS_LOCK_DISCOVERY_INFO.address
    assert len(mock_setup_entry.mock_calls) == 1


async def test_user_step_unknown_exception(hass: HomeAssistant) -> None:
    """Test user step with an unknown exception."""
    with patch(
        "homeassistant.components.yalexs_ble.config_flow.async_discovered_service_info",
        return_value=[NOT_YALE_DISCOVERY_INFO, YALE_ACCESS_LOCK_DISCOVERY_INFO],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.yalexs_ble.config_flow.PushLock.validate",
        side_effect=RuntimeError,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_ADDRESS: YALE_ACCESS_LOCK_DISCOVERY_INFO.address,
                CONF_KEY: "2fd51b8621c6a139eaffbedcb846b60f",
                CONF_SLOT: 66,
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.FORM
    assert result2["step_id"] == "user"
    assert result2["errors"] == {"base": "unknown"}

    with patch(
        "homeassistant.components.yalexs_ble.config_flow.PushLock.validate",
    ), patch(
        "homeassistant.components.yalexs_ble.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {
                CONF_ADDRESS: YALE_ACCESS_LOCK_DISCOVERY_INFO.address,
                CONF_KEY: "2fd51b8621c6a139eaffbedcb846b60f",
                CONF_SLOT: 66,
            },
        )
        await hass.async_block_till_done()

    assert result3["type"] == FlowResultType.CREATE_ENTRY
    assert result3["title"] == YALE_ACCESS_LOCK_DISCOVERY_INFO.name
    assert result3["data"] == {
        CONF_LOCAL_NAME: YALE_ACCESS_LOCK_DISCOVERY_INFO.name,
        CONF_ADDRESS: YALE_ACCESS_LOCK_DISCOVERY_INFO.address,
        CONF_KEY: "2fd51b8621c6a139eaffbedcb846b60f",
        CONF_SLOT: 66,
    }
    assert result3["result"].unique_id == YALE_ACCESS_LOCK_DISCOVERY_INFO.address
    assert len(mock_setup_entry.mock_calls) == 1


async def test_bluetooth_step_success(hass: HomeAssistant) -> None:
    """Test bluetooth step success path."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=YALE_ACCESS_LOCK_DISCOVERY_INFO,
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.yalexs_ble.config_flow.PushLock.validate",
    ), patch(
        "homeassistant.components.yalexs_ble.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_ADDRESS: YALE_ACCESS_LOCK_DISCOVERY_INFO.address,
                CONF_KEY: "2fd51b8621c6a139eaffbedcb846b60f",
                CONF_SLOT: 66,
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["title"] == YALE_ACCESS_LOCK_DISCOVERY_INFO.name
    assert result2["data"] == {
        CONF_LOCAL_NAME: YALE_ACCESS_LOCK_DISCOVERY_INFO.name,
        CONF_ADDRESS: YALE_ACCESS_LOCK_DISCOVERY_INFO.address,
        CONF_KEY: "2fd51b8621c6a139eaffbedcb846b60f",
        CONF_SLOT: 66,
    }
    assert result2["result"].unique_id == YALE_ACCESS_LOCK_DISCOVERY_INFO.address
    assert len(mock_setup_entry.mock_calls) == 1


async def test_integration_discovery_success(hass: HomeAssistant) -> None:
    """Test integration discovery step success path."""
    with patch(
        "homeassistant.components.yalexs_ble.util.async_discovered_service_info",
        return_value=[YALE_ACCESS_LOCK_DISCOVERY_INFO],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_INTEGRATION_DISCOVERY},
            data={
                "name": "Front Door",
                "address": YALE_ACCESS_LOCK_DISCOVERY_INFO.address,
                "key": "2fd51b8621c6a139eaffbedcb846b60f",
                "slot": 66,
                "serial": "M1XXX012LU",
            },
        )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "integration_discovery_confirm"
    assert result["errors"] is None

    with patch(
        "homeassistant.components.yalexs_ble.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {},
        )
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Front Door"
    assert result2["data"] == {
        CONF_LOCAL_NAME: YALE_ACCESS_LOCK_DISCOVERY_INFO.name,
        CONF_ADDRESS: YALE_ACCESS_LOCK_DISCOVERY_INFO.address,
        CONF_KEY: "2fd51b8621c6a139eaffbedcb846b60f",
        CONF_SLOT: 66,
    }
    assert result2["result"].unique_id == YALE_ACCESS_LOCK_DISCOVERY_INFO.address
    assert len(mock_setup_entry.mock_calls) == 1


async def test_integration_discovery_device_not_found(hass: HomeAssistant) -> None:
    """Test integration discovery when the device is not found."""
    with patch(
        "homeassistant.components.yalexs_ble.util.async_discovered_service_info",
        return_value=[],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_INTEGRATION_DISCOVERY},
            data={
                "name": "Front Door",
                "address": YALE_ACCESS_LOCK_DISCOVERY_INFO.address,
                "key": "2fd51b8621c6a139eaffbedcb846b60f",
                "slot": 66,
                "serial": "M1XXX012LU",
            },
        )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "no_devices_found"


async def test_integration_discovery_takes_precedence_over_bluetooth(
    hass: HomeAssistant,
) -> None:
    """Test integration discovery dismisses bluetooth discovery."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=YALE_ACCESS_LOCK_DISCOVERY_INFO,
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}
    flows = [
        flow
        for flow in hass.config_entries.flow.async_progress()
        if flow["handler"] == DOMAIN
    ]
    assert len(flows) == 1
    assert flows[0]["context"]["unique_id"] == YALE_ACCESS_LOCK_DISCOVERY_INFO.address
    assert flows[0]["context"]["local_name"] == YALE_ACCESS_LOCK_DISCOVERY_INFO.name

    with patch(
        "homeassistant.components.yalexs_ble.util.async_discovered_service_info",
        return_value=[YALE_ACCESS_LOCK_DISCOVERY_INFO],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_INTEGRATION_DISCOVERY},
            data={
                "name": "Front Door",
                "address": YALE_ACCESS_LOCK_DISCOVERY_INFO.address,
                "key": "2fd51b8621c6a139eaffbedcb846b60f",
                "slot": 66,
                "serial": "M1XXX012LU",
            },
        )
        await hass.async_block_till_done()
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "integration_discovery_confirm"
    assert result["errors"] is None

    # the bluetooth flow should get dismissed in favor
    # of the integration discovery flow since the integration
    # discovery flow will have the keys and the bluetooth
    # flow will not
    flows = [
        flow
        for flow in hass.config_entries.flow.async_progress()
        if flow["handler"] == DOMAIN
    ]
    assert len(flows) == 1

    with patch(
        "homeassistant.components.yalexs_ble.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {},
        )
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Front Door"
    assert result2["data"] == {
        CONF_LOCAL_NAME: YALE_ACCESS_LOCK_DISCOVERY_INFO.name,
        CONF_ADDRESS: YALE_ACCESS_LOCK_DISCOVERY_INFO.address,
        CONF_KEY: "2fd51b8621c6a139eaffbedcb846b60f",
        CONF_SLOT: 66,
    }
    assert result2["result"].unique_id == YALE_ACCESS_LOCK_DISCOVERY_INFO.address
    assert len(mock_setup_entry.mock_calls) == 1
    flows = [
        flow
        for flow in hass.config_entries.flow.async_progress()
        if flow["handler"] == DOMAIN
    ]
    assert len(flows) == 0


async def test_integration_discovery_updates_key_unique_local_name(
    hass: HomeAssistant,
) -> None:
    """Test integration discovery updates the key with a unique local name."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_LOCAL_NAME: LOCK_DISCOVERY_INFO_UUID_ADDRESS.name,
            CONF_ADDRESS: "61DE521B-F0BF-9F44-64D4-75BBE1738105",
            CONF_KEY: "5fd51b8621c6a139eaffbedcb846b60f",
            CONF_SLOT: 11,
        },
        unique_id="61DE521B-F0BF-9F44-64D4-75BBE1738105",
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.yalexs_ble.util.async_discovered_service_info",
        return_value=[LOCK_DISCOVERY_INFO_UUID_ADDRESS],
    ), patch(
        "homeassistant.components.yalexs_ble.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_INTEGRATION_DISCOVERY},
            data={
                "name": "Front Door",
                "address": "AA:BB:CC:DD:EE:FF",
                "key": "2fd51b8621c6a139eaffbedcb846b60f",
                "slot": 66,
                "serial": "M1XXX012LU",
            },
        )
        await hass.async_block_till_done()
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert entry.data[CONF_KEY] == "2fd51b8621c6a139eaffbedcb846b60f"
    assert entry.data[CONF_SLOT] == 66
    assert len(mock_setup_entry.mock_calls) == 1


async def test_integration_discovery_updates_key_without_unique_local_name(
    hass: HomeAssistant,
) -> None:
    """Test integration discovery updates the key without a unique local name."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_LOCAL_NAME: OLD_FIRMWARE_LOCK_DISCOVERY_INFO.name,
            CONF_ADDRESS: OLD_FIRMWARE_LOCK_DISCOVERY_INFO.address,
            CONF_KEY: "5fd51b8621c6a139eaffbedcb846b60f",
            CONF_SLOT: 11,
        },
        unique_id=OLD_FIRMWARE_LOCK_DISCOVERY_INFO.address,
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.yalexs_ble.util.async_discovered_service_info",
        return_value=[LOCK_DISCOVERY_INFO_UUID_ADDRESS],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_INTEGRATION_DISCOVERY},
            data={
                "name": "Front Door",
                "address": OLD_FIRMWARE_LOCK_DISCOVERY_INFO.address,
                "key": "2fd51b8621c6a139eaffbedcb846b60f",
                "slot": 66,
                "serial": "M1XXX012LU",
            },
        )
        await hass.async_block_till_done()
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert entry.data[CONF_KEY] == "2fd51b8621c6a139eaffbedcb846b60f"
    assert entry.data[CONF_SLOT] == 66


async def test_integration_discovery_updates_key_duplicate_local_name(
    hass: HomeAssistant,
) -> None:
    """Test integration discovery updates the key with duplicate local names."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_LOCAL_NAME: "Aug",
            CONF_ADDRESS: OLD_FIRMWARE_LOCK_DISCOVERY_INFO.address,
            CONF_KEY: "5fd51b8621c6a139eaffbedcb846b60f",
            CONF_SLOT: 11,
        },
        unique_id=OLD_FIRMWARE_LOCK_DISCOVERY_INFO.address,
    )
    entry.add_to_hass(hass)
    entry2 = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_LOCAL_NAME: "Aug",
            CONF_ADDRESS: "CC:DD:CC:DD:CC:DD",
            CONF_KEY: "5fd51b8621c6a139eaffbedcb846b60f",
            CONF_SLOT: 11,
        },
        unique_id="CC:DD:CC:DD:CC:DD",
    )
    entry2.add_to_hass(hass)

    with patch(
        "homeassistant.components.yalexs_ble.util.async_discovered_service_info",
        return_value=[LOCK_DISCOVERY_INFO_UUID_ADDRESS],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_INTEGRATION_DISCOVERY},
            data={
                "name": "Front Door",
                "address": OLD_FIRMWARE_LOCK_DISCOVERY_INFO.address,
                "key": "2fd51b8621c6a139eaffbedcb846b60f",
                "slot": 66,
                "serial": "M1XXX012LU",
            },
        )
        await hass.async_block_till_done()
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert entry.data[CONF_KEY] == "2fd51b8621c6a139eaffbedcb846b60f"
    assert entry.data[CONF_SLOT] == 66

    assert entry2.data[CONF_KEY] == "5fd51b8621c6a139eaffbedcb846b60f"
    assert entry2.data[CONF_SLOT] == 11


async def test_integration_discovery_takes_precedence_over_bluetooth_uuid_address(
    hass: HomeAssistant,
) -> None:
    """Test integration discovery dismisses bluetooth discovery with a uuid address."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=LOCK_DISCOVERY_INFO_UUID_ADDRESS,
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}
    flows = [
        flow
        for flow in hass.config_entries.flow.async_progress()
        if flow["handler"] == DOMAIN
    ]
    assert len(flows) == 1
    assert flows[0]["context"]["unique_id"] == LOCK_DISCOVERY_INFO_UUID_ADDRESS.address
    assert flows[0]["context"]["local_name"] == LOCK_DISCOVERY_INFO_UUID_ADDRESS.name

    with patch(
        "homeassistant.components.yalexs_ble.util.async_discovered_service_info",
        return_value=[LOCK_DISCOVERY_INFO_UUID_ADDRESS],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_INTEGRATION_DISCOVERY},
            data={
                "name": "Front Door",
                "address": "AA:BB:CC:DD:EE:FF",
                "key": "2fd51b8621c6a139eaffbedcb846b60f",
                "slot": 66,
                "serial": "M1XXX012LU",
            },
        )
        await hass.async_block_till_done()
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "integration_discovery_confirm"
    assert result["errors"] is None

    # the bluetooth flow should get dismissed in favor
    # of the integration discovery flow since the integration
    # discovery flow will have the keys and the bluetooth
    # flow will not
    flows = [
        flow
        for flow in hass.config_entries.flow.async_progress()
        if flow["handler"] == DOMAIN
    ]
    assert len(flows) == 1

    with patch(
        "homeassistant.components.yalexs_ble.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {},
        )
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Front Door"
    assert result2["data"] == {
        CONF_LOCAL_NAME: LOCK_DISCOVERY_INFO_UUID_ADDRESS.name,
        CONF_ADDRESS: LOCK_DISCOVERY_INFO_UUID_ADDRESS.address,
        CONF_KEY: "2fd51b8621c6a139eaffbedcb846b60f",
        CONF_SLOT: 66,
    }
    assert result2["result"].unique_id == OLD_FIRMWARE_LOCK_DISCOVERY_INFO.address
    assert len(mock_setup_entry.mock_calls) == 1
    flows = [
        flow
        for flow in hass.config_entries.flow.async_progress()
        if flow["handler"] == DOMAIN
    ]
    assert len(flows) == 0


async def test_integration_discovery_takes_precedence_over_bluetooth_non_unique_local_name(
    hass: HomeAssistant,
) -> None:
    """Test integration discovery dismisses bluetooth discovery with a non unique local name."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=OLD_FIRMWARE_LOCK_DISCOVERY_INFO,
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}
    flows = [
        flow
        for flow in hass.config_entries.flow.async_progress()
        if flow["handler"] == DOMAIN
    ]
    assert len(flows) == 1
    assert flows[0]["context"]["unique_id"] == OLD_FIRMWARE_LOCK_DISCOVERY_INFO.address
    assert flows[0]["context"]["local_name"] == OLD_FIRMWARE_LOCK_DISCOVERY_INFO.name

    with patch(
        "homeassistant.components.yalexs_ble.util.async_discovered_service_info",
        return_value=[OLD_FIRMWARE_LOCK_DISCOVERY_INFO],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_INTEGRATION_DISCOVERY},
            data={
                "name": "Front Door",
                "address": OLD_FIRMWARE_LOCK_DISCOVERY_INFO.address,
                "key": "2fd51b8621c6a139eaffbedcb846b60f",
                "slot": 66,
                "serial": "M1XXX012LU",
            },
        )
        await hass.async_block_till_done()
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "integration_discovery_confirm"
    assert result["errors"] is None

    # the bluetooth flow should get dismissed in favor
    # of the integration discovery flow since the integration
    # discovery flow will have the keys and the bluetooth
    # flow will not
    flows = [
        flow
        for flow in hass.config_entries.flow.async_progress()
        if flow["handler"] == DOMAIN
    ]
    assert len(flows) == 1


async def test_user_is_setting_up_lock_and_discovery_happens_in_the_middle(
    hass: HomeAssistant,
) -> None:
    """Test that the user is setting up the lock and waiting for validation and the keys get discovered.

    In this case the integration discovery should abort and let the user continue setting up the lock.
    """
    with patch(
        "homeassistant.components.yalexs_ble.config_flow.async_discovered_service_info",
        return_value=[NOT_YALE_DISCOVERY_INFO, YALE_ACCESS_LOCK_DISCOVERY_INFO],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    user_flow_event = asyncio.Event()
    valdidate_started = asyncio.Event()

    async def _wait_for_user_flow():
        valdidate_started.set()
        await user_flow_event.wait()

    with patch(
        "homeassistant.components.yalexs_ble.config_flow.PushLock.validate",
        side_effect=_wait_for_user_flow,
    ), patch(
        "homeassistant.components.yalexs_ble.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        user_flow_task = asyncio.create_task(
            hass.config_entries.flow.async_configure(
                result["flow_id"],
                {
                    CONF_ADDRESS: YALE_ACCESS_LOCK_DISCOVERY_INFO.address,
                    CONF_KEY: "2fd51b8621c6a139eaffbedcb846b60f",
                    CONF_SLOT: 66,
                },
            )
        )
        await valdidate_started.wait()

        with patch(
            "homeassistant.components.yalexs_ble.util.async_discovered_service_info",
            return_value=[LOCK_DISCOVERY_INFO_UUID_ADDRESS],
        ):
            discovery_result = await hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": config_entries.SOURCE_INTEGRATION_DISCOVERY},
                data={
                    "name": "Front Door",
                    "address": OLD_FIRMWARE_LOCK_DISCOVERY_INFO.address,
                    "key": "2fd51b8621c6a139eaffbedcb846b60f",
                    "slot": 66,
                    "serial": "M1XXX012LU",
                },
            )
            await hass.async_block_till_done()
        assert discovery_result["type"] == FlowResultType.ABORT
        assert discovery_result["reason"] == "already_in_progress"

        user_flow_event.set()
        user_flow_result = await user_flow_task

    assert user_flow_result["type"] == FlowResultType.CREATE_ENTRY
    assert user_flow_result["title"] == YALE_ACCESS_LOCK_DISCOVERY_INFO.name
    assert user_flow_result["data"] == {
        CONF_LOCAL_NAME: YALE_ACCESS_LOCK_DISCOVERY_INFO.name,
        CONF_ADDRESS: YALE_ACCESS_LOCK_DISCOVERY_INFO.address,
        CONF_KEY: "2fd51b8621c6a139eaffbedcb846b60f",
        CONF_SLOT: 66,
    }
    assert (
        user_flow_result["result"].unique_id == YALE_ACCESS_LOCK_DISCOVERY_INFO.address
    )
    assert len(mock_setup_entry.mock_calls) == 1


async def test_reauth(hass: HomeAssistant) -> None:
    """Test reauthentication."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_LOCAL_NAME: YALE_ACCESS_LOCK_DISCOVERY_INFO.name,
            CONF_ADDRESS: YALE_ACCESS_LOCK_DISCOVERY_INFO.address,
            CONF_KEY: "2fd51b8621c6a139eaffbedcb846b60f",
            CONF_SLOT: 66,
        },
        unique_id=YALE_ACCESS_LOCK_DISCOVERY_INFO.address,
    )
    entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_REAUTH, "entry_id": entry.entry_id},
        data=entry.data,
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "reauth_validate"

    with patch(
        "homeassistant.components.yalexs_ble.config_flow.PushLock.validate",
        side_effect=RuntimeError,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_KEY: "2fd51b8621c6a139eaffbedcb846b60f",
                CONF_SLOT: 66,
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.FORM
    assert result2["step_id"] == "reauth_validate"
    assert result2["errors"] == {"base": "no_longer_in_range"}

    with patch(
        "homeassistant.components.yalexs_ble.config_flow.async_ble_device_from_address",
        return_value=YALE_ACCESS_LOCK_DISCOVERY_INFO,
    ), patch(
        "homeassistant.components.yalexs_ble.config_flow.PushLock.validate",
    ), patch(
        "homeassistant.components.yalexs_ble.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {
                CONF_KEY: "2fd51b8621c6a139eaffbedcb846b60f",
                CONF_SLOT: 67,
            },
        )
        await hass.async_block_till_done()

    assert result3["type"] == FlowResultType.ABORT
    assert result3["reason"] == "reauth_successful"
    assert len(mock_setup_entry.mock_calls) == 1


async def test_options(hass: HomeAssistant) -> None:
    """Test options."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_LOCAL_NAME: YALE_ACCESS_LOCK_DISCOVERY_INFO.name,
            CONF_ADDRESS: YALE_ACCESS_LOCK_DISCOVERY_INFO.address,
            CONF_KEY: "2fd51b8621c6a139eaffbedcb846b60f",
            CONF_SLOT: 66,
        },
        unique_id=YALE_ACCESS_LOCK_DISCOVERY_INFO.address,
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.yalexs_ble.PushLock",
        return_value=_get_mock_push_lock(),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(
        entry.entry_id,
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "device_options"

    with patch(
        "homeassistant.components.yalexs_ble.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.options.async_configure(
            result["flow_id"],
            {
                CONF_ALWAYS_CONNECTED: True,
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert entry.options == {CONF_ALWAYS_CONNECTED: True}
    assert len(mock_setup_entry.mock_calls) == 1
