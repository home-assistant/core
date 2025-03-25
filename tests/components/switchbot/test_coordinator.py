"""Test the switchbot coordinator."""

from unittest.mock import patch

import pytest
import switchbot

from homeassistant.components import bluetooth
from homeassistant.components.switchbot.const import DOMAIN
from homeassistant.const import CONF_ADDRESS, CONF_NAME, CONF_SENSOR_TYPE
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from . import WOCURTAIN3_SERVICE_INFO

from tests.common import MockConfigEntry
from tests.components.bluetooth import inject_bluetooth_service_info


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_async_handle_unavailable(hass: HomeAssistant) -> None:
    """Test handling device unavailability."""
    await async_setup_component(hass, DOMAIN, {})
    inject_bluetooth_service_info(hass, WOCURTAIN3_SERVICE_INFO)

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_ADDRESS: "AA:BB:CC:DD:EE:FF",
            CONF_NAME: "test-name",
            CONF_SENSOR_TYPE: "curtain",
        },
        unique_id="aabbccddeeff",
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    coordinator = entry.runtime_data
    coordinator._async_handle_unavailable(WOCURTAIN3_SERVICE_INFO)

    assert coordinator._was_unavailable is True


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_not_advertisement_changed(hass: HomeAssistant) -> None:
    """Test handling bluetooth event when not adv changed."""
    await async_setup_component(hass, DOMAIN, {})
    inject_bluetooth_service_info(hass, WOCURTAIN3_SERVICE_INFO)

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_ADDRESS: "AA:BB:CC:DD:EE:FF",
            CONF_NAME: "test-name",
            CONF_SENSOR_TYPE: "curtain",
        },
        unique_id="aabbccddeeff",
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    coordinator = entry.runtime_data
    coordinator._was_unavailable = False

    with patch.object(
        switchbot.SwitchbotDevice, "advertisement_changed", return_value=False
    ) as mock_advertisement_changed:
        coordinator._async_handle_bluetooth_event(
            WOCURTAIN3_SERVICE_INFO, bluetooth.BluetoothChange.ADVERTISEMENT
        )
        mock_advertisement_changed.assert_called_once()
        assert coordinator._was_unavailable is False


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_not_adv(hass: HomeAssistant) -> None:
    """Test handling bluetooth event when not adv."""
    await async_setup_component(hass, DOMAIN, {})
    inject_bluetooth_service_info(hass, WOCURTAIN3_SERVICE_INFO)

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_ADDRESS: "AA:BB:CC:DD:EE:FF",
            CONF_NAME: "test-name",
            CONF_SENSOR_TYPE: "curtain",
        },
        unique_id="aabbccddeeff",
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    coordinator = entry.runtime_data

    with patch.object(
        switchbot, "parse_advertisement_data", return_value=False
    ) as mock_parse_advertisement_data:
        coordinator._async_handle_bluetooth_event(
            WOCURTAIN3_SERVICE_INFO, bluetooth.BluetoothChange.ADVERTISEMENT
        )
        mock_parse_advertisement_data.assert_called_once()


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_ready_event_timeout(hass: HomeAssistant) -> None:
    """Test coordinator wait ready timeout."""
    await async_setup_component(hass, DOMAIN, {})
    inject_bluetooth_service_info(hass, WOCURTAIN3_SERVICE_INFO)

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_ADDRESS: "AA:BB:CC:DD:EE:FF",
            CONF_NAME: "test-name",
            CONF_SENSOR_TYPE: "curtain",
        },
        unique_id="aabbccddeeff",
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    coordinator = entry.runtime_data

    with patch("asyncio.timeout", side_effect=TimeoutError):
        result = await coordinator.async_wait_ready()
        assert result is False
