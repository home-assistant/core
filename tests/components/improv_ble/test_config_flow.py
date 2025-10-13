"""Test the Improv via BLE config flow."""

import asyncio
from collections.abc import Callable
from unittest.mock import patch

from bleak.exc import BleakError
from improv_ble_client import Error, State, errors as improv_ble_errors
import pytest

from homeassistant import config_entries
from homeassistant.components import improv_ble
from homeassistant.components.bluetooth import (
    BluetoothChange,
    BluetoothServiceInfoBleak,
)
from homeassistant.components.improv_ble.const import DOMAIN
from homeassistant.config_entries import SOURCE_IGNORE, FlowType
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult, FlowResultType

from . import (
    BAD_IMPROV_BLE_DISCOVERY_INFO,
    IMPROV_BLE_DISCOVERY_INFO,
    NOT_IMPROV_BLE_DISCOVERY_INFO,
    PROVISIONED_IMPROV_BLE_DISCOVERY_INFO,
)

from tests.common import MockConfigEntry, async_capture_events
from tests.components.bluetooth import (
    generate_advertisement_data,
    generate_ble_device,
    inject_bluetooth_service_info_bleak,
)

IMPROV_BLE = "homeassistant.components.improv_ble"


@pytest.mark.parametrize(
    ("url", "abort_reason", "placeholders"),
    [
        ("http://bla.local", "provision_successful_url", {"url": "http://bla.local"}),
        (None, "provision_successful", None),
    ],
)
async def test_user_step_success(
    hass: HomeAssistant,
    url: str | None,
    abort_reason: str | None,
    placeholders: dict[str, str] | None,
) -> None:
    """Test user step success path."""
    with patch(
        f"{IMPROV_BLE}.config_flow.bluetooth.async_discovered_service_info",
        return_value=[NOT_IMPROV_BLE_DISCOVERY_INFO, IMPROV_BLE_DISCOVERY_INFO],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    await _test_common_success_wo_identify(
        hass, result, IMPROV_BLE_DISCOVERY_INFO.address, url, abort_reason, placeholders
    )


async def test_user_step_success_authorize(hass: HomeAssistant) -> None:
    """Test user step success path."""
    with patch(
        f"{IMPROV_BLE}.config_flow.bluetooth.async_discovered_service_info",
        return_value=[NOT_IMPROV_BLE_DISCOVERY_INFO, IMPROV_BLE_DISCOVERY_INFO],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    await _test_common_success_wo_identify_w_authorize(
        hass, result, IMPROV_BLE_DISCOVERY_INFO.address
    )


async def test_user_step_no_devices_found(hass: HomeAssistant) -> None:
    """Test user step with no devices found."""
    with patch(
        f"{IMPROV_BLE}.config_flow.bluetooth.async_discovered_service_info",
        return_value=[
            PROVISIONED_IMPROV_BLE_DISCOVERY_INFO,
            NOT_IMPROV_BLE_DISCOVERY_INFO,
        ],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_devices_found"


async def test_async_step_user_takes_precedence_over_discovery(
    hass: HomeAssistant,
) -> None:
    """Test manual setup takes precedence over discovery."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=IMPROV_BLE_DISCOVERY_INFO,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "bluetooth_confirm"

    with patch(
        f"{IMPROV_BLE}.config_flow.bluetooth.async_discovered_service_info",
        return_value=[IMPROV_BLE_DISCOVERY_INFO],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
        )
        assert result["type"] is FlowResultType.FORM

    await _test_common_success_wo_identify(
        hass, result, IMPROV_BLE_DISCOVERY_INFO.address
    )

    # Verify the discovery flow was aborted
    assert not hass.config_entries.flow.async_progress(DOMAIN)


async def test_user_setup_removes_ignored_entry(hass: HomeAssistant) -> None:
    """Test the user initiated form can replace an ignored device."""
    ignored_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=IMPROV_BLE_DISCOVERY_INFO.address,
        source=SOURCE_IGNORE,
    )
    ignored_entry.add_to_hass(hass)
    with patch(
        f"{IMPROV_BLE}.config_flow.bluetooth.async_discovered_service_info",
        return_value=[NOT_IMPROV_BLE_DISCOVERY_INFO, IMPROV_BLE_DISCOVERY_INFO],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    await _test_common_success_wo_identify(
        hass, result, IMPROV_BLE_DISCOVERY_INFO.address
    )
    # Check the ignored entry is removed
    assert not hass.config_entries.async_entries(DOMAIN)


async def test_bluetooth_step_provisioned_device(hass: HomeAssistant) -> None:
    """Test bluetooth step when device is already provisioned."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=PROVISIONED_IMPROV_BLE_DISCOVERY_INFO,
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_provisioned"


async def test_bluetooth_step_provisioned_device_2(hass: HomeAssistant) -> None:
    """Test bluetooth step when device changes to provisioned."""
    with patch(
        f"{IMPROV_BLE}.config_flow.bluetooth.async_register_callback",
    ) as mock_async_register_callback:
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_BLUETOOTH},
            data=IMPROV_BLE_DISCOVERY_INFO,
        )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "bluetooth_confirm"

    assert len(hass.config_entries.flow.async_progress_by_handler("improv_ble")) == 1

    callback = mock_async_register_callback.call_args.args[1]
    callback(PROVISIONED_IMPROV_BLE_DISCOVERY_INFO, BluetoothChange.ADVERTISEMENT)

    assert len(hass.config_entries.flow.async_progress_by_handler("improv_ble")) == 0


async def test_bluetooth_step_provisioned_no_rediscovery(hass: HomeAssistant) -> None:
    """Test that provisioned device is not rediscovered while it stays provisioned."""
    # Step 1: Inject provisioned device advertisement (triggers discovery, aborts)
    inject_bluetooth_service_info_bleak(hass, PROVISIONED_IMPROV_BLE_DISCOVERY_INFO)
    await hass.async_block_till_done()

    # Verify flow was aborted
    flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert len(flows) == 0

    # Step 2: Inject same provisioned advertisement again
    # This should NOT trigger a new discovery because the content hasn't changed
    # even though we cleared the match history
    inject_bluetooth_service_info_bleak(hass, PROVISIONED_IMPROV_BLE_DISCOVERY_INFO)
    await hass.async_block_till_done()

    # Verify no new flow was started
    flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert len(flows) == 0


async def test_bluetooth_step_factory_reset_rediscovery(hass: HomeAssistant) -> None:
    """Test that factory reset device can be rediscovered."""
    # Start a flow manually with provisioned device to ensure improv_ble is loaded
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=PROVISIONED_IMPROV_BLE_DISCOVERY_INFO,
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_provisioned"

    # Now the match history has been cleared by the config flow
    # Inject authorized device advertisement - should trigger new discovery
    inject_bluetooth_service_info_bleak(hass, IMPROV_BLE_DISCOVERY_INFO)
    await hass.async_block_till_done()

    # Verify discovery proceeds (new flow started)
    flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert len(flows) == 1
    assert flows[0]["step_id"] == "bluetooth_confirm"


async def test_bluetooth_rediscovery_after_successful_provision(
    hass: HomeAssistant,
) -> None:
    """Test that device can be rediscovered after successful provisioning."""
    # Start provisioning flow
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=IMPROV_BLE_DISCOVERY_INFO,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "bluetooth_confirm"

    # Confirm bluetooth setup
    result = await hass.config_entries.flow.async_configure(result["flow_id"])
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "bluetooth_confirm"

    # Start provisioning
    with patch(
        f"{IMPROV_BLE}.config_flow.ImprovBLEClient.can_identify", return_value=False
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_ADDRESS: IMPROV_BLE_DISCOVERY_INFO.address},
        )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "provision"

    # Complete provisioning successfully
    with (
        patch(
            f"{IMPROV_BLE}.config_flow.ImprovBLEClient.need_authorization",
            return_value=False,
        ),
        patch(
            f"{IMPROV_BLE}.config_flow.ImprovBLEClient.provision",
            return_value=None,
        ),
        patch(f"{IMPROV_BLE}.config_flow.PROVISIONING_TIMEOUT", 0.0000001),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"ssid": "TestNetwork", "password": "secret"}
        )
        assert result["type"] is FlowResultType.SHOW_PROGRESS
        assert result["progress_action"] == "provisioning"
        assert result["step_id"] == "do_provision"
        await hass.async_block_till_done()

    result = await hass.config_entries.flow.async_configure(result["flow_id"])
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "provision_successful"

    # Now inject the same device again (simulating factory reset)
    # The match history was cleared after successful provision, so it should be rediscovered
    inject_bluetooth_service_info_bleak(hass, IMPROV_BLE_DISCOVERY_INFO)
    await hass.async_block_till_done()

    # Verify new discovery flow was created
    flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert len(flows) == 1
    assert flows[0]["step_id"] == "bluetooth_confirm"


async def test_bluetooth_step_success(hass: HomeAssistant) -> None:
    """Test bluetooth step success path."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=IMPROV_BLE_DISCOVERY_INFO,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "bluetooth_confirm"
    assert result["errors"] is None

    await _test_common_success_wo_identify(
        hass, result, IMPROV_BLE_DISCOVERY_INFO.address
    )


async def test_bluetooth_step_success_identify(hass: HomeAssistant) -> None:
    """Test bluetooth step success path."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=IMPROV_BLE_DISCOVERY_INFO,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "bluetooth_confirm"
    assert result["errors"] is None

    await _test_common_success_with_identify(
        hass, result, IMPROV_BLE_DISCOVERY_INFO.address
    )


async def _test_common_success_with_identify(
    hass: HomeAssistant, result: FlowResult, address: str
) -> None:
    """Test bluetooth and user flow success paths."""
    with patch(
        f"{IMPROV_BLE}.config_flow.ImprovBLEClient.can_identify", return_value=True
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_ADDRESS: address},
        )
    assert result["type"] is FlowResultType.MENU
    assert result["menu_options"] == ["identify", "provision"]
    assert result["step_id"] == "main_menu"

    with patch(f"{IMPROV_BLE}.config_flow.ImprovBLEClient.identify"):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"next_step_id": "identify"},
        )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "identify"
    assert result["errors"] is None

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.MENU
    assert result["menu_options"] == ["identify", "provision"]
    assert result["step_id"] == "main_menu"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"next_step_id": "provision"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "provision"
    assert result["errors"] is None

    await _test_common_success(hass, result)


async def _test_common_success_wo_identify(
    hass: HomeAssistant,
    result: FlowResult,
    address: str,
    url: str | None = None,
    abort_reason: str = "provision_successful",
    placeholders: dict[str, str] | None = None,
) -> None:
    """Test bluetooth and user flow success paths."""
    with patch(
        f"{IMPROV_BLE}.config_flow.ImprovBLEClient.can_identify", return_value=False
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_ADDRESS: address},
        )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "provision"
    assert result["errors"] is None

    await _test_common_success(hass, result)


async def _test_common_success(
    hass: HomeAssistant,
    result: FlowResult,
    url: str | None = None,
    abort_reason: str = "provision_successful",
    placeholders: dict[str, str] | None = None,
    patch_timeout_for_tests=None,
) -> None:
    """Test bluetooth and user flow success paths."""

    with (
        patch(
            f"{IMPROV_BLE}.config_flow.ImprovBLEClient.need_authorization",
            return_value=False,
        ),
        patch(
            f"{IMPROV_BLE}.config_flow.ImprovBLEClient.provision",
            return_value=url,
        ) as mock_provision,
        patch(f"{IMPROV_BLE}.config_flow.PROVISIONING_TIMEOUT", 0.0000001),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"ssid": "MyWIFI", "password": "secret"}
        )
        assert result["type"] is FlowResultType.SHOW_PROGRESS
        assert result["progress_action"] == "provisioning"
        assert result["step_id"] == "do_provision"
        await hass.async_block_till_done()

    result = await hass.config_entries.flow.async_configure(result["flow_id"])
    assert result.get("description_placeholders") == placeholders
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == abort_reason

    mock_provision.assert_awaited_once_with("MyWIFI", "secret", None)


async def _test_common_success_wo_identify_w_authorize(
    hass: HomeAssistant, result: FlowResult, address: str
) -> None:
    """Test bluetooth and user flow success paths."""
    with patch(
        f"{IMPROV_BLE}.config_flow.ImprovBLEClient.can_identify", return_value=False
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_ADDRESS: address},
        )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "provision"
    assert result["errors"] is None

    await _test_common_success_w_authorize(hass, result)


async def _test_common_success_w_authorize(
    hass: HomeAssistant, result: FlowResult
) -> None:
    """Test bluetooth and user flow success paths."""

    async def subscribe_state_updates(
        state_callback: Callable[[State], None],
    ) -> Callable[[], None]:
        state_callback(State.AUTHORIZED)
        return lambda: None

    with (
        patch(
            f"{IMPROV_BLE}.config_flow.ImprovBLEClient.need_authorization",
            return_value=True,
        ),
        patch(
            f"{IMPROV_BLE}.config_flow.ImprovBLEClient.subscribe_state_updates",
            side_effect=subscribe_state_updates,
        ) as mock_subscribe_state_updates,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"ssid": "MyWIFI", "password": "secret"}
        )
        assert result["type"] is FlowResultType.SHOW_PROGRESS
        assert result["progress_action"] == "authorize"
        assert result["step_id"] == "authorize"
        mock_subscribe_state_updates.assert_awaited_once()
        await hass.async_block_till_done()

    with (
        patch(
            f"{IMPROV_BLE}.config_flow.ImprovBLEClient.need_authorization",
            return_value=False,
        ),
        patch(
            f"{IMPROV_BLE}.config_flow.ImprovBLEClient.provision",
            return_value="http://blabla.local",
        ) as mock_provision,
        patch(f"{IMPROV_BLE}.config_flow.PROVISIONING_TIMEOUT", 0.0000001),
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"])
        assert result["type"] is FlowResultType.SHOW_PROGRESS
        assert result["progress_action"] == "provisioning"
        assert result["step_id"] == "do_provision"
        await hass.async_block_till_done()

    result = await hass.config_entries.flow.async_configure(result["flow_id"])
    assert result["description_placeholders"] == {"url": "http://blabla.local"}
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "provision_successful_url"

    mock_provision.assert_awaited_once_with("MyWIFI", "secret", None)


async def test_bluetooth_step_already_in_progress(hass: HomeAssistant) -> None:
    """Test we can't start a flow for the same device twice."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=IMPROV_BLE_DISCOVERY_INFO,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "bluetooth_confirm"

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=IMPROV_BLE_DISCOVERY_INFO,
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_in_progress"


@pytest.mark.parametrize(
    ("exc", "error"),
    [
        (BleakError, "cannot_connect"),
        (Exception, "unknown"),
        (improv_ble_errors.CharacteristicMissingError, "characteristic_missing"),
    ],
)
async def test_can_identify_fails(hass: HomeAssistant, exc, error) -> None:
    """Test bluetooth flow with error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=IMPROV_BLE_DISCOVERY_INFO,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "bluetooth_confirm"
    assert result["errors"] is None

    result = await hass.config_entries.flow.async_configure(result["flow_id"])
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "bluetooth_confirm"
    assert result["errors"] is None

    with patch(
        f"{IMPROV_BLE}.config_flow.ImprovBLEClient.can_identify", side_effect=exc
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_ADDRESS: IMPROV_BLE_DISCOVERY_INFO.address},
        )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == error


@pytest.mark.parametrize(
    ("exc", "error"),
    [
        (BleakError, "cannot_connect"),
        (Exception, "unknown"),
        (improv_ble_errors.CharacteristicMissingError, "characteristic_missing"),
    ],
)
async def test_identify_fails(hass: HomeAssistant, exc, error) -> None:
    """Test bluetooth flow with error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=IMPROV_BLE_DISCOVERY_INFO,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "bluetooth_confirm"
    assert result["errors"] is None

    result = await hass.config_entries.flow.async_configure(result["flow_id"])
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "bluetooth_confirm"
    assert result["errors"] is None

    with patch(
        f"{IMPROV_BLE}.config_flow.ImprovBLEClient.can_identify", return_value=True
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_ADDRESS: IMPROV_BLE_DISCOVERY_INFO.address},
        )
    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "main_menu"

    with patch(f"{IMPROV_BLE}.config_flow.ImprovBLEClient.identify", side_effect=exc):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"next_step_id": "identify"},
        )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == error


@pytest.mark.parametrize(
    ("exc", "error"),
    [
        (BleakError, "cannot_connect"),
        (Exception, "unknown"),
        (improv_ble_errors.CharacteristicMissingError, "characteristic_missing"),
    ],
)
async def test_need_authorization_fails(hass: HomeAssistant, exc, error) -> None:
    """Test bluetooth flow with error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=IMPROV_BLE_DISCOVERY_INFO,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "bluetooth_confirm"
    assert result["errors"] is None

    result = await hass.config_entries.flow.async_configure(result["flow_id"])
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "bluetooth_confirm"
    assert result["errors"] is None

    with patch(
        f"{IMPROV_BLE}.config_flow.ImprovBLEClient.can_identify", return_value=False
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_ADDRESS: IMPROV_BLE_DISCOVERY_INFO.address},
        )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "provision"

    with patch(
        f"{IMPROV_BLE}.config_flow.ImprovBLEClient.need_authorization", side_effect=exc
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"ssid": "MyWIFI", "password": "secret"}
        )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == error


@pytest.mark.parametrize(
    ("exc", "error"),
    [
        (BleakError, "cannot_connect"),
        (Exception, "unknown"),
        (improv_ble_errors.CharacteristicMissingError, "characteristic_missing"),
    ],
)
async def test_authorize_fails(hass: HomeAssistant, exc, error) -> None:
    """Test bluetooth flow with error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=IMPROV_BLE_DISCOVERY_INFO,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "bluetooth_confirm"
    assert result["errors"] is None

    result = await hass.config_entries.flow.async_configure(result["flow_id"])
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "bluetooth_confirm"
    assert result["errors"] is None

    with patch(
        f"{IMPROV_BLE}.config_flow.ImprovBLEClient.can_identify", return_value=False
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_ADDRESS: IMPROV_BLE_DISCOVERY_INFO.address},
        )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "provision"

    with (
        patch(
            f"{IMPROV_BLE}.config_flow.ImprovBLEClient.need_authorization",
            return_value=True,
        ),
        patch(
            f"{IMPROV_BLE}.config_flow.ImprovBLEClient.subscribe_state_updates",
            side_effect=exc,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"ssid": "MyWIFI", "password": "secret"}
        )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == error


async def _test_provision_error(hass: HomeAssistant, exc) -> str:
    """Test bluetooth flow with error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=IMPROV_BLE_DISCOVERY_INFO,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "bluetooth_confirm"
    assert result["errors"] is None

    result = await hass.config_entries.flow.async_configure(result["flow_id"])
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "bluetooth_confirm"
    assert result["errors"] is None

    with patch(
        f"{IMPROV_BLE}.config_flow.ImprovBLEClient.can_identify", return_value=False
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_ADDRESS: IMPROV_BLE_DISCOVERY_INFO.address},
        )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "provision"

    with (
        patch(
            f"{IMPROV_BLE}.config_flow.ImprovBLEClient.need_authorization",
            return_value=False,
        ),
        patch(
            f"{IMPROV_BLE}.config_flow.ImprovBLEClient.provision",
            side_effect=exc,
        ),
        patch(f"{IMPROV_BLE}.config_flow.PROVISIONING_TIMEOUT", 0.0000001),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"ssid": "MyWIFI", "password": "secret"}
        )
        assert result["type"] is FlowResultType.SHOW_PROGRESS
        assert result["progress_action"] == "provisioning"
        assert result["step_id"] == "do_provision"
        await hass.async_block_till_done()

    return result["flow_id"]


@pytest.mark.parametrize(
    ("exc", "error"),
    [
        (BleakError, "cannot_connect"),
        (Exception, "unknown"),
        (improv_ble_errors.CharacteristicMissingError, "characteristic_missing"),
        (improv_ble_errors.ProvisioningFailed(Error.UNKNOWN_ERROR), "unknown"),
    ],
)
async def test_provision_fails(hass: HomeAssistant, exc, error) -> None:
    """Test bluetooth flow with error."""
    flow_id = await _test_provision_error(hass, exc)

    result = await hass.config_entries.flow.async_configure(flow_id)
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == error


@pytest.mark.parametrize(
    ("exc", "error"),
    [(improv_ble_errors.ProvisioningFailed(Error.NOT_AUTHORIZED), "unknown")],
)
async def test_provision_not_authorized(hass: HomeAssistant, exc, error) -> None:
    """Test bluetooth flow with error."""

    async def subscribe_state_updates(
        state_callback: Callable[[State], None],
    ) -> Callable[[], None]:
        state_callback(State.AUTHORIZED)
        return lambda: None

    with patch(
        f"{IMPROV_BLE}.config_flow.ImprovBLEClient.subscribe_state_updates",
        side_effect=subscribe_state_updates,
    ):
        flow_id = await _test_provision_error(hass, exc)
    result = await hass.config_entries.flow.async_configure(flow_id)
    assert result["type"] is FlowResultType.SHOW_PROGRESS
    assert result["progress_action"] == "authorize"
    assert result["step_id"] == "authorize"


@pytest.mark.parametrize(
    ("exc", "error"),
    [
        (
            improv_ble_errors.ProvisioningFailed(Error.UNABLE_TO_CONNECT),
            "unable_to_connect",
        ),
    ],
)
async def test_provision_retry(hass: HomeAssistant, exc, error) -> None:
    """Test bluetooth flow with error."""
    flow_id = await _test_provision_error(hass, exc)

    result = await hass.config_entries.flow.async_configure(flow_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "provision"
    assert result["errors"] == {"base": error}


async def test_provision_fails_invalid_data(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test bluetooth flow with error due to invalid data."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=BAD_IMPROV_BLE_DISCOVERY_INFO,
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "invalid_improv_data"
    assert (
        "Received invalid improv via BLE data '000000000000' from device with bluetooth address 'AA:BB:CC:DD:EE:F0'"
        in caplog.text
    )


async def test_flow_chaining_with_next_flow(hass: HomeAssistant) -> None:
    """Test flow chaining when another integration registers a next flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=IMPROV_BLE_DISCOVERY_INFO,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "bluetooth_confirm"

    # Confirm bluetooth setup
    result = await hass.config_entries.flow.async_configure(result["flow_id"])
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "bluetooth_confirm"

    # Start provisioning
    with patch(
        f"{IMPROV_BLE}.config_flow.ImprovBLEClient.can_identify", return_value=False
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_ADDRESS: IMPROV_BLE_DISCOVERY_INFO.address},
        )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "provision"

    with (
        patch(
            f"{IMPROV_BLE}.config_flow.ImprovBLEClient.need_authorization",
            return_value=False,
        ),
        patch(
            f"{IMPROV_BLE}.config_flow.ImprovBLEClient.provision",
            return_value=None,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"ssid": "TestNetwork", "password": "secret"}
        )
        assert result["type"] is FlowResultType.SHOW_PROGRESS
        assert result["progress_action"] == "provisioning"
        assert result["step_id"] == "do_provision"

        # Yield to allow the background task to create the future
        await asyncio.sleep(0)  # task is created with eager_start=False

        # Simulate another integration discovering the device and registering a flow
        # This happens while provision is waiting on the future
        improv_ble.async_register_next_flow(
            hass, IMPROV_BLE_DISCOVERY_INFO.address, "next_config_flow_id"
        )

        await hass.async_block_till_done()

    result = await hass.config_entries.flow.async_configure(result["flow_id"])
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "provision_successful"
    assert result.get("next_flow") == (FlowType.CONFIG_FLOW, "next_config_flow_id")


async def test_flow_chaining_timeout(hass: HomeAssistant) -> None:
    """Test flow chaining timeout when no integration discovers the device."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=IMPROV_BLE_DISCOVERY_INFO,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "bluetooth_confirm"

    # Confirm bluetooth setup
    result = await hass.config_entries.flow.async_configure(result["flow_id"])
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "bluetooth_confirm"

    # Start provisioning
    with patch(
        f"{IMPROV_BLE}.config_flow.ImprovBLEClient.can_identify", return_value=False
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_ADDRESS: IMPROV_BLE_DISCOVERY_INFO.address},
        )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "provision"

    # Complete provisioning successfully but no integration discovers the device
    with (
        patch(
            f"{IMPROV_BLE}.config_flow.ImprovBLEClient.need_authorization",
            return_value=False,
        ),
        patch(
            f"{IMPROV_BLE}.config_flow.ImprovBLEClient.provision",
            return_value=None,
        ),
        patch("asyncio.wait_for", side_effect=TimeoutError),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"ssid": "TestNetwork", "password": "secret"}
        )
        assert result["type"] is FlowResultType.SHOW_PROGRESS
        assert result["progress_action"] == "provisioning"
        assert result["step_id"] == "do_provision"
        await hass.async_block_till_done()

    result = await hass.config_entries.flow.async_configure(result["flow_id"])
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "provision_successful"
    assert "next_flow" not in result


async def test_flow_chaining_with_redirect_url(hass: HomeAssistant) -> None:
    """Test flow chaining takes precedence over redirect URL."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=IMPROV_BLE_DISCOVERY_INFO,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "bluetooth_confirm"

    # Confirm bluetooth setup
    result = await hass.config_entries.flow.async_configure(result["flow_id"])
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "bluetooth_confirm"

    # Start provisioning
    with patch(
        f"{IMPROV_BLE}.config_flow.ImprovBLEClient.can_identify", return_value=False
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_ADDRESS: IMPROV_BLE_DISCOVERY_INFO.address},
        )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "provision"

    with (
        patch(
            f"{IMPROV_BLE}.config_flow.ImprovBLEClient.need_authorization",
            return_value=False,
        ),
        patch(
            f"{IMPROV_BLE}.config_flow.ImprovBLEClient.provision",
            return_value="http://blabla.local",
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"ssid": "TestNetwork", "password": "secret"}
        )
        assert result["type"] is FlowResultType.SHOW_PROGRESS
        assert result["progress_action"] == "provisioning"
        assert result["step_id"] == "do_provision"

        # Yield to allow the background task to create the future
        await asyncio.sleep(0)  # task is created with eager_start=False

        # Simulate ESPHome discovering the device and notifying Improv BLE
        # This happens while provision is still running
        improv_ble.async_register_next_flow(
            hass, IMPROV_BLE_DISCOVERY_INFO.address, "esphome_flow_id"
        )

        await hass.async_block_till_done()

    result = await hass.config_entries.flow.async_configure(result["flow_id"])
    assert result["type"] is FlowResultType.ABORT
    # Should use next_flow instead of redirect URL
    assert result["reason"] == "provision_successful"
    assert result.get("next_flow") == (FlowType.CONFIG_FLOW, "esphome_flow_id")


async def test_bluetooth_name_update(hass: HomeAssistant) -> None:
    """Test that discovery notification title updates when device name changes."""
    with patch(
        f"{IMPROV_BLE}.config_flow.bluetooth.async_register_callback",
    ) as mock_async_register_callback:
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_BLUETOOTH},
            data=IMPROV_BLE_DISCOVERY_INFO,
        )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "bluetooth_confirm"

    # Get the flow to check initial title_placeholders
    flow = hass.config_entries.flow.async_get(result["flow_id"])
    assert flow["context"]["title_placeholders"] == {"name": "00123456"}

    # Get the callback that was registered
    callback = mock_async_register_callback.call_args.args[1]

    # Create updated discovery info with a new name
    updated_discovery_info = BluetoothServiceInfoBleak(
        name="improvtest",
        address="AA:BB:CC:DD:EE:F0",
        rssi=-60,
        manufacturer_data={},
        service_uuids=[IMPROV_BLE_DISCOVERY_INFO.service_uuids[0]],
        service_data=IMPROV_BLE_DISCOVERY_INFO.service_data,
        source="local",
        device=generate_ble_device(address="AA:BB:CC:DD:EE:F0", name="improvtest"),
        advertisement=generate_advertisement_data(
            service_uuids=IMPROV_BLE_DISCOVERY_INFO.service_uuids,
            service_data=IMPROV_BLE_DISCOVERY_INFO.service_data,
        ),
        time=0,
        connectable=True,
        tx_power=-127,
    )

    # Capture events to verify frontend notification
    events = async_capture_events(hass, "data_entry_flow_progressed")

    # Simulate receiving updated advertisement with new name
    callback(updated_discovery_info, BluetoothChange.ADVERTISEMENT)
    await hass.async_block_till_done()

    # Verify title_placeholders were updated
    flow = hass.config_entries.flow.async_get(result["flow_id"])
    assert flow["context"]["title_placeholders"] == {"name": "improvtest"}

    # Verify frontend was notified
    assert len(events) == 1
    assert events[0].data == {
        "handler": DOMAIN,
        "flow_id": result["flow_id"],
        "refresh": True,
    }
