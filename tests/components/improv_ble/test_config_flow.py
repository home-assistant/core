"""Test the Improv via BLE config flow."""

from collections.abc import Callable
from unittest.mock import patch

from bleak.exc import BleakError
from improv_ble_client import Error, State, errors as improv_ble_errors
import pytest

from homeassistant import config_entries
from homeassistant.components.bluetooth import BluetoothChange
from homeassistant.components.improv_ble.const import DOMAIN
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult, FlowResultType

from . import (
    IMPROV_BLE_DISCOVERY_INFO,
    NOT_IMPROV_BLE_DISCOVERY_INFO,
    PROVISIONED_IMPROV_BLE_DISCOVERY_INFO,
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


async def _test_provision_error(hass: HomeAssistant, exc) -> None:
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
