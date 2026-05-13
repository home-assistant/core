"""Test HomematicIP Cloud setup process."""

from unittest.mock import AsyncMock, Mock, patch

from homematicip.exceptions.connection_exceptions import HmipConnectionError
import pytest

from homeassistant.components.homematicip_cloud.const import (
    CONF_ACCESSPOINT,
    CONF_AUTHTOKEN,
    DOMAIN,
    HMIPC_AUTHTOKEN,
    HMIPC_HAPID,
    HMIPC_NAME,
)
from homeassistant.components.homematicip_cloud.hap import HomematicipHAP
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry


async def test_config_with_accesspoint_passed_to_config_entry(
    hass: HomeAssistant, mock_connection, simple_mock_home
) -> None:
    """Test that config for a accesspoint are loaded via config entry."""

    entry_config = {
        CONF_ACCESSPOINT: "ABC123",
        CONF_AUTHTOKEN: "123",
        CONF_NAME: "name",
    }
    # no config_entry exists
    assert len(hass.config_entries.async_entries(DOMAIN)) == 0

    with patch(
        "homeassistant.components.homematicip_cloud.hap.HomematicipHAP.async_connect",
    ):
        assert await async_setup_component(hass, DOMAIN, {DOMAIN: entry_config})

    # config_entry created for access point
    config_entries = hass.config_entries.async_entries(DOMAIN)
    assert len(config_entries) == 1
    assert config_entries[0].data == {
        "authtoken": "123",
        "hapid": "ABC123",
        "name": "name",
    }
    # defined access_point created for config_entry
    assert isinstance(config_entries[0].runtime_data, HomematicipHAP)


async def test_config_already_registered_not_passed_to_config_entry(
    hass: HomeAssistant, simple_mock_home
) -> None:
    """Test that an already registered accesspoint does not get imported."""

    mock_config = {HMIPC_AUTHTOKEN: "123", HMIPC_HAPID: "ABC123", HMIPC_NAME: "name"}
    MockConfigEntry(domain=DOMAIN, data=mock_config).add_to_hass(hass)

    # one config_entry exists
    config_entries = hass.config_entries.async_entries(DOMAIN)
    assert len(config_entries) == 1
    assert config_entries[0].data == {
        "authtoken": "123",
        "hapid": "ABC123",
        "name": "name",
    }
    # config_enty has no unique_id
    assert not config_entries[0].unique_id

    entry_config = {
        CONF_ACCESSPOINT: "ABC123",
        CONF_AUTHTOKEN: "123",
        CONF_NAME: "name",
    }

    with patch(
        "homeassistant.components.homematicip_cloud.hap.HomematicipHAP.async_connect",
    ):
        assert await async_setup_component(hass, DOMAIN, {DOMAIN: entry_config})

    # no new config_entry created / still one config_entry
    config_entries = hass.config_entries.async_entries(DOMAIN)
    assert len(config_entries) == 1
    assert config_entries[0].data == {
        "authtoken": "123",
        "hapid": "ABC123",
        "name": "name",
    }
    # config_enty updated with unique_id
    assert config_entries[0].unique_id == "ABC123"


async def test_load_entry_fails_due_to_connection_error(
    hass: HomeAssistant, hmip_config_entry: MockConfigEntry, mock_connection_init
) -> None:
    """Test load entry fails due to connection error."""
    hmip_config_entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.homematicip_cloud.hap.AsyncHome.get_current_state_async",
            side_effect=HmipConnectionError,
        ),
        patch(
            "homeassistant.components.homematicip_cloud.hap.ConnectionContextBuilder.build_context_async",
        ),
    ):
        assert await async_setup_component(hass, DOMAIN, {})

    assert hmip_config_entry.runtime_data
    assert hmip_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_load_entry_fails_due_to_generic_exception(
    hass: HomeAssistant, hmip_config_entry: MockConfigEntry
) -> None:
    """Test load entry fails due to generic exception."""
    hmip_config_entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.homematicip_cloud.hap.AsyncHome.get_current_state_async",
            side_effect=Exception,
        ),
        patch(
            "homeassistant.components.homematicip_cloud.hap.ConnectionContextBuilder.build_context_async",
        ),
    ):
        assert await async_setup_component(hass, DOMAIN, {})

    assert hmip_config_entry.runtime_data
    assert hmip_config_entry.state is ConfigEntryState.SETUP_ERROR


async def test_unload_entry(hass: HomeAssistant) -> None:
    """Test being able to unload an entry."""
    mock_config = {HMIPC_AUTHTOKEN: "123", HMIPC_HAPID: "ABC123", HMIPC_NAME: "name"}
    MockConfigEntry(domain=DOMAIN, data=mock_config).add_to_hass(hass)

    with patch("homeassistant.components.homematicip_cloud.HomematicipHAP") as mock_hap:
        instance = mock_hap.return_value
        instance.async_setup = AsyncMock(return_value=True)
        instance.home.id = "1"
        instance.home.modelType = "mock-type"
        instance.home.name = "mock-name"
        instance.home.label = "mock-label"
        instance.home.currentAPVersion = "mock-ap-version"
        instance.async_reset = AsyncMock(return_value=True)

        assert await async_setup_component(hass, DOMAIN, {})

    assert mock_hap.return_value.mock_calls[0][0] == "async_setup"

    config_entries = hass.config_entries.async_entries(DOMAIN)
    assert len(config_entries) == 1
    assert config_entries[0].runtime_data
    assert config_entries[0].state is ConfigEntryState.LOADED
    await hass.config_entries.async_unload(config_entries[0].entry_id)
    assert config_entries[0].state is ConfigEntryState.NOT_LOADED


async def test_hmip_dump_hap_config_services(
    hass: HomeAssistant, mock_hap_with_service
) -> None:
    """Test dump configuration services."""

    with patch("pathlib.Path.write_text", return_value=Mock()) as write_mock:
        await hass.services.async_call(
            "homematicip_cloud", "dump_hap_config", {"anonymize": True}, blocking=True
        )
        home = mock_hap_with_service.home
        assert home.mock_calls[-1][0] == "download_configuration_async"
        assert home.mock_calls
        assert write_mock.mock_calls


async def test_setup_services(hass: HomeAssistant) -> None:
    """Test setup services."""
    mock_config = {HMIPC_AUTHTOKEN: "123", HMIPC_HAPID: "ABC123", HMIPC_NAME: "name"}
    MockConfigEntry(domain=DOMAIN, data=mock_config).add_to_hass(hass)

    with patch("homeassistant.components.homematicip_cloud.HomematicipHAP") as mock_hap:
        instance = mock_hap.return_value
        instance.async_setup = AsyncMock(return_value=True)
        instance.home.id = "1"
        instance.home.modelType = "mock-type"
        instance.home.name = "mock-name"
        instance.home.label = "mock-label"
        instance.home.currentAPVersion = "mock-ap-version"
        instance.async_reset = AsyncMock(return_value=True)

        assert await async_setup_component(hass, DOMAIN, {})

    # Check services are created
    hmipc_services = hass.services.async_services()[DOMAIN]
    assert len(hmipc_services) == 9

    config_entries = hass.config_entries.async_entries(DOMAIN)
    assert len(config_entries) == 1

    await hass.config_entries.async_unload(config_entries[0].entry_id)


# --- Unique ID migration tests ---


@pytest.fixture
def mock_config_entry_v1(hass: HomeAssistant) -> MockConfigEntry:
    """Create a v1 config entry for migration testing."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={HMIPC_HAPID: "ABC123", HMIPC_AUTHTOKEN: "token", HMIPC_NAME: ""},
        version=1,
    )
    entry.add_to_hass(hass)
    return entry


@pytest.mark.parametrize(
    ("platform", "old_unique_id", "new_unique_id"),
    [
        (
            "binary_sensor",
            "HomematicipMotionDetector_3014F711ABCD",
            "3014F711ABCD_1_motion",
        ),
        (
            "switch",
            "HomematicipMultiSwitch_Channel3_3014F711ABCD",
            "3014F711ABCD_3_switch",
        ),
        (
            "light",
            "HomematicipNotificationLight_Top_3014F711ABCD",
            "3014F711ABCD_2_notification_light",
        ),
        ("climate", "HomematicipHeatingGroup_UUID-GROUP-123", "UUID-GROUP-123_climate"),
    ],
    ids=["single_channel", "multi_channel", "notification_light", "group"],
)
async def test_migrate_unique_id(
    hass: HomeAssistant,
    mock_config_entry_v1: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    platform: str,
    old_unique_id: str,
    new_unique_id: str,
) -> None:
    """Test unique_id migration for different entity types."""
    entity_registry.async_get_or_create(
        platform,
        DOMAIN,
        old_unique_id,
        config_entry=mock_config_entry_v1,
    )

    with patch("homeassistant.components.homematicip_cloud.HomematicipHAP") as mock_hap:
        instance = mock_hap.return_value
        instance.async_setup = AsyncMock(return_value=True)
        instance.home.id = "1"
        instance.home.modelType = "mock-type"
        instance.home.name = "mock-name"
        instance.home.label = "mock-label"
        instance.home.currentAPVersion = "mock-ap-version"
        instance.async_reset = AsyncMock(return_value=True)

        await hass.config_entries.async_setup(mock_config_entry_v1.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry_v1.version == 2
    assert entity_registry.async_get_entity_id(platform, DOMAIN, new_unique_id)


async def test_migrate_stable_unique_id_skipped(
    hass: HomeAssistant,
    mock_config_entry_v1: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that a non-class-name unique_id is silently skipped and preserved."""
    entity_registry.async_get_or_create(
        "sensor",
        DOMAIN,
        "HomematicipFutureEntity_3014F711ABCD",
        config_entry=mock_config_entry_v1,
    )

    with patch("homeassistant.components.homematicip_cloud.HomematicipHAP") as mock_hap:
        instance = mock_hap.return_value
        instance.async_setup = AsyncMock(return_value=True)
        instance.home.id = "1"
        instance.home.modelType = "mock-type"
        instance.home.name = "mock-name"
        instance.home.label = "mock-label"
        instance.home.currentAPVersion = "mock-ap-version"
        instance.async_reset = AsyncMock(return_value=True)

        await hass.config_entries.async_setup(mock_config_entry_v1.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry_v1.version == 2
    # Unknown prefix is not a known class name, so it's treated as already
    # stable and skipped silently (no warning, just debug).
    assert "already stable format" in caplog.text
    # Old unique_id is preserved (not migrated)
    assert entity_registry.async_get_entity_id(
        "sensor", DOMAIN, "HomematicipFutureEntity_3014F711ABCD"
    )


async def test_migrate_battery_and_obsolete_access_point(
    hass: HomeAssistant,
    mock_config_entry_v1: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test battery migration and obsolete access point entity removal."""

    # Obsolete access point battery entity: legacy unique_id, no linked device.
    obsolete_entity_id = entity_registry.async_get_or_create(
        "binary_sensor",
        DOMAIN,
        "HomematicipBatterySensor_ABC123",
        config_entry=mock_config_entry_v1,
    ).entity_id

    # Real device battery entity: same legacy class prefix, but attached to a device.
    device_entry = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry_v1.entry_id,
        identifiers={(DOMAIN, "3014F711ABCD")},
    )
    entity_registry.async_get_or_create(
        "binary_sensor",
        DOMAIN,
        "HomematicipBatterySensor_3014F711ABCD",
        config_entry=mock_config_entry_v1,
        device_id=device_entry.id,
    )

    with patch("homeassistant.components.homematicip_cloud.HomematicipHAP") as mock_hap:
        instance = mock_hap.return_value
        instance.async_setup = AsyncMock(return_value=True)
        instance.home.id = "1"
        instance.home.modelType = "mock-type"
        instance.home.name = "mock-name"
        instance.home.label = "mock-label"
        instance.home.currentAPVersion = "mock-ap-version"
        instance.async_reset = AsyncMock(return_value=True)

        await hass.config_entries.async_setup(mock_config_entry_v1.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry_v1.version == 2
    # Obsolete access point battery entity removed
    assert entity_registry.async_get(obsolete_entity_id) is None
    # Real device battery entity migrated
    assert entity_registry.async_get_entity_id(
        "binary_sensor", DOMAIN, "3014F711ABCD_0_battery"
    )
