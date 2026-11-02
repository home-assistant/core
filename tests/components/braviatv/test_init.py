"""Test the Bravia TV integration setup."""

from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed

from homeassistant.components import ssdp
from homeassistant.components.braviatv.const import CONF_USE_PSK, DOMAIN
from homeassistant.const import CONF_HOST, CONF_MAC, CONF_PIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.service_info.ssdp import SsdpServiceInfo

from . import init_integration

ENTRY_DATA = {
    CONF_HOST: "bravia-host",
    CONF_MAC: "AA:BB:CC:DD:EE:FF",
    CONF_PIN: "secret",
    CONF_USE_PSK: True,
}


@pytest.mark.usefixtures("mock_braviatv_client")
@pytest.mark.parametrize(
    ("unique_id", "mac", "expected_unique_id"),
    [
        ("", "AA:BB:CC:DD:EE:FF", "aa:bb:cc:dd:ee:ff"),
        ("very_unique_string", "AA:BB:CC:DD:EE:FF", "very_unique_string"),
        ("", "", ""),
    ],
)
async def test_migrate_unique_id(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    unique_id: str,
    mac: str,
    expected_unique_id: str,
) -> None:
    """Test only an entry stored without a CID gets a new unique ID."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=unique_id,
        data=ENTRY_DATA | {CONF_MAC: mac},
        version=1,
        minor_version=1,
    )
    config_entry.add_to_hass(hass)
    entity = entity_registry.async_get_or_create(
        "media_player", DOMAIN, unique_id, config_entry=config_entry
    )

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.unique_id == expected_unique_id
    assert config_entry.minor_version == 2

    migrated_entity = entity_registry.async_get(entity.entity_id)
    assert migrated_entity is not None
    assert migrated_entity.unique_id == expected_unique_id


@pytest.mark.usefixtures("mock_braviatv_client")
async def test_migration_keeps_entities_and_device(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test entities and the device move along and keep their entity IDs."""
    config_entry = MockConfigEntry(
        domain=DOMAIN, unique_id="", data=ENTRY_DATA, version=1, minor_version=1
    )
    config_entry.add_to_hass(hass)

    device = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id, identifiers={(DOMAIN, "")}
    )
    media_player = entity_registry.async_get_or_create(
        "media_player", DOMAIN, "", config_entry=config_entry, device_id=device.id
    )
    button = entity_registry.async_get_or_create(
        "button", DOMAIN, "_reboot", config_entry=config_entry, device_id=device.id
    )

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.unique_id == "aa:bb:cc:dd:ee:ff"
    assert config_entry.minor_version == 2

    migrated_media_player = entity_registry.async_get(media_player.entity_id)
    assert migrated_media_player is not None
    assert migrated_media_player.unique_id == "aa:bb:cc:dd:ee:ff"

    migrated_button = entity_registry.async_get(button.entity_id)
    assert migrated_button is not None
    assert migrated_button.unique_id == "aa:bb:cc:dd:ee:ff_reboot"

    assert device_registry.async_get(device.id).identifiers == {
        (DOMAIN, "aa:bb:cc:dd:ee:ff")
    }


async def test_ssdp_callback_triggers_refresh(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_braviatv_client: AsyncMock,
) -> None:
    """Test that an SSDP update for the TV refreshes the coordinator."""
    unsubscribe = MagicMock()
    with patch(
        "homeassistant.components.braviatv.ssdp.async_register_callback",
        return_value=unsubscribe,
    ) as mock_register:
        await init_integration(hass, mock_config_entry)

    callback, match_dict = mock_register.call_args.args[1:]
    assert match_dict == {
        "nt": "urn:schemas-upnp-org:device:MediaRenderer:1",
        "_host": "bravia-host",
    }
    assert mock_braviatv_client.get_power_status.call_count == 1

    await callback(
        SsdpServiceInfo(
            ssdp_usn="mock_usn",
            ssdp_st="mock_st",
            ssdp_location="http://bravia-host:52323/dmr.xml",
            upnp={},
        ),
        ssdp.SsdpChange.ALIVE,
    )
    freezer.tick(timedelta(seconds=2))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert mock_braviatv_client.get_power_status.call_count == 2

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    unsubscribe.assert_called_once()
