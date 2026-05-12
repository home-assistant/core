"""Lifecycle and registry tests for the Inepro Metering integration."""

from unittest.mock import AsyncMock, patch

from inepro_metering.const import MeterFamily, TransportType
import pytest

from homeassistant.components.inepro_metering import (
    EXC_WIFI_CREDENTIALS_NOT_LOADED,
    SERVICE_SET_WIFI_CREDENTIALS,
    async_remove_config_entry_device,
)
from homeassistant.components.inepro_metering.const import (
    CONF_BAUDRATE,
    CONF_BYTESIZE,
    CONF_FAMILY,
    CONF_METERS,
    CONF_PARITY,
    CONF_SERIAL_NUMBER,
    CONF_SERIAL_PORT,
    CONF_SLAVE_ID,
    CONF_STOPBITS,
    CONF_TIMEOUT,
    CONF_TRANSPORT,
    CONF_VARIANT,
    DEFAULT_BAUDRATE,
    DEFAULT_BYTESIZE,
    DEFAULT_PARITY,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_STOPBITS,
    DOMAIN,
)
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import device_registry as dr

from tests.common import MockConfigEntry


class _FakeCoordinator:
    """Small coordinator stub used to isolate setup lifecycle behavior."""

    def __init__(self) -> None:
        self.async_config_entry_first_refresh = AsyncMock()
        self.async_shutdown = AsyncMock()


async def test_setup_entry_uses_runtime_data_and_service_survives_unload(
    hass,
) -> None:
    """Config entries should keep runtime data on the entry and keep services loaded."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="075625480002",
        unique_id="075625480002",
        data={
            CONF_FAMILY: MeterFamily.GROW.value,
            CONF_VARIANT: "grow_750",
            CONF_TRANSPORT: TransportType.TCP_ETHERNET.value,
            CONF_SLAVE_ID: 1,
            CONF_TIMEOUT: 3,
            "host": "192.168.68.80",
            "port": 502,
            "scan_interval": DEFAULT_SCAN_INTERVAL,
            CONF_SERIAL_NUMBER: "075625480002",
        },
        version=5,
    )
    entry.add_to_hass(hass)
    coordinator = _FakeCoordinator()

    with (
        patch(
            "homeassistant.components.inepro_metering.build_runtime_coordinator",
            return_value=coordinator,
        ),
        patch.object(
            hass.config_entries,
            "async_forward_entry_setups",
            AsyncMock(return_value=True),
        ),
        patch.object(
            hass.config_entries,
            "async_unload_platforms",
            AsyncMock(return_value=True),
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        assert entry.runtime_data is coordinator
        assert hass.services.has_service(DOMAIN, SERVICE_SET_WIFI_CREDENTIALS)

        assert await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()

    coordinator.async_shutdown.assert_awaited_once()
    assert hass.services.has_service(DOMAIN, SERVICE_SET_WIFI_CREDENTIALS)

    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_WIFI_CREDENTIALS,
            {
                "serial_number": "075625480002",
                "ssid": "IneproLab",
                "password": "secret",
            },
            blocking=True,
        )
    err = exc_info.value
    assert err.translation_domain == DOMAIN
    assert err.translation_key == EXC_WIFI_CREDENTIALS_NOT_LOADED
    assert err.translation_placeholders == {"serial_number": "075625480002"}


async def test_async_remove_config_entry_device_allows_only_stale_bus_devices(
    hass,
) -> None:
    """Device removal should stay blocked for current meters and allow stale leftovers."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Main RS485 Bus",
        unique_id="COM5",
        data={
            CONF_FAMILY: MeterFamily.GROW.value,
            CONF_TRANSPORT: TransportType.SERIAL.value,
            "scan_interval": DEFAULT_SCAN_INTERVAL,
            CONF_SERIAL_PORT: "COM5",
            CONF_BAUDRATE: DEFAULT_BAUDRATE,
            CONF_BYTESIZE: DEFAULT_BYTESIZE,
            CONF_PARITY: DEFAULT_PARITY,
            CONF_STOPBITS: DEFAULT_STOPBITS,
            CONF_TIMEOUT: 3,
            CONF_METERS: [
                {
                    CONF_FAMILY: MeterFamily.GROW.value,
                    "name": "085125250008",
                    CONF_VARIANT: "grow_850",
                    CONF_SLAVE_ID: 1,
                    CONF_SERIAL_NUMBER: "085125250008",
                    "product_code": "0851",
                },
                {
                    CONF_FAMILY: MeterFamily.GROW.value,
                    "name": "075625480002",
                    CONF_VARIANT: "grow_750",
                    CONF_SLAVE_ID: 157,
                    CONF_SERIAL_NUMBER: "075625480002",
                    "product_code": "0756",
                },
            ],
        },
        version=5,
    )
    entry.add_to_hass(hass)

    device_registry = dr.async_get(hass)
    primary_device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, "085125250008")},
    )
    secondary_device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, "075625480002")},
    )
    stale_device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, f"{entry.entry_id}:stale-meter")},
    )

    assert not await async_remove_config_entry_device(hass, entry, primary_device)
    assert not await async_remove_config_entry_device(hass, entry, secondary_device)
    assert await async_remove_config_entry_device(hass, entry, stale_device)
