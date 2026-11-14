"""Tests for the select platform."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from pyvesync import VeSync
from pyvesync.base_devices.outlet_base import VeSyncOutlet
from pyvesync.base_devices.purifier_base import VeSyncPurifier
from pyvesync.const import DeviceStatus, ProductTypes
from pyvesync.utils.errors import ResponseInfo

from homeassistant.components.select import (
    DOMAIN as SELECT_DOMAIN,
    SelectService,
    SelectServiceArgument,
)
from homeassistant.components.vesync.const import (
    DOMAIN,
    HUMIDIFIER_NIGHT_LIGHT_LEVEL_BRIGHT,
    HUMIDIFIER_NIGHT_LIGHT_LEVEL_DIM,
    HUMIDIFIER_NIGHT_LIGHT_LEVEL_OFF,
    OUTLET_NIGHT_LIGHT_LEVEL_AUTO,
    PURIFIER_NIGHT_LIGHT_LEVEL_ON,
)
from homeassistant.components.vesync.select import (
    HA_TO_VS_HUMIDIFIER_NIGHT_LIGHT_LEVEL_MAP,
)
from homeassistant.components.vesync.services import VeSyncService
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_UNKNOWN, CommonServiceArgument, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .common import ENTITY_HUMIDIFIER_300S_NIGHT_LIGHT_SELECT

ENTITY_PURIFIER_NIGHT_LIGHT_SELECT = "select.test_purifier_night_light_level"
ENTITY_OUTLET_NIGHT_LIGHT_SELECT = "select.test_outlet_night_light_level"


@pytest.fixture(autouse=True)
def select_platform_only() -> Generator[None]:
    """Only set up the select platform."""
    with patch("homeassistant.components.vesync.PLATFORMS", [Platform.SELECT]):
        yield


@pytest.fixture(name="purifier_with_nightlight")
def purifier_with_nightlight_fixture() -> Mock:
    """Create a mock VeSync air purifier that supports a night light."""
    return Mock(
        VeSyncPurifier,
        cid="purifier",
        sub_device_no=0,
        device_name="Test Purifier",
        device_type="Core200S",
        product_type=ProductTypes.PURIFIER,
        supports_nightlight=True,
        current_firm_version="1.0.0",
        state=Mock(connection_status="online", nightlight_status="dim"),
    )


@pytest.fixture(name="outlet_with_nightlight")
def outlet_with_nightlight_fixture() -> Mock:
    """Create a mock VeSync outlet that supports a night light."""
    return Mock(
        VeSyncOutlet,
        cid="outlet",
        sub_device_no=0,
        device_name="Test Outlet",
        device_type="ESW15-USA",
        product_type=ProductTypes.OUTLET,
        supports_nightlight=True,
        current_firm_version="1.0.0",
        state=Mock(connection_status="online", nightlight_status="off"),
    )


@pytest.mark.parametrize(
    "install_humidifier_device", ["humidifier_300s"], indirect=True
)
async def test_humidifier_set_nightlight_level(
    hass: HomeAssistant, humidifier_300s, install_humidifier_device
) -> None:
    """Test set of humidifier night light level."""

    await hass.services.async_call(
        SELECT_DOMAIN,
        SelectService.SELECT_OPTION,
        {
            CommonServiceArgument.ENTITY_ID: ENTITY_HUMIDIFIER_300S_NIGHT_LIGHT_SELECT,
            SelectServiceArgument.OPTION: HUMIDIFIER_NIGHT_LIGHT_LEVEL_DIM,
        },
        blocking=True,
    )

    # Assert that setter API was invoked with the expected translated value
    humidifier_300s.set_nightlight_brightness.assert_called_once_with(
        HA_TO_VS_HUMIDIFIER_NIGHT_LIGHT_LEVEL_MAP[HUMIDIFIER_NIGHT_LIGHT_LEVEL_DIM]
    )


@pytest.mark.parametrize(
    ("brightness", "nightlight_status", "expected_state"),
    [
        pytest.param(0, DeviceStatus.OFF, HUMIDIFIER_NIGHT_LIGHT_LEVEL_OFF, id="off"),
        pytest.param(50, DeviceStatus.ON, HUMIDIFIER_NIGHT_LIGHT_LEVEL_DIM, id="dim"),
        pytest.param(
            100, DeviceStatus.ON, HUMIDIFIER_NIGHT_LIGHT_LEVEL_BRIGHT, id="bright"
        ),
        pytest.param(12, DeviceStatus.ON, STATE_UNKNOWN, id="sprout-brightness"),
        pytest.param(75, DeviceStatus.ON, STATE_UNKNOWN, id="intermediate-brightness"),
        pytest.param(None, DeviceStatus.ON, STATE_UNKNOWN, id="missing-brightness"),
    ],
)
async def test_humidifier_nightlight_level(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    manager: MagicMock,
    humidifier_300s: Mock,
    brightness: int | None,
    nightlight_status: DeviceStatus,
    expected_state: str,
) -> None:
    """Test the state of humidifier night light level select entity."""
    humidifier_300s.state.nightlight_brightness = brightness
    humidifier_300s.state.nightlight_status = nightlight_status
    manager.devices.humidifiers.append(humidifier_300s)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert (
        hass.states.get(ENTITY_HUMIDIFIER_300S_NIGHT_LIGHT_SELECT).state
        == expected_state
    )


@pytest.mark.parametrize(
    (
        "device_fixture",
        "category",
        "entity_id",
        "expected_state",
        "option",
        "setter",
    ),
    [
        pytest.param(
            "purifier_with_nightlight",
            "air_purifiers",
            ENTITY_PURIFIER_NIGHT_LIGHT_SELECT,
            "dim",
            PURIFIER_NIGHT_LIGHT_LEVEL_ON,
            "set_nightlight_mode",
            id="purifier",
        ),
        pytest.param(
            "outlet_with_nightlight",
            "outlets",
            ENTITY_OUTLET_NIGHT_LIGHT_SELECT,
            "off",
            OUTLET_NIGHT_LIGHT_LEVEL_AUTO,
            "set_nightlight_state",
            id="outlet",
        ),
    ],
)
async def test_nightlight_select_option(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    manager: MagicMock,
    request: pytest.FixtureRequest,
    device_fixture: str,
    category: str,
    entity_id: str,
    expected_state: str,
    option: str,
    setter: str,
) -> None:
    """Test the state and setter of purifier and outlet night light selects."""
    device = request.getfixturevalue(device_fixture)
    getattr(manager.devices, category).append(device)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == expected_state

    await hass.services.async_call(
        SELECT_DOMAIN,
        SelectService.SELECT_OPTION,
        {
            CommonServiceArgument.ENTITY_ID: entity_id,
            SelectServiceArgument.OPTION: option,
        },
        blocking=True,
    )

    getattr(device, setter).assert_awaited_once_with(option)


@pytest.mark.parametrize(
    (
        "device_fixture",
        "category",
        "entity_id",
        "option",
        "setter",
        "attribute",
        "value",
    ),
    [
        pytest.param(
            "humidifier_300s",
            "humidifiers",
            ENTITY_HUMIDIFIER_300S_NIGHT_LIGHT_SELECT,
            HUMIDIFIER_NIGHT_LIGHT_LEVEL_DIM,
            "set_nightlight_brightness",
            "product_type",
            ProductTypes.FAN,
            id="not_humidifier",
        ),
        pytest.param(
            "purifier_with_nightlight",
            "air_purifiers",
            ENTITY_PURIFIER_NIGHT_LIGHT_SELECT,
            PURIFIER_NIGHT_LIGHT_LEVEL_ON,
            "set_nightlight_mode",
            "product_type",
            ProductTypes.FAN,
            id="not_purifier",
        ),
        pytest.param(
            "outlet_with_nightlight",
            "outlets",
            ENTITY_OUTLET_NIGHT_LIGHT_SELECT,
            OUTLET_NIGHT_LIGHT_LEVEL_AUTO,
            "set_nightlight_state",
            "product_type",
            ProductTypes.FAN,
            id="not_outlet",
        ),
        pytest.param(
            "outlet_with_nightlight",
            "outlets",
            ENTITY_OUTLET_NIGHT_LIGHT_SELECT,
            OUTLET_NIGHT_LIGHT_LEVEL_AUTO,
            "set_nightlight_state",
            "supports_nightlight",
            False,
            id="outlet_without_nightlight",
        ),
    ],
)
async def test_nightlight_select_option_unsupported(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    manager: MagicMock,
    request: pytest.FixtureRequest,
    device_fixture: str,
    category: str,
    entity_id: str,
    option: str,
    setter: str,
    attribute: str,
    value: ProductTypes | bool,
) -> None:
    """Test an error is raised when the device cannot set its night light."""
    device = request.getfixturevalue(device_fixture)
    getattr(manager.devices, category).append(device)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    # exists_fn filters these devices out, so change the device after setup
    setattr(device, attribute, value)

    with pytest.raises(
        HomeAssistantError, match="Device does not support toggling nightlight"
    ):
        await hass.services.async_call(
            SELECT_DOMAIN,
            SelectService.SELECT_OPTION,
            {
                CommonServiceArgument.ENTITY_ID: entity_id,
                SelectServiceArgument.OPTION: option,
            },
            blocking=True,
        )

    getattr(device, setter).assert_not_called()


@pytest.mark.parametrize(
    "install_humidifier_device", ["humidifier_300s"], indirect=True
)
@pytest.mark.parametrize(
    ("last_response", "message"),
    [
        pytest.param(
            ResponseInfo(name="error", error_type="error", message="Device error"),
            "Device error",
            id="last_response",
        ),
        pytest.param(
            None,
            "Unknown error selecting option, no response.",
            id="no_last_response",
        ),
    ],
)
@pytest.mark.usefixtures("install_humidifier_device")
async def test_select_option_device_failure(
    hass: HomeAssistant,
    humidifier_300s: Mock,
    last_response: ResponseInfo | None,
    message: str,
) -> None:
    """Test an error is raised when the device rejects the option."""
    humidifier_300s.set_nightlight_brightness.return_value = False
    humidifier_300s.last_response = last_response

    with pytest.raises(HomeAssistantError, match=message):
        await hass.services.async_call(
            SELECT_DOMAIN,
            SelectService.SELECT_OPTION,
            {
                CommonServiceArgument.ENTITY_ID: ENTITY_HUMIDIFIER_300S_NIGHT_LIGHT_SELECT,
                SelectServiceArgument.OPTION: HUMIDIFIER_NIGHT_LIGHT_LEVEL_DIM,
            },
            blocking=True,
        )


async def test_discover_new_device(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    manager: VeSync,
    humidifier_300s: Mock,
) -> None:
    """Test a select entity is added for a device discovered after setup."""
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get(ENTITY_HUMIDIFIER_300S_NIGHT_LIGHT_SELECT) is None

    manager.get_devices = AsyncMock(
        side_effect=lambda: manager.devices.humidifiers.append(humidifier_300s)
    )

    await hass.services.async_call(
        DOMAIN, VeSyncService.UPDATE_DEVICES, {}, blocking=True
    )
    await hass.async_block_till_done()

    assert (
        hass.states.get(ENTITY_HUMIDIFIER_300S_NIGHT_LIGHT_SELECT).state
        == HUMIDIFIER_NIGHT_LIGHT_LEVEL_DIM
    )
