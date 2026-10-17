"""Linksys Smart Wi-Fi device tracker platform tests."""

from datetime import timedelta
from unittest.mock import AsyncMock, patch

from jnap import (
    GetDeviceInfoResponse,
    GetDevicesResponse,
    JNAPClient,
    JNAPDevice,
    JNAPError,
    JNAPUnauthorizedError,
)
import pytest

from homeassistant.components.device_tracker import legacy
from homeassistant.components.linksys_smart import config_flow as linksys_config_flow
from homeassistant.components.linksys_smart.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_HOST, CONF_PASSWORD
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.helpers import entity_registry as er, issue_registry as ir
from homeassistant.setup import async_setup_component
from homeassistant.util.dt import utcnow

from .conftest import SERIAL

from tests.common import MockConfigEntry, async_fire_time_changed

UPDATE_INTERVAL = timedelta(seconds=31)

LAPTOP = JNAPDevice(
    mac="aa:bb:cc:dd:ee:ff",
    name="My Laptop",
    ip_address="192.168.1.10",
    hostname="my-laptop",
)
PHONE = JNAPDevice(
    mac="11:22:33:44:55:66",
    name="My Phone",
    ip_address="192.168.1.11",
    hostname="my-phone",
)


async def _setup_entry(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    initial_devices: list[JNAPDevice] | None = None,
) -> AsyncMock:
    """Set up a config entry with a mocked JNAPClient, return the mock client."""
    mock_client = AsyncMock(spec=JNAPClient)
    mock_client.get_devices.return_value = GetDevicesResponse(
        devices=initial_devices or []
    )
    entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.linksys_smart.util.JNAPClient",
        return_value=mock_client,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return mock_client


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_entity_state_when_connected(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test entity state and attributes when device is connected."""
    entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_HOST: "192.168.1.1", CONF_PASSWORD: "pass"}
    )
    await _setup_entry(hass, entry, [LAPTOP])

    entity_id = entity_registry.async_get_entity_id(
        "device_tracker", DOMAIN, f"{entry.entry_id}_aa:bb:cc:dd:ee:ff"
    )
    assert entity_id is not None
    reg_entry = entity_registry.async_get(entity_id)
    assert reg_entry is not None
    assert reg_entry.unique_id == f"{entry.entry_id}_aa:bb:cc:dd:ee:ff"

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "home"
    assert state.attributes["source_type"] == "router"
    assert state.attributes["ip"] == "192.168.1.10"
    assert state.attributes["host_name"] == "my-laptop"
    assert state.attributes["mac"] == "aa:bb:cc:dd:ee:ff"


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_entity_state_when_disconnected(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test entity state when device is not present in coordinator data."""
    entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_HOST: "192.168.1.1", CONF_PASSWORD: "pass"}
    )
    mock_client = await _setup_entry(hass, entry, [LAPTOP])

    mock_client.get_devices.return_value = GetDevicesResponse(devices=[])
    async_fire_time_changed(hass, utcnow() + UPDATE_INTERVAL)
    await hass.async_block_till_done()

    entity_id = entity_registry.async_get_entity_id(
        "device_tracker", DOMAIN, f"{entry.entry_id}_aa:bb:cc:dd:ee:ff"
    )
    assert entity_id is not None
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "not_home"
    assert "ip" not in state.attributes
    assert "host_name" not in state.attributes


async def test_setup_entry_creates_entity_per_device(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test async_setup_entry adds one entity per device in coordinator data."""
    entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_HOST: "192.168.1.1", CONF_PASSWORD: "pass"}
    )
    await _setup_entry(hass, entry, [LAPTOP, PHONE])

    entries = er.async_entries_for_config_entry(entity_registry, entry.entry_id)
    assert len(entries) == 2
    assert {entity.unique_id for entity in entries} == {
        f"{entry.entry_id}_aa:bb:cc:dd:ee:ff",
        f"{entry.entry_id}_11:22:33:44:55:66",
    }


async def test_setup_entry_does_not_duplicate_on_coordinator_update(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test that existing devices are not re-added when coordinator refreshes."""
    entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_HOST: "192.168.1.1", CONF_PASSWORD: "pass"}
    )
    await _setup_entry(hass, entry, [LAPTOP])

    entries = er.async_entries_for_config_entry(entity_registry, entry.entry_id)
    assert len(entries) == 1

    async_fire_time_changed(hass, utcnow() + UPDATE_INTERVAL)
    await hass.async_block_till_done()

    entries = er.async_entries_for_config_entry(entity_registry, entry.entry_id)
    assert len(entries) == 1


async def test_new_device_added_on_coordinator_update(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test that a new entity is added when a new device appears in coordinator data."""
    entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_HOST: "192.168.1.1", CONF_PASSWORD: "pass"}
    )
    mock_client = await _setup_entry(hass, entry, [LAPTOP])

    entries = er.async_entries_for_config_entry(entity_registry, entry.entry_id)
    assert len(entries) == 1

    mock_client.get_devices.return_value = GetDevicesResponse(devices=[LAPTOP, PHONE])
    async_fire_time_changed(hass, utcnow() + UPDATE_INTERVAL)
    await hass.async_block_till_done()

    entries = er.async_entries_for_config_entry(entity_registry, entry.entry_id)
    assert len(entries) == 2
    assert {entity.unique_id for entity in entries} == {
        f"{entry.entry_id}_aa:bb:cc:dd:ee:ff",
        f"{entry.entry_id}_11:22:33:44:55:66",
    }


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_entity_name_updates_on_coordinator_refresh(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that a router-side rename is reflected after a coordinator refresh."""
    entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_HOST: "192.168.1.1", CONF_PASSWORD: "pass"}
    )
    mock_client = await _setup_entry(hass, entry, [LAPTOP])

    entity_id = entity_registry.async_get_entity_id(
        "device_tracker", DOMAIN, f"{entry.entry_id}_aa:bb:cc:dd:ee:ff"
    )
    assert entity_id is not None
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.attributes["friendly_name"] == "My Laptop"

    renamed_laptop = JNAPDevice(
        mac="aa:bb:cc:dd:ee:ff",
        name="Someone's Laptop",
        ip_address="192.168.1.10",
        hostname="my-laptop",
    )
    mock_client.get_devices.return_value = GetDevicesResponse(devices=[renamed_laptop])
    async_fire_time_changed(hass, utcnow() + UPDATE_INTERVAL)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.attributes["friendly_name"] == "Someone's Laptop"


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_restored_entity_name_updates_once_reconnected(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test a restored entity picks up the router's name once the device reconnects."""
    entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_HOST: "192.168.1.1", CONF_PASSWORD: "pass"}
    )
    await _setup_entry(hass, entry, [LAPTOP])
    await hass.config_entries.async_unload(entry.entry_id)

    mock_client = AsyncMock(spec=JNAPClient)
    mock_client.get_devices.return_value = GetDevicesResponse(devices=[])
    with patch(
        "homeassistant.components.linksys_smart.util.JNAPClient",
        return_value=mock_client,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    entity_id = entity_registry.async_get_entity_id(
        "device_tracker", DOMAIN, f"{entry.entry_id}_aa:bb:cc:dd:ee:ff"
    )
    assert entity_id is not None
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.attributes["friendly_name"] == "My Laptop"

    renamed_laptop = JNAPDevice(
        mac="aa:bb:cc:dd:ee:ff",
        name="Someone's Laptop",
        ip_address="192.168.1.10",
        hostname="my-laptop",
    )
    mock_client.get_devices.return_value = GetDevicesResponse(devices=[renamed_laptop])
    async_fire_time_changed(hass, utcnow() + UPDATE_INTERVAL)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.attributes["friendly_name"] == "Someone's Laptop"


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_entity_restored_when_offline_at_startup(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test that a device known to the registry is restored even if offline at startup."""
    entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_HOST: "192.168.1.1", CONF_PASSWORD: "pass"}
    )
    await _setup_entry(hass, entry, [LAPTOP])
    await hass.config_entries.async_unload(entry.entry_id)

    mock_client = AsyncMock(spec=JNAPClient)
    mock_client.get_devices.return_value = GetDevicesResponse(devices=[])
    with patch(
        "homeassistant.components.linksys_smart.util.JNAPClient",
        return_value=mock_client,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    entity_id = entity_registry.async_get_entity_id(
        "device_tracker", DOMAIN, f"{entry.entry_id}_aa:bb:cc:dd:ee:ff"
    )
    assert entity_id is not None
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "not_home"


async def test_yaml_config_no_entry_imports_without_credentials(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    mock_jnap_client: AsyncMock,
) -> None:
    """Test that YAML config is imported as a credential-less entry when possible."""
    with patch.object(legacy.LOGGER, "error") as mock_error:
        assert await async_setup_component(
            hass,
            "device_tracker",
            {
                "device_tracker": {
                    "platform": "linksys_smart",
                    "host": "192.168.1.1",
                }
            },
        )
        await hass.async_block_till_done()
    mock_error.assert_not_called()

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0].data == {CONF_HOST: "192.168.1.1"}
    assert entries[0].state == ConfigEntryState.LOADED

    assert (
        issue_registry.async_get_issue(
            DOMAIN, "deprecated_yaml_import_issue_credentials_required_192.168.1.1"
        )
        is None
    )
    issue = issue_registry.async_get_issue(
        HOMEASSISTANT_DOMAIN, f"deprecated_yaml_{DOMAIN}"
    )
    assert issue is not None


async def test_yaml_config_no_entry_creates_credentials_required_issue(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    mock_jnap_client: AsyncMock,
) -> None:
    """Test that a router requiring credentials creates a credentials-required issue."""
    mock_jnap_client.get_devices.side_effect = JNAPUnauthorizedError

    with patch.object(legacy.LOGGER, "error") as mock_error:
        assert await async_setup_component(
            hass,
            "device_tracker",
            {
                "device_tracker": {
                    "platform": "linksys_smart",
                    "host": "192.168.1.1",
                }
            },
        )
        await hass.async_block_till_done()
    mock_error.assert_called_once()

    assert not hass.config_entries.async_entries(DOMAIN)

    issue = issue_registry.async_get_issue(
        DOMAIN, "deprecated_yaml_import_issue_credentials_required_192.168.1.1"
    )
    assert issue is not None
    assert issue.severity == ir.IssueSeverity.WARNING
    assert issue.translation_placeholders == {
        "domain": DOMAIN,
        "integration_title": "Linksys Smart Wi-Fi",
        "host": "192.168.1.1",
    }
    assert (
        issue_registry.async_get_issue(
            DOMAIN, "deprecated_yaml_import_issue_cannot_connect_192.168.1.1"
        )
        is None
    )


async def test_yaml_config_two_routers_failing_the_same_way_both_get_issues(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    mock_jnap_client: AsyncMock,
) -> None:
    """Test that two routers failing the same way don't collide on issue ID."""
    mock_jnap_client.get_devices.side_effect = JNAPUnauthorizedError

    assert await async_setup_component(
        hass,
        "device_tracker",
        {
            "device_tracker": [
                {"platform": "linksys_smart", "host": "192.168.1.1"},
                {"platform": "linksys_smart", "host": "192.168.1.2"},
            ]
        },
    )
    await hass.async_block_till_done()

    for host in ("192.168.1.1", "192.168.1.2"):
        issue = issue_registry.async_get_issue(
            DOMAIN, f"deprecated_yaml_import_issue_credentials_required_{host}"
        )
        assert issue is not None
        assert issue.translation_placeholders["host"] == host


async def test_yaml_config_no_entry_creates_unknown_issue(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    mock_jnap_client: AsyncMock,
) -> None:
    """Test that an unexpected error creates a distinct unknown-error issue."""
    mock_jnap_client.get_devices.side_effect = Exception

    with (
        patch.object(legacy.LOGGER, "error") as mock_error,
        patch.object(linksys_config_flow._LOGGER, "exception"),
    ):
        assert await async_setup_component(
            hass,
            "device_tracker",
            {
                "device_tracker": {
                    "platform": "linksys_smart",
                    "host": "192.168.1.1",
                }
            },
        )
        await hass.async_block_till_done()
    mock_error.assert_called_once()

    assert not hass.config_entries.async_entries(DOMAIN)

    issue = issue_registry.async_get_issue(
        DOMAIN, "deprecated_yaml_import_issue_unknown_192.168.1.1"
    )
    assert issue is not None
    assert issue.severity == ir.IssueSeverity.WARNING
    assert issue.translation_placeholders == {
        "domain": DOMAIN,
        "integration_title": "Linksys Smart Wi-Fi",
        "host": "192.168.1.1",
    }


async def test_yaml_config_no_entry_creates_cannot_connect_issue(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    mock_jnap_client: AsyncMock,
) -> None:
    """Test that an unreachable router creates a distinct cannot-connect issue."""
    mock_jnap_client.get_device_info.side_effect = JNAPError

    with patch.object(legacy.LOGGER, "error") as mock_error:
        assert await async_setup_component(
            hass,
            "device_tracker",
            {
                "device_tracker": {
                    "platform": "linksys_smart",
                    "host": "192.168.1.1",
                }
            },
        )
        await hass.async_block_till_done()
    mock_error.assert_called_once()

    assert not hass.config_entries.async_entries(DOMAIN)

    issue = issue_registry.async_get_issue(
        DOMAIN, "deprecated_yaml_import_issue_cannot_connect_192.168.1.1"
    )
    assert issue is not None
    assert issue.severity == ir.IssueSeverity.WARNING
    assert issue.translation_placeholders == {
        "domain": DOMAIN,
        "integration_title": "Linksys Smart Wi-Fi",
        "host": "192.168.1.1",
    }
    assert (
        issue_registry.async_get_issue(
            DOMAIN, "deprecated_yaml_import_issue_credentials_required_192.168.1.1"
        )
        is None
    )


async def test_yaml_config_with_entry_creates_remove_yaml_issue(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test that YAML config with an existing config entry prompts removal of YAML."""
    entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_HOST: "192.168.1.1", CONF_PASSWORD: "pass"}
    )
    entry.add_to_hass(hass)

    with patch.object(legacy.LOGGER, "error") as mock_error:
        assert await async_setup_component(
            hass,
            "device_tracker",
            {
                "device_tracker": {
                    "platform": "linksys_smart",
                    "host": "192.168.1.1",
                }
            },
        )
        await hass.async_block_till_done()
    mock_error.assert_not_called()

    issue = issue_registry.async_get_issue(
        HOMEASSISTANT_DOMAIN, f"deprecated_yaml_{DOMAIN}"
    )
    assert issue is not None
    assert issue.severity == ir.IssueSeverity.WARNING
    assert issue.translation_placeholders == {
        "domain": DOMAIN,
        "integration_title": "Linksys Smart Wi-Fi",
    }


async def test_yaml_config_second_router_with_different_host_is_imported(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    mock_jnap_client: AsyncMock,
) -> None:
    """Test that a second, differently-hosted YAML entry is still imported."""
    MockConfigEntry(
        domain=DOMAIN,
        unique_id="existing-serial",
        data={CONF_HOST: "192.168.1.1", CONF_PASSWORD: "pass"},
    ).add_to_hass(hass)

    mock_jnap_client.get_device_info.return_value = GetDeviceInfoResponse(
        description="Velop MX4200", serial_number=SERIAL
    )

    assert await async_setup_component(
        hass,
        "device_tracker",
        {
            "device_tracker": {
                "platform": "linksys_smart",
                "host": "192.168.1.2",
            }
        },
    )
    await hass.async_block_till_done()

    entries = hass.config_entries.async_entries(DOMAIN)
    assert {entry.data[CONF_HOST] for entry in entries} == {
        "192.168.1.1",
        "192.168.1.2",
    }
    issue = issue_registry.async_get_issue(
        HOMEASSISTANT_DOMAIN, f"deprecated_yaml_{DOMAIN}"
    )
    assert issue is not None


async def test_yaml_config_host_alias_creates_remove_yaml_issue(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    mock_jnap_client: AsyncMock,
) -> None:
    """Test that a YAML host aliasing an existing router still prompts YAML removal."""
    MockConfigEntry(
        domain=DOMAIN,
        unique_id=SERIAL,
        data={CONF_HOST: "192.168.1.1", CONF_PASSWORD: "pass"},
    ).add_to_hass(hass)

    assert await async_setup_component(
        hass,
        "device_tracker",
        {
            "device_tracker": {
                "platform": "linksys_smart",
                "host": "192.168.1.2",
            }
        },
    )
    await hass.async_block_till_done()

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1

    issue = issue_registry.async_get_issue(
        HOMEASSISTANT_DOMAIN, f"deprecated_yaml_{DOMAIN}"
    )
    assert issue is not None


async def test_yaml_config_host_alias_creates_remove_yaml_issue_when_devices_unauthorized(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    mock_jnap_client: AsyncMock,
) -> None:
    """Test host aliasing still prompts YAML removal if get_devices needs auth."""
    MockConfigEntry(
        domain=DOMAIN,
        unique_id=SERIAL,
        data={CONF_HOST: "192.168.1.1", CONF_PASSWORD: "pass"},
    ).add_to_hass(hass)

    mock_jnap_client.get_devices.side_effect = JNAPUnauthorizedError

    assert await async_setup_component(
        hass,
        "device_tracker",
        {
            "device_tracker": {
                "platform": "linksys_smart",
                "host": "192.168.1.2",
            }
        },
    )
    await hass.async_block_till_done()

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1

    assert (
        issue_registry.async_get_issue(
            DOMAIN, "deprecated_yaml_import_issue_credentials_required_192.168.1.2"
        )
        is None
    )
    issue = issue_registry.async_get_issue(
        HOMEASSISTANT_DOMAIN, f"deprecated_yaml_{DOMAIN}"
    )
    assert issue is not None
