"""Tests for Besen config flow."""

from unittest.mock import Mock

from besen.exceptions import CannotConnect, InvalidAuth
import pytest
import voluptuous as vol

from homeassistant.components.besen.const import DOMAIN
from homeassistant.components.bluetooth import BluetoothServiceInfoBleak
from homeassistant.config_entries import SOURCE_BLUETOOTH, SOURCE_USER
from homeassistant.const import CONF_ADDRESS, CONF_NAME, CONF_PIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import (
    FIXTURE_ADDRESS,
    FIXTURE_DISCOVERY_ADDRESS,
    FIXTURE_NAME,
    FIXTURE_PIN,
)

from tests.common import MockConfigEntry
from tests.components.bluetooth import generate_advertisement_data, generate_ble_device


def _discovery(name: str | None = FIXTURE_NAME) -> BluetoothServiceInfoBleak:
    """Return Bluetooth discovery info."""

    return BluetoothServiceInfoBleak(
        name=name,
        address=FIXTURE_DISCOVERY_ADDRESS,
        rssi=-60,
        manufacturer_data={},
        service_uuids=[],
        service_data={},
        source="local",
        device=generate_ble_device(address=FIXTURE_DISCOVERY_ADDRESS, name=name),
        advertisement=generate_advertisement_data(
            local_name=name,
            manufacturer_data={},
            service_data={},
            service_uuids=[],
        ),
        time=0,
        connectable=True,
        tx_power=-127,
    )


def _assert_create_entry(result: dict) -> None:
    """Assert a successful flow result."""

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "BS20"
    assert result["data"] == {
        CONF_ADDRESS: FIXTURE_ADDRESS,
        CONF_NAME: FIXTURE_NAME,
        CONF_PIN: FIXTURE_PIN,
    }
    assert result["options"] == {}
    assert result["result"].unique_id == FIXTURE_ADDRESS


async def test_bluetooth_step_unsupported_name_aborts(
    hass: HomeAssistant,
) -> None:
    """Test unsupported Bluetooth discoveries are aborted."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_BLUETOOTH},
        data=_discovery("Other"),
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "not_supported"


@pytest.mark.usefixtures("mock_besen_client", "mock_setup_entry")
async def test_bluetooth_step_sets_discovered_context(
    hass: HomeAssistant,
) -> None:
    """Test Bluetooth discovery normalizes the address and asks for confirmation."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_BLUETOOTH},
        data=_discovery(),
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "bluetooth_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_PIN: FIXTURE_PIN},
    )

    _assert_create_entry(result)


@pytest.mark.usefixtures("mock_setup_entry")
async def test_bluetooth_confirm_success(
    hass: HomeAssistant,
    mock_besen_client: Mock,
) -> None:
    """Test Bluetooth confirmation creates an entry."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_BLUETOOTH},
        data=_discovery(),
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "bluetooth_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_PIN: FIXTURE_PIN},
    )

    _assert_create_entry(result)
    mock_besen_client.async_start.assert_awaited_once()
    mock_besen_client.async_stop.assert_awaited_once()


@pytest.mark.parametrize(
    ("exception", "error"),
    [
        pytest.param(InvalidAuth("bad pin"), "invalid_auth", id="invalid-auth"),
        pytest.param(CannotConnect("cannot connect"), "cannot_connect", id="connect"),
        pytest.param(RuntimeError("boom"), "unknown", id="unknown"),
    ],
)
@pytest.mark.usefixtures("mock_setup_entry")
async def test_bluetooth_confirm_errors_can_recover(
    hass: HomeAssistant,
    mock_besen_client: Mock,
    exception: Exception,
    error: str,
) -> None:
    """Test Bluetooth confirmation errors can recover."""

    mock_besen_client.async_start.side_effect = [exception, None]

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_BLUETOOTH},
        data=_discovery(),
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_PIN: FIXTURE_PIN},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "bluetooth_confirm"
    assert result["errors"] == {"base": error}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_PIN: FIXTURE_PIN},
    )

    _assert_create_entry(result)


@pytest.mark.usefixtures("mock_besen_client", "mock_setup_entry")
async def test_bluetooth_confirm_no_connectable_path_can_recover(
    hass: HomeAssistant,
    mock_ble_device: Mock,
) -> None:
    """Test Bluetooth confirmation recovers after a path becomes available."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_BLUETOOTH},
        data=_discovery(),
    )

    mock_ble_device.return_value = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_PIN: FIXTURE_PIN},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "bluetooth_confirm"
    assert result["errors"] == {"base": "no_connectable_path"}

    mock_ble_device.return_value = _discovery().device
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_PIN: FIXTURE_PIN},
    )

    _assert_create_entry(result)


async def test_bluetooth_flow_existing_device_aborts(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test Bluetooth discovery aborts for an already configured charger."""

    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_BLUETOOTH},
        data=_discovery(),
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.usefixtures("mock_besen_client", "mock_setup_entry")
async def test_user_step_success(
    hass: HomeAssistant,
) -> None:
    """Test manual setup creates an entry."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_ADDRESS: FIXTURE_ADDRESS,
            CONF_PIN: FIXTURE_PIN,
        },
    )

    _assert_create_entry(result)


@pytest.mark.usefixtures("mock_besen_client", "mock_setup_entry")
async def test_user_step_rejects_invalid_pin(
    hass: HomeAssistant,
) -> None:
    """Test the user step PIN schema rejects invalid values."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    with pytest.raises(vol.Invalid):
        await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_ADDRESS: FIXTURE_ADDRESS,
                CONF_PIN: "12345",
            },
        )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_ADDRESS: FIXTURE_ADDRESS,
            CONF_PIN: FIXTURE_PIN,
        },
    )

    _assert_create_entry(result)


@pytest.mark.parametrize(
    ("exception", "error"),
    [
        pytest.param(InvalidAuth("bad pin"), "invalid_auth", id="invalid-auth"),
        pytest.param(CannotConnect("cannot connect"), "cannot_connect", id="connect"),
        pytest.param(RuntimeError("boom"), "unknown", id="unknown"),
    ],
)
@pytest.mark.usefixtures("mock_setup_entry")
async def test_user_step_errors_can_recover(
    hass: HomeAssistant,
    mock_besen_client: Mock,
    exception: Exception,
    error: str,
) -> None:
    """Test manual setup errors can recover."""

    mock_besen_client.async_start.side_effect = [exception, None]

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_ADDRESS: FIXTURE_ADDRESS, CONF_PIN: FIXTURE_PIN},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": error}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_ADDRESS: FIXTURE_ADDRESS, CONF_PIN: FIXTURE_PIN},
    )

    _assert_create_entry(result)


@pytest.mark.usefixtures("mock_besen_client", "mock_setup_entry")
async def test_user_step_no_connectable_path_can_recover(
    hass: HomeAssistant,
    mock_ble_device: Mock,
) -> None:
    """Test manual setup recovers after a path becomes available."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    mock_ble_device.return_value = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_ADDRESS: FIXTURE_ADDRESS, CONF_PIN: FIXTURE_PIN},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "no_connectable_path"}

    mock_ble_device.return_value = _discovery().device
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_ADDRESS: FIXTURE_ADDRESS, CONF_PIN: FIXTURE_PIN},
    )

    _assert_create_entry(result)


async def test_user_step_existing_device_aborts(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test manual setup aborts for an already configured charger."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_ADDRESS: FIXTURE_ADDRESS, CONF_PIN: FIXTURE_PIN},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_user_step_no_devices_found_aborts(
    hass: HomeAssistant,
    mock_discovered_service_info: Mock,
) -> None:
    """Test manual setup aborts when no unconfigured chargers are discovered."""

    mock_discovered_service_info.return_value = []

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_devices_found"


@pytest.mark.usefixtures("mock_besen_client", "mock_setup_entry")
async def test_user_step_ignores_bluetooth_flow_in_progress(
    hass: HomeAssistant,
) -> None:
    """Test manual setup can finish when a Bluetooth flow is already in progress."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_BLUETOOTH},
        data=_discovery(),
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "bluetooth_confirm"

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_ADDRESS: FIXTURE_ADDRESS, CONF_PIN: FIXTURE_PIN},
    )

    _assert_create_entry(result)
