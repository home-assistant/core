"""Tests for ScreenLogic integration service calls."""

from typing import Any
from unittest.mock import DEFAULT, AsyncMock, patch

import pytest
from screenlogicpy import ScreenLogicGateway
from screenlogicpy.device_const.system import COLOR_MODE

from homeassistant.components.screenlogic import DOMAIN
from homeassistant.components.screenlogic.const import (
    ATTR_COLOR_MODE,
    ATTR_CONFIG_ENTRY,
    ATTR_RUNTIME,
    SERVICE_SET_COLOR_MODE,
    SERVICE_START_SUPER_CHLORINATION,
    SERVICE_STOP_SUPER_CHLORINATION,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_AREA_ID, ATTR_DEVICE_ID, ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import device_registry as dr
from homeassistant.util import slugify

from . import (
    DATA_FULL_CHEM,
    DATA_FULL_CHEM_CHLOR,
    DATA_MIN_ENTITY_CLEANUP,
    GATEWAY_DISCOVERY_IMPORT_PATH,
    MOCK_ADAPTER_MAC,
    MOCK_ADAPTER_NAME,
    MOCK_CONFIG_ENTRY_ID,
    MOCK_DEVICE_AREA,
    stub_async_connect,
)

from tests.common import MockConfigEntry

NON_SL_CONFIG_ENTRY_ID = "test"


@pytest.fixture(name="dataset")
def dataset_fixture():
    """Define the default dataset for service tests."""
    return DATA_FULL_CHEM


@pytest.fixture(name="service_fixture")
async def setup_screenlogic_services_fixture(
    hass: HomeAssistant,
    request,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
):
    """Define the setup for a patched screenlogic integration."""
    data = (
        marker.args[0]
        if (marker := request.node.get_closest_marker("dataset")) is not None
        else DATA_FULL_CHEM
    )

    def _service_connect(*args, **kwargs):
        return stub_async_connect(data, *args, **kwargs)

    mock_config_entry.add_to_hass(hass)

    device: dr.DeviceEntry = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, MOCK_ADAPTER_MAC)},
        suggested_area=MOCK_DEVICE_AREA,
    )

    with (
        patch(
            GATEWAY_DISCOVERY_IMPORT_PATH,
            return_value={},
        ),
        patch.multiple(
            ScreenLogicGateway,
            async_connect=_service_connect,
            is_connected=True,
            _async_connected_request=DEFAULT,
            async_set_color_lights=DEFAULT,
            async_set_scg_config=DEFAULT,
        ) as gateway,
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        yield {"gateway": gateway, "device": device}


@pytest.mark.parametrize(
    ("data", "target"),
    [
        (
            {
                ATTR_COLOR_MODE: COLOR_MODE.ALL_OFF.name.lower(),
                ATTR_CONFIG_ENTRY: MOCK_CONFIG_ENTRY_ID,
            },
            None,
        ),
        (
            {
                ATTR_COLOR_MODE: COLOR_MODE.ALL_ON.name.lower(),
            },
            {
                ATTR_AREA_ID: MOCK_DEVICE_AREA,
            },
        ),
        (
            {
                ATTR_COLOR_MODE: COLOR_MODE.ALL_ON.name.lower(),
            },
            {
                ATTR_ENTITY_ID: f"{Platform.SENSOR}.{slugify(f'{MOCK_ADAPTER_NAME} Air Temperature')}",
            },
        ),
    ],
)
async def test_service_set_color_mode(
    hass: HomeAssistant,
    service_fixture: dict[str, Any],
    data: dict[str, Any],
    target: dict[str, Any],
) -> None:
    """Test set_color_mode service."""

    mocked_async_set_color_lights: AsyncMock = service_fixture["gateway"][
        "async_set_color_lights"
    ]

    assert hass.services.has_service(DOMAIN, SERVICE_SET_COLOR_MODE)

    non_screenlogic_entry = MockConfigEntry(entry_id="test")
    non_screenlogic_entry.add_to_hass(hass)

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_COLOR_MODE,
        service_data=data,
        blocking=True,
        target=target,
    )

    mocked_async_set_color_lights.assert_awaited_once()


async def test_service_set_color_mode_with_device(
    hass: HomeAssistant,
    service_fixture: dict[str, Any],
) -> None:
    """Test set_color_mode service with a device target."""
    mocked_async_set_color_lights: AsyncMock = service_fixture["gateway"][
        "async_set_color_lights"
    ]

    assert hass.services.has_service(DOMAIN, SERVICE_SET_COLOR_MODE)

    sl_device: dr.DeviceEntry = service_fixture["device"]

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_COLOR_MODE,
        service_data={ATTR_COLOR_MODE: COLOR_MODE.ALL_ON.name.lower()},
        blocking=True,
        target={ATTR_DEVICE_ID: sl_device.id},
    )

    mocked_async_set_color_lights.assert_awaited_once()


@pytest.mark.parametrize(
    ("data", "target", "error_msg"),
    [
        (
            {
                ATTR_COLOR_MODE: COLOR_MODE.ALL_OFF.name.lower(),
                ATTR_CONFIG_ENTRY: "invalidconfigentry",
            },
            None,
            f"Failed to call service '{SERVICE_SET_COLOR_MODE}'. Config entry "
            "'invalidconfigentry' not found",
        ),
        (
            {
                ATTR_COLOR_MODE: COLOR_MODE.ALL_OFF.name.lower(),
                ATTR_CONFIG_ENTRY: NON_SL_CONFIG_ENTRY_ID,
            },
            None,
            f"Failed to call service '{SERVICE_SET_COLOR_MODE}'. Config entry "
            "'test' is not a screenlogic config",
        ),
        (
            {
                ATTR_COLOR_MODE: COLOR_MODE.ALL_ON.name.lower(),
            },
            {
                ATTR_AREA_ID: "invalidareaid",
            },
            f"Failed to call service '{SERVICE_SET_COLOR_MODE}'. Config entry for "
            "target not found",
        ),
        (
            {
                ATTR_COLOR_MODE: COLOR_MODE.ALL_ON.name.lower(),
            },
            {
                ATTR_DEVICE_ID: "invaliddeviceid",
            },
            f"Failed to call service '{SERVICE_SET_COLOR_MODE}'. Config entry for "
            "target not found",
        ),
        (
            {
                ATTR_COLOR_MODE: COLOR_MODE.ALL_ON.name.lower(),
            },
            {
                ATTR_ENTITY_ID: "sensor.invalidentityid",
            },
            f"Failed to call service '{SERVICE_SET_COLOR_MODE}'. Config entry for "
            "target not found",
        ),
    ],
)
async def test_service_set_color_mode_error(
    hass: HomeAssistant,
    service_fixture: dict[str, Any],
    data: dict[str, Any],
    target: dict[str, Any],
    error_msg: str,
) -> None:
    """Test set_color_mode service error cases."""

    mocked_async_set_color_lights: AsyncMock = service_fixture["gateway"][
        "async_set_color_lights"
    ]

    non_screenlogic_entry = MockConfigEntry(entry_id=NON_SL_CONFIG_ENTRY_ID)
    non_screenlogic_entry.add_to_hass(hass)

    assert hass.services.has_service(DOMAIN, SERVICE_SET_COLOR_MODE)

    with pytest.raises(
        ServiceValidationError,
        match=error_msg,
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_COLOR_MODE,
            service_data=data,
            blocking=True,
            target=target,
        )

    mocked_async_set_color_lights.assert_not_awaited()


@pytest.mark.dataset(DATA_FULL_CHEM_CHLOR)
@pytest.mark.parametrize(
    ("data", "target"),
    [
        (
            {
                ATTR_CONFIG_ENTRY: MOCK_CONFIG_ENTRY_ID,
                ATTR_RUNTIME: 24,
            },
            None,
        ),
    ],
)
async def test_service_start_super_chlorination(
    hass: HomeAssistant,
    service_fixture: dict[str, Any],
    data: dict[str, Any],
    target: dict[str, Any],
) -> None:
    """Test start_super_chlorination service."""

    mocked_async_set_scg_config: AsyncMock = service_fixture["gateway"][
        "async_set_scg_config"
    ]

    assert hass.services.has_service(DOMAIN, SERVICE_START_SUPER_CHLORINATION)

    await hass.services.async_call(
        DOMAIN,
        SERVICE_START_SUPER_CHLORINATION,
        service_data=data,
        blocking=True,
        target=target,
    )

    mocked_async_set_scg_config.assert_awaited_once()


@pytest.mark.parametrize(
    ("data", "target", "error_msg"),
    [
        (
            {
                ATTR_CONFIG_ENTRY: "invalidconfigentry",
                ATTR_RUNTIME: 24,
            },
            None,
            f"Failed to call service '{SERVICE_START_SUPER_CHLORINATION}'. "
            "Config entry 'invalidconfigentry' not found",
        ),
        (
            {
                ATTR_CONFIG_ENTRY: MOCK_CONFIG_ENTRY_ID,
                ATTR_RUNTIME: 24,
            },
            None,
            f"Equipment configuration for {MOCK_ADAPTER_NAME} does not"
            f" support {SERVICE_START_SUPER_CHLORINATION}",
        ),
    ],
)
async def test_service_start_super_chlorination_error(
    hass: HomeAssistant,
    service_fixture: dict[str, Any],
    data: dict[str, Any],
    target: dict[str, Any],
    error_msg: str,
) -> None:
    """Test start_super_chlorination service error cases."""

    mocked_async_set_scg_config: AsyncMock = service_fixture["gateway"][
        "async_set_scg_config"
    ]

    assert hass.services.has_service(DOMAIN, SERVICE_START_SUPER_CHLORINATION)

    with pytest.raises(
        ServiceValidationError,
        match=error_msg,
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_START_SUPER_CHLORINATION,
            service_data=data,
            blocking=True,
            target=target,
        )

    mocked_async_set_scg_config.assert_not_awaited()


@pytest.mark.dataset(DATA_FULL_CHEM_CHLOR)
@pytest.mark.parametrize(
    ("data", "target"),
    [
        (
            {
                ATTR_CONFIG_ENTRY: MOCK_CONFIG_ENTRY_ID,
            },
            None,
        ),
    ],
)
async def test_service_stop_super_chlorination(
    hass: HomeAssistant,
    service_fixture: dict[str, Any],
    data: dict[str, Any],
    target: dict[str, Any],
) -> None:
    """Test stop_super_chlorination service."""

    mocked_async_set_scg_config: AsyncMock = service_fixture["gateway"][
        "async_set_scg_config"
    ]

    assert hass.services.has_service(DOMAIN, SERVICE_STOP_SUPER_CHLORINATION)

    await hass.services.async_call(
        DOMAIN,
        SERVICE_STOP_SUPER_CHLORINATION,
        service_data=data,
        blocking=True,
        target=target,
    )

    mocked_async_set_scg_config.assert_awaited_once()


@pytest.mark.parametrize(
    ("data", "target", "error_msg"),
    [
        (
            {
                ATTR_CONFIG_ENTRY: "invalidconfigentry",
            },
            None,
            f"Failed to call service '{SERVICE_STOP_SUPER_CHLORINATION}'. "
            "Config entry 'invalidconfigentry' not found",
        ),
        (
            {
                ATTR_CONFIG_ENTRY: MOCK_CONFIG_ENTRY_ID,
            },
            None,
            f"Equipment configuration for {MOCK_ADAPTER_NAME} does not"
            f" support {SERVICE_STOP_SUPER_CHLORINATION}",
        ),
    ],
)
async def test_service_stop_super_chlorination_error(
    hass: HomeAssistant,
    service_fixture: dict[str, Any],
    data: dict[str, Any],
    target: dict[str, Any],
    error_msg: str,
) -> None:
    """Test stop_super_chlorination service error cases."""

    mocked_async_set_scg_config: AsyncMock = service_fixture["gateway"][
        "async_set_scg_config"
    ]

    assert hass.services.has_service(DOMAIN, SERVICE_STOP_SUPER_CHLORINATION)

    with pytest.raises(
        ServiceValidationError,
        match=error_msg,
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_STOP_SUPER_CHLORINATION,
            service_data=data,
            blocking=True,
            target=target,
        )

    mocked_async_set_scg_config.assert_not_awaited()


async def test_service_config_entry_not_loaded(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the error case of config not loaded."""
    mock_config_entry.add_to_hass(hass)

    _ = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, MOCK_ADAPTER_MAC)},
    )

    mock_set_color_lights = AsyncMock()

    with (
        patch(
            GATEWAY_DISCOVERY_IMPORT_PATH,
            return_value={},
        ),
        patch.multiple(
            ScreenLogicGateway,
            async_connect=lambda *args, **kwargs: stub_async_connect(
                DATA_MIN_ENTITY_CLEANUP, *args, **kwargs
            ),
            async_disconnect=DEFAULT,
            is_connected=True,
            _async_connected_request=DEFAULT,
            async_set_color_lights=mock_set_color_lights,
        ),
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        assert hass.services.has_service(DOMAIN, SERVICE_SET_COLOR_MODE)
        assert len(hass.config_entries.async_entries(DOMAIN)) == 1

        await hass.config_entries.async_unload(mock_config_entry.entry_id)
        await hass.async_block_till_done()
        assert mock_config_entry.state is ConfigEntryState.NOT_LOADED

        with pytest.raises(
            ServiceValidationError,
            match=f"Failed to call service '{SERVICE_SET_COLOR_MODE}'. "
            f"Config entry '{MOCK_CONFIG_ENTRY_ID}' not loaded",
        ):
            await hass.services.async_call(
                DOMAIN,
                SERVICE_SET_COLOR_MODE,
                service_data={
                    ATTR_COLOR_MODE: COLOR_MODE.ALL_OFF.name.lower(),
                    ATTR_CONFIG_ENTRY: MOCK_CONFIG_ENTRY_ID,
                },
                blocking=True,
            )

        mock_set_color_lights.assert_not_awaited()
