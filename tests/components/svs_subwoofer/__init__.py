"""Tests for the SVS Subwoofer integration."""

from unittest.mock import MagicMock, patch

from homeassistant.components.bluetooth import BluetoothServiceInfoBleak
from homeassistant.components.svs_subwoofer.const import DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry
from tests.components.bluetooth import generate_advertisement_data, generate_ble_device

SVS_SERVICE_UUID = "1fee6acf-a826-4e37-9635-4d8a01642c5d"

SVS_ADDRESS = "08:EB:ED:11:22:33"
SVS_NAME = "RIGHTSUB"

def _service_info(
    address: str = SVS_ADDRESS, name: str = SVS_NAME
) -> BluetoothServiceInfoBleak:
    """Build a BluetoothServiceInfoBleak for an SVS subwoofer."""
    return BluetoothServiceInfoBleak(
        name=name,
        address=address,
        rssi=-50,
        manufacturer_data={},
        service_data={},
        service_uuids=[SVS_SERVICE_UUID],
        source="local",
        device=generate_ble_device(address=address, name=name),
        advertisement=generate_advertisement_data(
            local_name=name,
            service_uuids=[SVS_SERVICE_UUID],
        ),
        connectable=True,
        time=0,
        tx_power=0,
    )

SVS_SERVICE_INFO = _service_info()

def patch_async_setup_entry(return_value: bool = True):
    """Patch async_setup_entry."""
    return patch(
        "homeassistant.components.svs_subwoofer.async_setup_entry",
        return_value=return_value,
    )

def patch_async_discovered_service_info(
    return_value: list[BluetoothServiceInfoBleak] | None = None,
):
    """Patch async_discovered_service_info as imported by config_flow."""
    return patch(
        "homeassistant.components.svs_subwoofer.config_flow."
        "async_discovered_service_info",
        return_value=return_value or [],
    )

async def async_init_integration(
    hass: HomeAssistant,
    *,
    address: str = SVS_ADDRESS,
    name: str = SVS_NAME,
    bleak_client: MagicMock | None = None,
) -> ConfigEntry:
    """Create the config entry and set up the integration with BLE mocked."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=address.lower(),
        data={CONF_ADDRESS: address, CONF_NAME: name},
        title=name,
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.svs_subwoofer.coordinator."
        "async_ble_device_from_address",
        return_value=MagicMock(),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    return entry

def entity_id(hass: HomeAssistant, platform: str, address: str, key: str) -> str:
    """Resolve a configured entity's entity_id by its unique_id.

    Uses the entity registry instead of guessing slugs, which keeps tests
    robust to translation/slug variations.
    """
    resolved = er.async_get(hass).async_get_entity_id(
        platform, DOMAIN, f"{address}_{key}"
    )
    assert resolved is not None, f"no {platform} entity for {address}_{key}"
    return resolved
