"""Test the Wolf SmartSet Service."""

from unittest.mock import MagicMock, patch

from httpx import RequestError
from wolf_comm.models import Device
from wolf_comm.token_auth import InvalidAuth
from wolf_comm.wolf_client import FetchFailed

from homeassistant.components.wolflink import async_migrate_entry
from homeassistant.components.wolflink.const import CONF_DEVICES, DOMAIN, MANUFACTURER
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .const import CONFIG

from tests.common import MockConfigEntry


async def test_unique_id_migration(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> None:
    """Test migration from version 1.1 (int unique_id) through to version 2.1."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=1234,
        data={
            CONF_USERNAME: CONFIG[CONF_USERNAME],
            CONF_PASSWORD: CONFIG[CONF_PASSWORD],
            "device_name": "test-device",
            "device_gateway": 5678,
            "device_id": 1234,
        },
        version=1,
        minor_version=1,
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

    with (
        patch(
            "homeassistant.components.wolflink.WolfClient", autospec=True
        ) as wolflink_mock,
    ):
        wolflink_mock.return_value.fetch_system_list.side_effect = RequestError(
            "Unable to fetch system list"
        )
        await hass.config_entries.async_setup(config_entry.entry_id)

    assert config_entry.version == 2
    assert config_entry.minor_version == 1
    assert config_entry.unique_id == CONFIG[CONF_USERNAME].lower()
    assert config_entry.data == {
        CONF_USERNAME: CONFIG[CONF_USERNAME],
        CONF_PASSWORD: CONFIG[CONF_PASSWORD],
    }
    # Device identifiers should have been converted to strings during migration
    assert device_registry.async_get(device_id).identifiers == {(DOMAIN, "1234")}
    # The old device_id should have been preserved in options
    assert config_entry.options == {CONF_DEVICES: ["1234"]}


async def test_migration_v1_2_to_v2(
    hass: HomeAssistant,
) -> None:
    """Test migration from version 1.2 (string device_id unique_id) to version 2.1."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="1234",
        data={
            CONF_USERNAME: CONFIG[CONF_USERNAME],
            CONF_PASSWORD: CONFIG[CONF_PASSWORD],
            "device_name": "test-device",
            "device_gateway": 5678,
            "device_id": 1234,
        },
        version=1,
        minor_version=2,
    )
    config_entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.wolflink.WolfClient", autospec=True
        ) as wolflink_mock,
    ):
        wolflink_mock.return_value.fetch_system_list.side_effect = RequestError(
            "Unable to fetch system list"
        )
        await hass.config_entries.async_setup(config_entry.entry_id)

    assert config_entry.version == 2
    assert config_entry.minor_version == 1
    assert config_entry.unique_id == CONFIG[CONF_USERNAME].lower()
    assert config_entry.data == {
        CONF_USERNAME: CONFIG[CONF_USERNAME],
        CONF_PASSWORD: CONFIG[CONF_PASSWORD],
    }
    # The old device_id should have been preserved in options
    assert config_entry.options == {CONF_DEVICES: ["1234"]}


async def test_migration_v1_no_device_id(
    hass: HomeAssistant,
) -> None:
    """Test migration from version 1.x without a device_id leaves options unchanged."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="1234",
        data={
            CONF_USERNAME: CONFIG[CONF_USERNAME],
            CONF_PASSWORD: CONFIG[CONF_PASSWORD],
            # no device_id key
        },
        version=1,
        minor_version=2,
    )
    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.wolflink.WolfClient", autospec=True
    ) as wolflink_mock:
        wolflink_mock.return_value.fetch_system_list.side_effect = RequestError(
            "Unable to fetch system list"
        )
        await hass.config_entries.async_setup(config_entry.entry_id)

    assert config_entry.version == 2
    assert config_entry.options == {}


async def test_migration_duplicate_entries(
    hass: HomeAssistant,
) -> None:
    """Test that duplicate v1 entries for the same account collapse to one v2 entry."""
    entry_a = MockConfigEntry(
        domain=DOMAIN,
        unique_id="1234",
        data={
            CONF_USERNAME: CONFIG[CONF_USERNAME],
            CONF_PASSWORD: CONFIG[CONF_PASSWORD],
            "device_name": "device-a",
            "device_gateway": 5678,
            "device_id": 1234,
        },
        version=1,
        minor_version=2,
    )
    entry_b = MockConfigEntry(
        domain=DOMAIN,
        unique_id="9999",
        data={
            CONF_USERNAME: CONFIG[CONF_USERNAME],
            CONF_PASSWORD: CONFIG[CONF_PASSWORD],
            "device_name": "device-b",
            "device_gateway": 5678,
            "device_id": 9999,
        },
        version=1,
        minor_version=2,
    )
    entry_a.add_to_hass(hass)
    entry_b.add_to_hass(hass)

    result_a = await async_migrate_entry(hass, entry_a)
    result_b = await async_migrate_entry(hass, entry_b)

    assert result_a is True
    assert entry_a.version == 2
    assert entry_a.unique_id == CONFIG[CONF_USERNAME].lower()
    assert result_b is False
    # entry_b's device_id (9999) should have been merged into entry_a's options
    assert set(entry_a.options.get(CONF_DEVICES, [])) == {"1234", "9999"}


async def test_setup_multi_device(
    hass: HomeAssistant,
    mock_wolflink: MagicMock,
) -> None:
    """Test that all selected devices from options are set up."""
    mock_wolflink.fetch_system_list.return_value = [
        Device(1234, 5678, "device-a"),
        Device(9999, 5678, "device-b"),
    ]

    config_entry = MockConfigEntry(
        title="test-username",
        domain=DOMAIN,
        data={
            CONF_USERNAME: CONFIG[CONF_USERNAME],
            CONF_PASSWORD: CONFIG[CONF_PASSWORD],
        },
        options={
            CONF_DEVICES: ["1234", "9999"],
        },
        unique_id=CONFIG[CONF_USERNAME].lower(),
        version=2,
        minor_version=1,
    )
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert len(config_entry.runtime_data.coordinators) == 2
    device_names = {c.device_name for c in config_entry.runtime_data.coordinators}
    assert device_names == {"device-a", "device-b"}


async def test_setup_filters_unselected_device(
    hass: HomeAssistant,
    mock_wolflink: MagicMock,
) -> None:
    """Test that devices not in options[CONF_DEVICES] are skipped."""
    mock_wolflink.fetch_system_list.return_value = [
        Device(1234, 5678, "device-a"),
        Device(9999, 5678, "device-b"),
    ]

    config_entry = MockConfigEntry(
        title="test-username",
        domain=DOMAIN,
        data={
            CONF_USERNAME: CONFIG[CONF_USERNAME],
            CONF_PASSWORD: CONFIG[CONF_PASSWORD],
        },
        options={
            CONF_DEVICES: ["1234"],  # only device-a selected
        },
        unique_id=CONFIG[CONF_USERNAME].lower(),
        version=2,
        minor_version=1,
    )
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert len(config_entry.runtime_data.coordinators) == 1
    assert config_entry.runtime_data.coordinators[0].device_name == "device-a"


async def test_setup_entry_invalid_auth(
    hass: HomeAssistant,
    mock_wolflink: MagicMock,
) -> None:
    """Test setup raises ConfigEntryAuthFailed when fetch_system_list raises InvalidAuth."""
    mock_wolflink.fetch_system_list.side_effect = InvalidAuth

    config_entry = MockConfigEntry(
        title="test-username",
        domain=DOMAIN,
        data={
            CONF_USERNAME: CONFIG[CONF_USERNAME],
            CONF_PASSWORD: CONFIG[CONF_PASSWORD],
        },
        options={CONF_DEVICES: ["1234"]},
        unique_id=CONFIG[CONF_USERNAME].lower(),
        version=2,
        minor_version=1,
    )
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.SETUP_ERROR


async def test_setup_entry_fetch_failed(
    hass: HomeAssistant,
    mock_wolflink: MagicMock,
) -> None:
    """Test setup raises ConfigEntryNotReady when fetch_system_list raises FetchFailed."""
    mock_wolflink.fetch_system_list.side_effect = FetchFailed("error")

    config_entry = MockConfigEntry(
        title="test-username",
        domain=DOMAIN,
        data={
            CONF_USERNAME: CONFIG[CONF_USERNAME],
            CONF_PASSWORD: CONFIG[CONF_PASSWORD],
        },
        options={CONF_DEVICES: ["1234"]},
        unique_id=CONFIG[CONF_USERNAME].lower(),
        version=2,
        minor_version=1,
    )
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_entry_fetch_parameters_invalid_auth(
    hass: HomeAssistant,
    mock_wolflink: MagicMock,
) -> None:
    """Test setup raises ConfigEntryAuthFailed when fetch_parameters raises InvalidAuth."""
    mock_wolflink.fetch_system_list.return_value = [Device(1234, 5678, "device-a")]

    config_entry = MockConfigEntry(
        title="test-username",
        domain=DOMAIN,
        data={
            CONF_USERNAME: CONFIG[CONF_USERNAME],
            CONF_PASSWORD: CONFIG[CONF_PASSWORD],
        },
        options={CONF_DEVICES: ["1234"]},
        unique_id=CONFIG[CONF_USERNAME].lower(),
        version=2,
        minor_version=1,
    )
    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.wolflink.fetch_parameters",
        side_effect=InvalidAuth,
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.SETUP_ERROR


async def test_setup_entry_fetch_parameters_fetch_failed(
    hass: HomeAssistant,
    mock_wolflink: MagicMock,
) -> None:
    """Test setup raises ConfigEntryNotReady when fetch_parameters raises FetchFailed."""
    mock_wolflink.fetch_system_list.return_value = [Device(1234, 5678, "device-a")]

    config_entry = MockConfigEntry(
        title="test-username",
        domain=DOMAIN,
        data={
            CONF_USERNAME: CONFIG[CONF_USERNAME],
            CONF_PASSWORD: CONFIG[CONF_PASSWORD],
        },
        options={CONF_DEVICES: ["1234"]},
        unique_id=CONFIG[CONF_USERNAME].lower(),
        version=2,
        minor_version=1,
    )
    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.wolflink.fetch_parameters",
        side_effect=FetchFailed("error"),
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_unload_entry(
    hass: HomeAssistant,
    mock_wolflink: MagicMock,
) -> None:
    """Test that unloading an entry succeeds."""
    config_entry = MockConfigEntry(
        title="test-username",
        domain=DOMAIN,
        data={
            CONF_USERNAME: CONFIG[CONF_USERNAME],
            CONF_PASSWORD: CONFIG[CONF_PASSWORD],
        },
        options={CONF_DEVICES: ["1234"]},
        unique_id=CONFIG[CONF_USERNAME].lower(),
        version=2,
        minor_version=1,
    )
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.NOT_LOADED
