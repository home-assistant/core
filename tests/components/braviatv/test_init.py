"""Test the Bravia TV integration setup."""

from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
from pybravia import (
    BraviaAuthError,
    BraviaConnectionError,
    BraviaConnectionTimeout,
    BraviaError,
    BraviaNotFound,
    BraviaTurnedOff,
)
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed

from homeassistant.components import ssdp
from homeassistant.components.braviatv.const import (
    CONF_NICKNAME,
    CONF_USE_PSK,
    DOMAIN,
    LEGACY_CLIENT_ID,
    NICKNAME_PREFIX,
)
from homeassistant.components.braviatv.coordinator import SCAN_INTERVAL
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.const import (
    CONF_CLIENT_ID,
    CONF_HOST,
    CONF_MAC,
    CONF_PIN,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.service_info.ssdp import SsdpServiceInfo
from homeassistant.helpers.update_coordinator import UpdateFailed

from . import init_integration

ENTRY_DATA = {
    CONF_HOST: "bravia-host",
    CONF_MAC: "AA:BB:CC:DD:EE:FF",
    CONF_PIN: "secret",
    CONF_USE_PSK: True,
}

ENTITY_ID = "media_player.bravia_tv_model"


async def tick_update(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    """Advance time to trigger the next coordinator update."""
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()


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


async def test_setup_auth_error_starts_reauth(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_braviatv_client: AsyncMock,
) -> None:
    """Test an authentication error during setup starts a reauth flow."""
    mock_braviatv_client.connect.side_effect = BraviaAuthError
    mock_config_entry.add_to_hass(hass)

    assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
    flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert len(flows) == 1
    assert flows[0]["context"]["source"] == SOURCE_REAUTH
    assert flows[0]["context"]["entry_id"] == mock_config_entry.entry_id


@pytest.mark.parametrize(
    ("entry_data", "connect_kwargs"),
    [
        (ENTRY_DATA, {"psk": "secret"}),
        (
            {
                **ENTRY_DATA,
                CONF_USE_PSK: False,
                CONF_CLIENT_ID: "client-id",
                CONF_NICKNAME: "Home Assistant (test)",
            },
            {
                "pin": "secret",
                "clientid": "client-id",
                "nickname": "Home Assistant (test)",
            },
        ),
        (
            {
                CONF_HOST: "bravia-host",
                CONF_MAC: "AA:BB:CC:DD:EE:FF",
                CONF_PIN: "secret",
            },
            {
                "pin": "secret",
                "clientid": LEGACY_CLIENT_ID,
                "nickname": NICKNAME_PREFIX,
            },
        ),
    ],
)
async def test_connect(
    hass: HomeAssistant,
    mock_braviatv_client: AsyncMock,
    entry_data: dict[str, str | bool],
    connect_kwargs: dict[str, str],
) -> None:
    """Test the TV is connected with a PSK or with PIN credentials."""
    config_entry = MockConfigEntry(
        domain=DOMAIN, unique_id="very_unique_string", data=entry_data, minor_version=2
    )

    await init_integration(hass, config_entry)

    mock_braviatv_client.connect.assert_called_once_with(**connect_kwargs)


@pytest.mark.parametrize(
    ("exception", "expected_state"),
    [
        (BraviaNotFound, STATE_ON),
        (BraviaConnectionError, STATE_OFF),
        (BraviaConnectionTimeout, STATE_OFF),
        (BraviaTurnedOff, STATE_OFF),
        (BraviaError, STATE_UNAVAILABLE),
    ],
)
async def test_update_error_reconnects(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_braviatv_client: AsyncMock,
    exception: type[BraviaError],
    expected_state: str,
) -> None:
    """Test a failed update reconnects the TV on the next successful update."""
    await init_integration(hass, mock_config_entry)
    assert hass.states.get(ENTITY_ID).state == STATE_ON

    mock_braviatv_client.get_power_status.side_effect = exception
    await tick_update(hass, freezer)

    assert hass.states.get(ENTITY_ID).state == expected_state

    mock_braviatv_client.get_power_status.side_effect = None
    await tick_update(hass, freezer)

    assert hass.states.get(ENTITY_ID).state == STATE_ON
    assert mock_braviatv_client.connect.call_count == 2


@pytest.mark.parametrize(
    ("exception", "skipped_updates", "translation_key", "placeholders"),
    [
        (
            BraviaNotFound,
            10,
            "update_error_not_found",
            {"device": "BRAVIA TV-Model"},
        ),
        (
            BraviaError,
            0,
            "update_error",
            {"device": "BRAVIA TV-Model", "error": "BraviaError()"},
        ),
    ],
)
async def test_update_failed(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_braviatv_client: AsyncMock,
    exception: type[BraviaError],
    skipped_updates: int,
    translation_key: str,
    placeholders: dict[str, str],
) -> None:
    """Test the entity becomes unavailable once an update fails."""
    await init_integration(hass, mock_config_entry)

    mock_braviatv_client.get_power_status.side_effect = exception
    # Updates failing because the API is reloading are skipped up to ten times
    for _ in range(skipped_updates):
        await tick_update(hass, freezer)
    assert hass.states.get(ENTITY_ID).state == STATE_ON

    await tick_update(hass, freezer)

    assert hass.states.get(ENTITY_ID).state == STATE_UNAVAILABLE
    error = mock_config_entry.runtime_data.last_exception
    assert isinstance(error, UpdateFailed)
    assert error.translation_key == translation_key
    assert error.translation_placeholders == placeholders
