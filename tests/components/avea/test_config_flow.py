"""Test the Avea config flow."""

from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components.avea.const import AVEA_SERVICE_UUID, DOMAIN
from homeassistant.config_entries import SOURCE_BLUETOOTH, SOURCE_IMPORT, SOURCE_USER
from homeassistant.const import CONF_ADDRESS, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import AVEA_DISCOVERY_INFO, NOT_AVEA_DISCOVERY_INFO

from tests.components.bluetooth import (
    generate_advertisement_data,
    generate_ble_device,
    inject_bluetooth_service_info,
)

pytestmark = pytest.mark.usefixtures("enable_bluetooth")


def _mock_bulb(name: str | Exception | None, brightness: int | None) -> MagicMock:
    """Create a mocked Avea bulb for validation."""
    bulb = MagicMock()
    bulb.connect.return_value = True
    if isinstance(name, Exception):
        bulb.get_name.side_effect = name
    else:
        bulb.get_name.return_value = name
    bulb.get_brightness.return_value = brightness
    return bulb


async def test_user_step_success(hass: HomeAssistant) -> None:
    """Test the user step success path."""
    inject_bluetooth_service_info(hass, NOT_AVEA_DISCOVERY_INFO)
    inject_bluetooth_service_info(hass, AVEA_DISCOVERY_INFO)
    await hass.async_block_till_done(wait_background_tasks=True)

    with patch(
        "homeassistant.components.avea.config_flow.bluetooth.async_request_active_scan"
    ) as mock_request_active_scan:
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}
    assert result["data_schema"].schema[CONF_ADDRESS].container == {
        AVEA_DISCOVERY_INFO.address: (
            f"{AVEA_DISCOVERY_INFO.name} ({AVEA_DISCOVERY_INFO.address})"
        )
    }
    mock_request_active_scan.assert_awaited_once_with(hass)

    with (
        patch(
            "homeassistant.components.avea.config_flow.avea.Bulb",
            return_value=_mock_bulb("Living Room", 0),
        ),
        patch("homeassistant.components.avea.async_setup_entry", return_value=True),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_ADDRESS: AVEA_DISCOVERY_INFO.address},
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Living Room"
    assert result["data"] == {CONF_ADDRESS: AVEA_DISCOVERY_INFO.address}
    assert result["result"].unique_id == AVEA_DISCOVERY_INFO.address


async def test_user_step_no_devices_found(hass: HomeAssistant) -> None:
    """Test the user step when no devices are found."""
    inject_bluetooth_service_info(hass, NOT_AVEA_DISCOVERY_INFO)
    await hass.async_block_till_done(wait_background_tasks=True)

    with patch(
        "homeassistant.components.avea.config_flow.bluetooth.async_request_active_scan"
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_devices_found"


async def test_user_step_unnamed_device_label(hass: HomeAssistant) -> None:
    """Test unnamed discovered devices are shown without duplicating the address."""
    discovery_info = type(AVEA_DISCOVERY_INFO)(
        name=AVEA_DISCOVERY_INFO.address,
        address=AVEA_DISCOVERY_INFO.address,
        rssi=-60,
        manufacturer_data={},
        service_uuids=[AVEA_SERVICE_UUID],
        service_data={},
        source="local",
        device=generate_ble_device(
            address=AVEA_DISCOVERY_INFO.address, name=AVEA_DISCOVERY_INFO.address
        ),
        advertisement=generate_advertisement_data(
            local_name=AVEA_DISCOVERY_INFO.address,
            manufacturer_data={},
            service_data={},
            service_uuids=[AVEA_SERVICE_UUID],
        ),
        time=0,
        connectable=True,
        tx_power=-127,
    )

    with (
        patch(
            "homeassistant.components.avea.config_flow.async_discovered_service_info",
            return_value=[discovery_info],
        ),
        patch(
            "homeassistant.components.avea.config_flow.bluetooth.async_request_active_scan"
        ) as mock_request_active_scan,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["data_schema"].schema[CONF_ADDRESS].container == {
        AVEA_DISCOVERY_INFO.address: AVEA_DISCOVERY_INFO.address
    }
    mock_request_active_scan.assert_awaited_once_with(hass)


async def test_user_step_cannot_connect_recovers(hass: HomeAssistant) -> None:
    """Test the user step recovers after a cannot connect error."""
    inject_bluetooth_service_info(hass, AVEA_DISCOVERY_INFO)
    await hass.async_block_till_done(wait_background_tasks=True)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM

    failing_bulb = _mock_bulb("Bedroom", 0)
    failing_bulb.get_brightness.side_effect = RuntimeError

    with patch(
        "homeassistant.components.avea.config_flow.avea.Bulb",
        return_value=failing_bulb,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_ADDRESS: AVEA_DISCOVERY_INFO.address},
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "cannot_connect"}

    with (
        patch(
            "homeassistant.components.avea.config_flow.avea.Bulb",
            return_value=_mock_bulb("Bedroom", 0),
        ),
        patch("homeassistant.components.avea.async_setup_entry", return_value=True),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_ADDRESS: AVEA_DISCOVERY_INFO.address},
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Bedroom"


async def test_user_step_unknown_error_recovers(hass: HomeAssistant) -> None:
    """Test the user step recovers after an unknown error."""
    inject_bluetooth_service_info(hass, AVEA_DISCOVERY_INFO)
    await hass.async_block_till_done(wait_background_tasks=True)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM

    with patch(
        "homeassistant.components.avea.config_flow.avea.Bulb",
        return_value=_mock_bulb(ValueError("boom"), 0),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_ADDRESS: AVEA_DISCOVERY_INFO.address},
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "unknown"}

    with (
        patch(
            "homeassistant.components.avea.config_flow.avea.Bulb",
            return_value=_mock_bulb("Bedroom", 0),
        ),
        patch("homeassistant.components.avea.async_setup_entry", return_value=True),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_ADDRESS: AVEA_DISCOVERY_INFO.address},
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Bedroom"


async def test_bluetooth_step_success(hass: HomeAssistant) -> None:
    """Test bluetooth discovery starts the flow and creates an entry."""
    inject_bluetooth_service_info(hass, AVEA_DISCOVERY_INFO)
    await hass.async_block_till_done(wait_background_tasks=True)

    result = next(iter(hass.config_entries.flow.async_progress_by_handler(DOMAIN)))

    assert result["step_id"] == "bluetooth_confirm"

    with (
        patch(
            "homeassistant.components.avea.config_flow.avea.Bulb",
            return_value=_mock_bulb(RuntimeError("name"), 0),
        ),
        patch("homeassistant.components.avea.async_setup_entry", return_value=True),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {},
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == AVEA_DISCOVERY_INFO.name
    assert result["data"] == {CONF_ADDRESS: AVEA_DISCOVERY_INFO.address}
    assert result["result"].unique_id == AVEA_DISCOVERY_INFO.address


async def test_bluetooth_step_uses_discovery_name_for_unknown_bulb_name(
    hass: HomeAssistant,
) -> None:
    """Test bluetooth discovery falls back from the library default name."""
    inject_bluetooth_service_info(hass, AVEA_DISCOVERY_INFO)
    await hass.async_block_till_done(wait_background_tasks=True)

    progress = next(iter(hass.config_entries.flow.async_progress_by_handler(DOMAIN)))

    with (
        patch(
            "homeassistant.components.avea.config_flow.avea.Bulb",
            return_value=_mock_bulb("Unknown", 0),
        ),
        patch("homeassistant.components.avea.async_setup_entry", return_value=True),
    ):
        result = await hass.config_entries.flow.async_configure(
            progress["flow_id"],
            {},
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == AVEA_DISCOVERY_INFO.name


async def test_bluetooth_step_cannot_connect_recovers(hass: HomeAssistant) -> None:
    """Test bluetooth confirmation recovers after cannot connect."""
    inject_bluetooth_service_info(hass, AVEA_DISCOVERY_INFO)
    await hass.async_block_till_done(wait_background_tasks=True)

    progress = next(iter(hass.config_entries.flow.async_progress_by_handler(DOMAIN)))
    failing_bulb = _mock_bulb("Avea Bulb", 0)
    failing_bulb.get_brightness.side_effect = RuntimeError

    with patch(
        "homeassistant.components.avea.config_flow.avea.Bulb",
        return_value=failing_bulb,
    ):
        result = await hass.config_entries.flow.async_configure(
            progress["flow_id"],
            {},
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "bluetooth_confirm"
    assert result["errors"] == {"base": "cannot_connect"}

    with (
        patch(
            "homeassistant.components.avea.config_flow.avea.Bulb",
            return_value=_mock_bulb("Avea Bulb", 0),
        ),
        patch("homeassistant.components.avea.async_setup_entry", return_value=True),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {},
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Avea Bulb"


async def test_import_step_success(hass: HomeAssistant) -> None:
    """Test the YAML import step."""
    with patch("homeassistant.components.avea.async_setup_entry", return_value=True):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data={
                CONF_ADDRESS: AVEA_DISCOVERY_INFO.address,
                CONF_NAME: "Bedroom",
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Bedroom"
    assert result["data"] == {CONF_ADDRESS: AVEA_DISCOVERY_INFO.address}
    assert result["result"].unique_id == AVEA_DISCOVERY_INFO.address


async def test_import_step_aborts_bluetooth_flow_in_progress(
    hass: HomeAssistant,
) -> None:
    """Test YAML import can complete while a Bluetooth flow is in progress."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_BLUETOOTH},
        data=AVEA_DISCOVERY_INFO,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "bluetooth_confirm"
    assert hass.config_entries.flow.async_progress_by_handler(DOMAIN)

    with patch("homeassistant.components.avea.async_setup_entry", return_value=True):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data={
                CONF_ADDRESS: AVEA_DISCOVERY_INFO.address,
                CONF_NAME: "Bedroom",
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Bedroom"
    assert result["data"] == {CONF_ADDRESS: AVEA_DISCOVERY_INFO.address}
    assert result["result"].unique_id == AVEA_DISCOVERY_INFO.address
    assert not hass.config_entries.flow.async_progress_by_handler(DOMAIN)
