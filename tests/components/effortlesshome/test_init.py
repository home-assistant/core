"""Tests for the EffortlessHome init module."""

from unittest.mock import AsyncMock, Mock, patch

from oasira import OasiraAPIError
import pytest

from homeassistant.components.effortlesshome import (
    HASSComponent,
    add_label_to_entity,
    async_setup_entry,
    async_unload_entry,
    clean_motion_files,
    create_event,
    register_services,
)
from homeassistant.components.effortlesshome.const import DOMAIN
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryError,
    ConfigEntryNotReady,
)


async def test_async_setup_entry_success(
    hass: HomeAssistant,
    mock_config_entry,
    parsed_customer_data: dict[str, object],
) -> None:
    """Test successful setup from config entry."""
    mock_client = AsyncMock()
    mock_client.get_customer_and_system.return_value = parsed_customer_data
    mock_client.get_plan_features_by_system_id.return_value = {"feature": True}

    with (
        patch("homeassistant.components.effortlesshome.OasiraAPIClient") as mock_api,
        patch.object(
            hass.config_entries,
            "async_forward_entry_setups",
            new=AsyncMock(),
        ),
        patch("homeassistant.components.effortlesshome.dr.async_get") as mock_dr_get,
        patch("homeassistant.components.effortlesshome.lr.async_get") as mock_lr_get,
    ):
        mock_api.return_value.__aenter__.return_value = mock_client
        mock_api.return_value.__aexit__.return_value = None

        mock_device_registry = Mock()
        mock_dr_get.return_value = mock_device_registry

        mock_label_registry = Mock()
        mock_lr_get.return_value = mock_label_registry

        assert await async_setup_entry(hass, mock_config_entry)

    assert DOMAIN in hass.data
    assert hass.data[DOMAIN]["systemid"] == "67890"
    assert hass.data[DOMAIN]["customerid"] == "12345"
    assert hass.data[DOMAIN]["plan"] == "Basic Plan"
    assert mock_config_entry.runtime_data == hass.data[DOMAIN]

    mock_device_registry.async_get_or_create.assert_called_once()
    assert hass.services.has_service(DOMAIN, "create_event")


@pytest.mark.parametrize(
    ("field", "message"),
    [
        ("system_id", "System ID is missing"),
        ("customer_id", "Customer ID is missing"),
    ],
)
async def test_async_setup_entry_missing_required_ids(
    hass: HomeAssistant,
    mock_config_entry,
    field: str,
    message: str,
) -> None:
    """Test setup fails when required IDs are missing."""
    mock_config_entry.data = {**mock_config_entry.data, field: ""}

    with pytest.raises(ConfigEntryError, match=message):
        await async_setup_entry(hass, mock_config_entry)


async def test_async_setup_entry_auth_failed(
    hass: HomeAssistant,
    mock_config_entry,
) -> None:
    """Test setup raises ConfigEntryAuthFailed on auth failure."""
    mock_client = AsyncMock()
    mock_client.get_customer_and_system.side_effect = OasiraAPIError(
        "401 Unauthorized"
    )

    with patch("homeassistant.components.effortlesshome.OasiraAPIClient") as mock_api:
        mock_api.return_value.__aenter__.return_value = mock_client
        mock_api.return_value.__aexit__.return_value = None

        with pytest.raises(ConfigEntryAuthFailed):
            await async_setup_entry(hass, mock_config_entry)


async def test_async_setup_entry_not_ready(
    hass: HomeAssistant,
    mock_config_entry,
) -> None:
    """Test setup raises ConfigEntryNotReady on transient API failure."""
    mock_client = AsyncMock()
    mock_client.get_customer_and_system.side_effect = OasiraAPIError(
        "Gateway timeout"
    )

    with patch("homeassistant.components.effortlesshome.OasiraAPIClient") as mock_api:
        mock_api.return_value.__aenter__.return_value = mock_client
        mock_api.return_value.__aexit__.return_value = None

        with pytest.raises(ConfigEntryNotReady):
            await async_setup_entry(hass, mock_config_entry)


async def test_async_unload_entry_removes_services(
    hass: HomeAssistant,
    mock_config_entry,
) -> None:
    """Test unload unregisters services and unloads platforms."""
    register_services(hass)

    with patch.object(
        hass.config_entries, "async_unload_platforms", new=AsyncMock()
    ) as mock_unload:
        assert await async_unload_entry(hass, mock_config_entry)

    mock_unload.assert_awaited_once_with(mock_config_entry, ["switch"])
    assert not hass.services.has_service(DOMAIN, "create_event")


async def test_add_label_to_entity_updates_registry(hass: HomeAssistant) -> None:
    """Test adding a label updates entity labels in registry."""
    fake_entity = Mock(labels={"Existing"})
    fake_registry = Mock()
    fake_registry.async_get.return_value = fake_entity

    HASSComponent.set_hass(hass)
    with patch(
        "homeassistant.components.effortlesshome.er.async_get",
        return_value=fake_registry,
    ):
        await add_label_to_entity(
            ServiceCall(
                DOMAIN,
                "add_label_to_entity",
                {"entity_id": "light.kitchen", "label": "Favorite"},
            )
        )

    fake_registry.async_update_entity.assert_called_once_with(
        "light.kitchen",
        labels={"Existing", "Favorite"},
    )


async def test_create_event_returns_none_when_entity_missing(
    hass: HomeAssistant,
) -> None:
    """Test create_event short-circuits when entity_id is missing."""
    HASSComponent.set_hass(hass)
    assert await create_event(ServiceCall(DOMAIN, "create_event", {})) is None


async def test_clean_motion_files_invalid_age_uses_default(
    hass: HomeAssistant,
) -> None:
    """Test clean_motion_files handles invalid age values."""
    HASSComponent.set_hass(hass)

    with patch(
        "homeassistant.components.effortlesshome._clean_motion_files_sync",
        return_value=(1, []),
    ) as mock_clean:
        await clean_motion_files(
            ServiceCall(DOMAIN, "clean_motion_files", {"age": 0})
        )

    mock_clean.assert_called_once_with(30)
