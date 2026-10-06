"""Testing the Prowl initialisation."""

from typing import Any
from unittest.mock import AsyncMock

import prowlpy
import pytest

from homeassistant.components import notify
from homeassistant.components.prowl.const import DOMAIN
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntryState
from homeassistant.const import CONF_API_KEY, CONF_NAME, CONF_PLATFORM
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.setup import async_setup_component

from .conftest import ENTITY_ID, OTHER_API_KEY, TEST_API_KEY, TEST_NAME

from tests.common import MockConfigEntry


async def test_load_reload_unload_config_entry(
    hass: HomeAssistant,
    mock_prowlpy_config_entry: MockConfigEntry,
    mock_prowlpy: AsyncMock,
) -> None:
    """Test the Prowl configuration entry loading/reloading/unloading."""
    mock_prowlpy_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_prowlpy_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_prowlpy_config_entry.state is ConfigEntryState.LOADED
    assert mock_prowlpy.verify_key.call_count > 0

    await hass.config_entries.async_reload(mock_prowlpy_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_prowlpy_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(mock_prowlpy_config_entry.entry_id)
    await hass.async_block_till_done()

    assert not hass.data.get(DOMAIN)
    assert mock_prowlpy_config_entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.parametrize(
    ("prowlpy_side_effect", "expected_config_state"),
    [
        (TimeoutError, ConfigEntryState.SETUP_RETRY),
        (
            prowlpy.APIError(f"Invalid API key: {TEST_API_KEY}"),
            ConfigEntryState.SETUP_ERROR,
        ),
        (
            prowlpy.APIError("Not accepted: exceeded rate limit"),
            ConfigEntryState.SETUP_RETRY,
        ),
        (prowlpy.APIError("Internal server error"), ConfigEntryState.SETUP_ERROR),
    ],
)
async def test_config_entry_failures(
    hass: HomeAssistant,
    mock_prowlpy_config_entry: MockConfigEntry,
    mock_prowlpy: AsyncMock,
    prowlpy_side_effect,
    expected_config_state: ConfigEntryState,
) -> None:
    """Test the Prowl configuration entry dealing with bad API key."""
    mock_prowlpy.verify_key.side_effect = prowlpy_side_effect

    mock_prowlpy_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_prowlpy_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_prowlpy_config_entry.state is expected_config_state
    assert mock_prowlpy.verify_key.call_count > 0


async def _setup_yaml(hass: HomeAssistant, platform_config: dict[str, str]) -> None:
    """Set up the Prowl notify platform from YAML."""
    await async_setup_component(
        hass,
        notify.DOMAIN,
        {notify.DOMAIN: [{CONF_PLATFORM: DOMAIN, **platform_config}]},
    )
    await hass.async_block_till_done()


@pytest.mark.usefixtures("configure_prowl_through_yaml")
async def test_yaml_import(
    hass: HomeAssistant,
    mock_prowlpy: AsyncMock,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test the YAML configuration is imported and the legacy action keeps working."""
    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    entry = entries[0]
    assert entry.state is ConfigEntryState.LOADED
    assert entry.source == SOURCE_IMPORT
    assert entry.title == DOMAIN
    assert entry.data == {CONF_API_KEY: TEST_API_KEY}
    assert issue_registry.async_get_issue(
        HOMEASSISTANT_DOMAIN, f"deprecated_yaml_{DOMAIN}"
    )

    assert hass.services.has_service(notify.DOMAIN, DOMAIN)
    await hass.services.async_call(
        notify.DOMAIN, DOMAIN, {notify.ATTR_MESSAGE: "Test"}, blocking=True
    )
    mock_prowlpy.post.assert_called_once()

    # YAML provides the legacy service while it is present, not the entry
    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert hass.services.has_service(notify.DOMAIN, DOMAIN)


@pytest.mark.usefixtures("mock_prowlpy")
async def test_yaml_import_without_name(hass: HomeAssistant) -> None:
    """Test the legacy action keeps its default name after the import."""
    await _setup_yaml(hass, {CONF_API_KEY: TEST_API_KEY})

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0].title == "Prowl"
    assert hass.services.has_service(notify.DOMAIN, notify.SERVICE_NOTIFY)


@pytest.mark.usefixtures("mock_prowlpy")
async def test_yaml_import_existing_config_entry(
    hass: HomeAssistant,
    mock_prowlpy_config_entry: MockConfigEntry,
) -> None:
    """Test YAML for an API key that was already set up in the UI."""
    mock_prowlpy_config_entry.add_to_hass(hass)

    await _setup_yaml(hass, {CONF_API_KEY: TEST_API_KEY, CONF_NAME: DOMAIN})

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert mock_prowlpy_config_entry.state is ConfigEntryState.LOADED
    # The existing entry is not changed: YAML keeps providing the legacy action
    assert mock_prowlpy_config_entry.title == TEST_NAME
    assert hass.services.has_service(notify.DOMAIN, DOMAIN)
    assert hass.states.get(ENTITY_ID) is not None


@pytest.mark.parametrize(
    ("prowlpy_side_effect", "expected_state"),
    [
        pytest.param(
            prowlpy.APIError("Invalid API key: foo"),
            ConfigEntryState.SETUP_ERROR,
            id="invalid_api_key",
        ),
        pytest.param(TimeoutError, ConfigEntryState.SETUP_RETRY, id="timeout"),
    ],
)
async def test_yaml_import_entry_setup_failure(
    hass: HomeAssistant,
    mock_prowlpy: AsyncMock,
    issue_registry: ir.IssueRegistry,
    prowlpy_side_effect: Exception | type[Exception],
    expected_state: ConfigEntryState,
) -> None:
    """Test the import is not blocked by API problems and YAML keeps working."""
    mock_prowlpy.verify_key.side_effect = prowlpy_side_effect

    await _setup_yaml(hass, {CONF_API_KEY: TEST_API_KEY, CONF_NAME: DOMAIN})

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0].state is expected_state
    assert issue_registry.async_get_issue(
        HOMEASSISTANT_DOMAIN, f"deprecated_yaml_{DOMAIN}"
    )
    assert len(issue_registry.issues) == 1

    assert hass.services.has_service(notify.DOMAIN, DOMAIN)
    await hass.services.async_call(
        notify.DOMAIN, DOMAIN, {notify.ATTR_MESSAGE: "Test"}, blocking=True
    )
    mock_prowlpy.post.assert_called_once()


@pytest.mark.usefixtures("mock_prowlpy")
async def test_config_entry_without_legacy_service(
    hass: HomeAssistant,
    mock_prowlpy_config_entry: MockConfigEntry,
) -> None:
    """Test a config entry set up in the UI does not get a legacy action."""
    mock_prowlpy_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_prowlpy_config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get(ENTITY_ID) is not None
    assert not hass.services.has_service(notify.DOMAIN, DOMAIN)
    assert not hass.services.has_service(notify.DOMAIN, notify.SERVICE_NOTIFY)


@pytest.mark.parametrize(
    ("config", "issue_expected"),
    [
        pytest.param(
            {
                notify.DOMAIN: [
                    {CONF_PLATFORM: DOMAIN, CONF_API_KEY: OTHER_API_KEY},
                ]
            },
            True,
            id="yaml_configured",
        ),
        pytest.param(
            {notify.DOMAIN: [{CONF_PLATFORM: "other", CONF_API_KEY: "key"}]},
            False,
            id="other_notify_platform",
        ),
        pytest.param({}, False, id="no_yaml"),
    ],
)
@pytest.mark.usefixtures("mock_prowlpy")
async def test_config_entry_setup_yaml_deprecation_issue(
    hass: HomeAssistant,
    mock_prowlpy_config_entry: MockConfigEntry,
    issue_registry: ir.IssueRegistry,
    config: dict[str, Any],
    issue_expected: bool,
) -> None:
    """Test a config entry raises the YAML deprecation issue while YAML is present."""
    mock_prowlpy_config_entry.add_to_hass(hass)

    assert await async_setup_component(hass, DOMAIN, config)
    await hass.async_block_till_done()

    assert mock_prowlpy_config_entry.state is ConfigEntryState.LOADED
    assert (
        issue_registry.async_get_issue(
            HOMEASSISTANT_DOMAIN, f"deprecated_yaml_{DOMAIN}"
        )
        is not None
    ) is issue_expected


@pytest.mark.parametrize(
    ("title", "service"),
    [
        pytest.param("prowl", "prowl", id="yaml_name"),
        pytest.param("My Prowl", "my_prowl", id="slugified"),
    ],
)
async def test_legacy_service_from_config_entry(
    hass: HomeAssistant,
    mock_prowlpy: AsyncMock,
    title: str,
    service: str,
) -> None:
    """Test an imported entry sets up the legacy action after YAML is removed."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=title,
        data={CONF_API_KEY: TEST_API_KEY},
        source=SOURCE_IMPORT,
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert hass.services.has_service(notify.DOMAIN, service)
    await hass.services.async_call(
        notify.DOMAIN, service, {notify.ATTR_MESSAGE: "Test"}, blocking=True
    )
    mock_prowlpy.post.assert_called_once()

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert not hass.services.has_service(notify.DOMAIN, service)


@pytest.mark.usefixtures("mock_prowlpy")
async def test_yaml_import_multiple_names(hass: HomeAssistant) -> None:
    """Test several YAML notifiers with the same API key create one entry."""
    await async_setup_component(
        hass,
        notify.DOMAIN,
        {
            notify.DOMAIN: [
                {CONF_PLATFORM: DOMAIN, CONF_API_KEY: TEST_API_KEY, CONF_NAME: "one"},
                {CONF_PLATFORM: DOMAIN, CONF_API_KEY: TEST_API_KEY, CONF_NAME: "two"},
            ]
        },
    )
    await hass.async_block_till_done()

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0].title in ("one", "two")
    # YAML provides both legacy actions while it is present
    assert hass.services.has_service(notify.DOMAIN, "one")
    assert hass.services.has_service(notify.DOMAIN, "two")
