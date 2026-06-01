"""Test the Wolf SmartSet Service."""

from unittest.mock import MagicMock, patch

from httpx import RequestError
import pytest

from homeassistant.components.wolflink.const import DEVICE_ID, DOMAIN, MANUFACTURER
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from tests.common import MockConfigEntry

LEGACY_CONFIG = {
    "device_name": "test-device",
    "device_id": 1234,
    "device_gateway": 5678,
    CONF_USERNAME: "test-username",
    CONF_PASSWORD: "test-password",
}


async def test_migration_v1_1_to_v2(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> None:
    """Test migration from v1.1 (int unique_id, device-oriented) to v2 (hub-oriented)."""
    config_entry = MockConfigEntry(
        domain=DOMAIN, unique_id=1234, data=LEGACY_CONFIG, version=1, minor_version=1
    )
    config_entry.add_to_hass(hass)

    device_id = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, 1234)},
        configuration_url="https://www.wolf-smartset.com/",
        manufacturer=MANUFACTURER,
    ).id

    assert config_entry.version == 1
    assert config_entry.minor_version == 1
    assert config_entry.unique_id == 1234
    assert device_registry.async_get(device_id).identifiers == {(DOMAIN, 1234)}

    with patch(
        "homeassistant.components.wolflink.WolfClient",
        autospec=True,
    ) as wolf_mock:
        wolf_mock.return_value.fetch_system_list.side_effect = RequestError(
            "Unable to connect"
        )
        await hass.config_entries.async_setup(config_entry.entry_id)

    assert config_entry.version == 2
    assert config_entry.minor_version == 1
    assert config_entry.unique_id == "test-username"
    assert config_entry.data == {
        CONF_USERNAME: "test-username",
        CONF_PASSWORD: "test-password",
        DEVICE_ID: [1234],
    }

    assert device_registry.async_get(device_id).identifiers == {(DOMAIN, "1234")}


async def test_migration_v1_2_to_v2(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> None:
    """Test migration from v1.2 (str unique_id, device-oriented) to v2 (hub-oriented)."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="1234",
        data=LEGACY_CONFIG,
        version=1,
        minor_version=2,
    )
    config_entry.add_to_hass(hass)

    device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, "1234")},
        configuration_url="https://www.wolf-smartset.com/",
        manufacturer=MANUFACTURER,
    )

    with patch(
        "homeassistant.components.wolflink.WolfClient",
        autospec=True,
    ) as wolf_mock:
        wolf_mock.return_value.fetch_system_list.side_effect = RequestError(
            "Unable to connect"
        )
        await hass.config_entries.async_setup(config_entry.entry_id)

    assert config_entry.version == 2
    assert config_entry.minor_version == 1
    assert config_entry.unique_id == "test-username"
    assert config_entry.data == {
        CONF_USERNAME: "test-username",
        CONF_PASSWORD: "test-password",
        DEVICE_ID: [1234],
    }


async def test_migration_merges_duplicate_v1_entries(hass: HomeAssistant) -> None:
    """Test that migrating two v1 entries for the same account merges them into one v2 entry."""
    first_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="1234",
        data={**LEGACY_CONFIG, "device_id": 1234},
        version=1,
        minor_version=2,
    )
    second_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="5678",
        data={**LEGACY_CONFIG, "device_id": 5678},
        version=1,
        minor_version=2,
    )
    first_entry.add_to_hass(hass)
    second_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.wolflink.WolfClient",
        autospec=True,
    ) as wolf_mock:
        wolf_mock.return_value.fetch_system_list.side_effect = RequestError(
            "Unable to connect"
        )
        # Migrate the first entry — becomes the v2 hub entry.
        await hass.config_entries.async_setup(first_entry.entry_id)
        # Migrate the second entry — should merge into the first and be removed.
        await second_entry.async_migrate(hass)
        await hass.async_block_till_done()

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    surviving = entries[0]
    assert surviving.entry_id == first_entry.entry_id
    assert surviving.unique_id == "test-username"
    assert surviving.version == 2
    assert surviving.minor_version == 1
    assert sorted(surviving.data[DEVICE_ID]) == [1234, 5678]


@pytest.mark.parametrize(
    "stored_ids",
    [
        pytest.param([1234, 5678], id="list_of_int"),
        pytest.param(["1234", "5678"], id="list_of_str"),
    ],
)
async def test_migration_v1_with_list_device_id(
    hass: HomeAssistant, stored_ids: list[int] | list[str]
) -> None:
    """Test v1 migration tolerates DEVICE_ID stored as a list of int or str."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="1234",
        data={**LEGACY_CONFIG, "device_id": stored_ids},
        version=1,
        minor_version=2,
    )
    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.wolflink.WolfClient",
        autospec=True,
    ) as wolf_mock:
        wolf_mock.return_value.fetch_system_list.side_effect = RequestError(
            "Unable to connect"
        )
        await hass.config_entries.async_setup(config_entry.entry_id)

    assert config_entry.version == 2
    assert config_entry.minor_version == 1
    assert config_entry.unique_id == "test-username"
    assert sorted(config_entry.data[DEVICE_ID]) == [1234, 5678]


async def test_setup_no_devices_on_account(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test setup raises ConfigEntryNotReady if the account has no devices."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.wolflink.WolfClient",
        autospec=True,
    ) as wolf_mock:
        wolf_mock.return_value.fetch_system_list.return_value = []
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_migrate_future_version_aborts(hass: HomeAssistant) -> None:
    """Test migration refuses to downgrade a future-version entry."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="test-username",
        data={
            CONF_USERNAME: "test-username",
            CONF_PASSWORD: "test-password",
            DEVICE_ID: [1234],
        },
        version=3,
        minor_version=1,
    )
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.MIGRATION_ERROR


async def test_setup_fetch_parameters_fails(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_wolflink: MagicMock,
) -> None:
    """Test setup raises ConfigEntryNotReady if fetching parameters fails."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.wolflink.fetch_parameters",
        side_effect=RequestError("Unable to fetch parameters"),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_selected_devices_missing(
    hass: HomeAssistant, mock_wolflink: MagicMock
) -> None:
    """Test setup fails when none of the selected devices exist on the account."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="test-username",
        data={
            CONF_USERNAME: "test-username",
            CONF_PASSWORD: "test-password",
            DEVICE_ID: [9999],
        },
        version=2,
        minor_version=1,
    )
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.SETUP_ERROR
