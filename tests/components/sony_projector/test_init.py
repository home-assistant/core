"""Tests for the Sony Projector integration setup."""

from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.components.sony_projector import (
    PLATFORMS,
    SonyProjectorRuntimeData,
    async_setup,
    async_setup_entry,
    async_unload_entry,
)
from homeassistant.components.sony_projector.const import (
    CONF_TITLE,
    DATA_YAML_ISSUE_CREATED,
    DATA_YAML_SWITCH_HOSTS,
    DEFAULT_NAME,
    DOMAIN,
    ISSUE_YAML_DEPRECATED,
)
from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.issue_registry import IssueSeverity

from tests.common import MockConfigEntry


async def test_async_setup_imports_yaml_and_creates_issue(
    hass: HomeAssistant,
) -> None:
    """Test YAML setup imports configuration and surfaces a repairs issue."""

    hass.config_entries.flow.async_init = AsyncMock(return_value=None)

    config = {
        "switch": [
            {"platform": DOMAIN, CONF_HOST: "1.1.1.1", CONF_NAME: "Compat"},
            {"platform": DOMAIN, CONF_HOST: "2.2.2.2"},
        ],
        "media_player": [
            {"platform": DOMAIN, CONF_HOST: "3.3.3.3", CONF_NAME: "Projector"},
            {"platform": "other", CONF_HOST: "9.9.9.9"},
        ],
    }

    with patch(
        "homeassistant.components.sony_projector.async_create_issue",
        MagicMock(),
    ) as mock_issue:
        assert await async_setup(hass, config)
        await hass.async_block_till_done()

    yaml_hosts = hass.data[DOMAIN][DATA_YAML_SWITCH_HOSTS]
    assert yaml_hosts == {"1.1.1.1", "2.2.2.2"}
    hass.config_entries.flow.async_init.assert_awaited_once_with(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={CONF_HOST: "3.3.3.3", CONF_NAME: "Projector"},
    )
    assert mock_issue.call_count == 1
    issue_args, issue_kwargs = mock_issue.call_args
    assert issue_args == (hass, DOMAIN, ISSUE_YAML_DEPRECATED)
    assert issue_kwargs["is_fixable"] is False
    assert (
        issue_kwargs["learn_more_url"]
        == "https://www.home-assistant.io/integrations/sony_projector"
    )
    assert issue_kwargs["severity"] == IssueSeverity.WARNING
    assert issue_kwargs["translation_key"] == "yaml_deprecated"
    assert hass.data[DOMAIN][DATA_YAML_ISSUE_CREATED]


async def test_async_setup_entry_creates_runtime_and_device(
    hass: HomeAssistant,
) -> None:
    """Test setting up a config entry stores runtime data and device registry entry."""

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "1.2.3.4", CONF_TITLE: "Living Room"},
    )
    entry.add_to_hass(hass)

    mock_client = MagicMock()

    with (
        patch(
            "homeassistant.components.sony_projector.ProjectorClient",
            return_value=mock_client,
        ) as mock_client_ctor,
        patch.object(
            hass.config_entries,
            "async_forward_entry_setups",
            AsyncMock(return_value=None),
        ) as mock_forward,
    ):
        assert await async_setup_entry(hass, entry)

    mock_client_ctor.assert_called_once_with("1.2.3.4")
    mock_forward.assert_awaited_once_with(entry, PLATFORMS)
    runtime = hass.data[DOMAIN][entry.entry_id]
    assert isinstance(runtime, SonyProjectorRuntimeData)
    assert runtime.client is mock_client
    assert entry.runtime_data is runtime

    device_registry = dr.async_get(hass)
    device = device_registry.async_get_device({(DOMAIN, "1.2.3.4")})
    assert device is not None
    assert device.manufacturer == "Sony"
    assert device.name == "Living Room"


async def test_async_unload_entry_unloads_platforms_and_cleans_up(
    hass: HomeAssistant,
) -> None:
    """Test unloading a config entry removes stored data."""

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "5.6.7.8", CONF_TITLE: DEFAULT_NAME},
    )
    entry.add_to_hass(hass)

    mock_client = MagicMock()

    with (
        patch(
            "homeassistant.components.sony_projector.ProjectorClient",
            return_value=mock_client,
        ),
        patch.object(
            hass.config_entries,
            "async_forward_entry_setups",
            AsyncMock(return_value=None),
        ),
    ):
        assert await async_setup_entry(hass, entry)

    with patch.object(
        hass.config_entries,
        "async_unload_platforms",
        AsyncMock(return_value=True),
    ) as mock_unload:
        assert await async_unload_entry(hass, entry)

    mock_unload.assert_awaited_once_with(entry, PLATFORMS)
    assert entry.entry_id not in hass.data[DOMAIN]
