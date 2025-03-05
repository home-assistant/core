"""Test Govee light local config flow."""

from errno import EADDRINUSE
from unittest.mock import AsyncMock, patch

from govee_local_api import GoveeDevice

from homeassistant import config_entries
from homeassistant.components.govee_light_local.const import (
    CONF_AUTO_DISCOVERY,
    CONF_DEVICE_IP,
    CONF_IPS_TO_REMOVE,
    CONF_MANUAL_DEVICES,
    DOMAIN,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import DEFAULT_CAPABILITIES, set_mocked_devices

from tests.common import MockConfigEntry


def _get_devices(
    mock_govee_api: AsyncMock, is_manual: bool = False
) -> list[GoveeDevice]:
    devices: list[GoveeDevice] = [
        GoveeDevice(
            controller=mock_govee_api,
            ip="192.168.1.100",
            fingerprint="asdawdqwdqwd1",
            sku="H615A",
            capabilities=DEFAULT_CAPABILITIES,
        )
    ]
    for device in devices:
        device.is_manual = is_manual
    return devices


async def test_creating_entry_has_no_devices(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, mock_govee_api: AsyncMock
) -> None:
    """Test setting up Govee with no devices."""

    set_mocked_devices(mock_govee_api, [])

    with patch(
        "homeassistant.components.govee_light_local.config_flow.DISCOVERY_TIMEOUT",
        0,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] is FlowResultType.FORM

        # Auto Discovery selection
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_AUTO_DISCOVERY: True}
        )
        assert result["type"] is FlowResultType.FORM

        # Confirmation form
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        assert result["type"] is FlowResultType.ABORT

        await hass.async_block_till_done()
        mock_govee_api.start.assert_awaited_once()
        mock_setup_entry.assert_not_called()


async def test_creating_entry_has_with_devices(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_govee_api: AsyncMock,
) -> None:
    """Test setting up Govee with devices."""

    set_mocked_devices(mock_govee_api, _get_devices(mock_govee_api))

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM

    # Auto Discovery selection
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_AUTO_DISCOVERY: True}
    )
    assert result["type"] is FlowResultType.FORM

    # Confirmation form
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.CREATE_ENTRY

    await hass.async_block_till_done()

    mock_govee_api.start.assert_awaited_once()
    mock_setup_entry.assert_awaited_once()


async def test_creating_entry_errno(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_govee_api: AsyncMock,
) -> None:
    """Test setting up Govee with devices."""

    e = OSError()
    e.errno = EADDRINUSE
    mock_govee_api.start.side_effect = e
    set_mocked_devices(mock_govee_api, _get_devices(mock_govee_api))

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM

    # Auto Discovery selection
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_AUTO_DISCOVERY: True}
    )
    assert result["type"] is FlowResultType.FORM

    # Confirmation form
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.ABORT

    await hass.async_block_till_done()

    assert mock_govee_api.start.call_count == 1
    mock_setup_entry.assert_not_awaited()


async def test_creating_entry_no_discovery(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_govee_api: AsyncMock,
) -> None:
    """Test setting up Govee without discovery."""

    set_mocked_devices(mock_govee_api, _get_devices(mock_govee_api))

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM

    # Auto Discovery selection
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_AUTO_DISCOVERY: False}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY

    await hass.async_block_till_done()

    mock_govee_api.start.assert_not_awaited()
    mock_setup_entry.assert_awaited_once()


async def test_options_flow_init_menu(hass: HomeAssistant) -> None:
    """Test options flow menu."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_AUTO_DISCOVERY: True},
    )
    config_entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(config_entry.entry_id)

    assert result["type"] == "menu"
    assert result["step_id"] == "init"
    assert result["menu_options"] == [
        "add_device",
        "remove_device",
        "configure_auto_discovery",
    ]


async def test_options_flow_auto_discovery(hass: HomeAssistant) -> None:
    """Test configuring auto discovery through options flow."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_AUTO_DISCOVERY: True},
    )
    config_entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={"next_step_id": "configure_auto_discovery"},
    )

    assert result["type"] == "form"
    assert result["step_id"] == "configure_auto_discovery"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_AUTO_DISCOVERY: False},
    )

    assert result["type"] == "create_entry"
    assert result["data"] == {CONF_AUTO_DISCOVERY: False}


async def test_options_flow_add_device(hass: HomeAssistant) -> None:
    """Test adding a manual device through options flow."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_AUTO_DISCOVERY: False},
    )
    config_entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={"next_step_id": "add_device"},
    )

    assert result["type"] == "form"
    assert result["step_id"] == "add_device"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_DEVICE_IP: "192.168.1.100"},
    )

    assert result["type"] == "create_entry"
    assert result["data"] == {CONF_MANUAL_DEVICES: ["192.168.1.100"]}


async def test_options_flow_remove_device_with_devices(
    hass: HomeAssistant, mock_coordinator: AsyncMock
) -> None:
    """Test removing a manual device through options flow."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_AUTO_DISCOVERY: False},
        options={CONF_MANUAL_DEVICES: ["192.168.1.100", "192.168.1.101"]},
    )

    config_entry.add_to_hass(hass)

    # Mock coordinator with devices
    mock_device = AsyncMock()
    mock_device.ip = "192.168.1.100"
    mock_device.is_manual = True

    mock_coordinator.devices = [mock_device]
    mock_coordinator.discovery_queue = []
    config_entry.runtime_data = mock_coordinator

    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={"next_step_id": "remove_device"},
    )

    assert result["type"] == "form"
    assert result["step_id"] == "remove_device"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_IPS_TO_REMOVE: ["192.168.1.100"]},
    )

    assert result["type"] == "create_entry"
    assert result["data"] == {CONF_IPS_TO_REMOVE: ["192.168.1.100"]}


async def test_options_flow_remove_device_no_devices(hass: HomeAssistant) -> None:
    """Test removing devices when none are available."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_AUTO_DISCOVERY: False},
    )
    config_entry.add_to_hass(hass)

    # Mock coordinator with no devices
    mock_coordinator = AsyncMock()
    mock_coordinator.devices = []
    mock_coordinator.discovery_queue = []
    config_entry.runtime_data = mock_coordinator

    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={"next_step_id": "remove_device"},
    )

    assert result["type"] == "abort"
    assert result["reason"] == "no_devices"
