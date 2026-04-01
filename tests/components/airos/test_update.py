"""Test the Ubiquiti airOS firmware update."""

from unittest.mock import AsyncMock

from airos.exceptions import (
    AirOSConnectionAuthenticationError,
    AirOSDeviceConnectionError,
    AirOSException,
)
import pytest

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry


@pytest.mark.parametrize(
    ("ap_status_fixture", "ap_firmware_fixture", "entity_id"),
    [
        ("airos_loco5ac_ap-ptp.json", True, "update.nanostation_5ac_ap_name_firmware"),
        ("airos_liteapgps_ap_ptmp_40mhz.json", True, "update.house_bridge_firmware"),
    ],
    indirect=["ap_status_fixture", "ap_firmware_fixture"],
)
async def test_update_entity(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_airos_client: AsyncMock,
    mock_async_get_firmware_data: AsyncMock,
    entity_id: str,
) -> None:
    """Test the firmware update entity behavior."""
    await setup_integration(hass, mock_config_entry, [Platform.UPDATE])

    entries = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    update_entities = [e for e in entries if e.domain == "update"]

    assert len(update_entities) == 1
    assert update_entities[0].entity_id == entity_id

    state = hass.states.get(entity_id)
    assert state is not None

    await hass.services.async_call(
        "update",
        "install",
        {"entity_id": entity_id},
        blocking=True,
    )

    mock_airos_client.update_check.assert_awaited()
    mock_airos_client.download.assert_awaited()
    mock_airos_client.install.assert_awaited()

    await hass.async_block_till_done()
    new_state = hass.states.get(entity_id)
    assert new_state is not None


@pytest.mark.parametrize(
    "ap_status_fixture",
    [
        "airos_NanoStation_loco_M5_v6.3.16_XM_sta.json",
        "airos_NanoStation_M5_sta_v6.3.16.json",
    ],
    indirect=True,
)
async def test_no_update_entity(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_airos_client: AsyncMock,
    mock_async_get_firmware_data: AsyncMock,
    ap_firmware_fixture: dict[str, bool],
) -> None:
    """Test the firmware update entity behavior is not implemented."""
    await setup_integration(hass, mock_config_entry, [Platform.UPDATE])

    entries = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    update_entities = [e for e in entries if e.domain == "update"]

    assert not update_entities


@pytest.mark.parametrize(
    ("ap_status_fixture", "ap_firmware_fixture", "exception", "translation_key"),
    [
        (
            "airos_loco5ac_ap-ptp.json",
            True,
            AirOSConnectionAuthenticationError,
            "update_connection_authentication_error",
        ),
        (
            "airos_liteapgps_ap_ptmp_40mhz.json",
            True,
            AirOSDeviceConnectionError,
            "update_error",
        ),
    ],
    indirect=["ap_status_fixture", "ap_firmware_fixture"],
)
async def test_update_failure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_airos_client: AsyncMock,
    mock_async_get_firmware_data: AsyncMock,
    exception: AirOSException,
    translation_key: str,
) -> None:
    """Test the firmware update entity behavior."""
    await setup_integration(hass, mock_config_entry, [Platform.UPDATE])

    entries = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    update_entities = [e for e in entries if e.domain == "update"]

    assert len(update_entities) == 1
    entity_id = update_entities[0].entity_id

    state = hass.states.get(entity_id)
    assert state is not None

    mock_airos_client.download.side_effect = exception

    with pytest.raises(HomeAssistantError) as exc:
        await hass.services.async_call(
            "update",
            "install",
            {"entity_id": entity_id},
            blocking=True,
        )

    assert exc.value.translation_key == translation_key
