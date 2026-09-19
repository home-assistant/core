"""Test the De Lijn coordinator."""

from unittest.mock import MagicMock

from pydelijn import DeLijnAuthError, DeLijnConnectionError
import pytest

from homeassistant.components.delijn.const import DOMAIN
from homeassistant.components.delijn.coordinator import DeLijnCoordinator
from homeassistant.config_entries import ConfigSubentry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import UpdateFailed

from tests.common import MockConfigEntry


async def test_update_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_stop_subentry: ConfigSubentry,
    mock_delijn_client: MagicMock,
) -> None:
    """Test a connection error is raised as a translatable UpdateFailed."""
    coordinator = DeLijnCoordinator(
        hass, mock_config_entry, mock_stop_subentry, mock_delijn_client
    )
    mock_delijn_client.get_passages.side_effect = DeLijnConnectionError("boom")

    with pytest.raises(UpdateFailed) as exc_info:
        await coordinator._async_update_data()

    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_key == "update_error"
    assert exc_info.value.translation_placeholders == {"error": "boom"}


async def test_auth_failed(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_stop_subentry: ConfigSubentry,
    mock_delijn_client: MagicMock,
) -> None:
    """Test an auth error is raised as a translatable ConfigEntryAuthFailed."""
    coordinator = DeLijnCoordinator(
        hass, mock_config_entry, mock_stop_subentry, mock_delijn_client
    )
    mock_delijn_client.get_passages.side_effect = DeLijnAuthError("nope")

    with pytest.raises(ConfigEntryAuthFailed) as exc_info:
        await coordinator._async_update_data()

    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_key == "auth_failed"
