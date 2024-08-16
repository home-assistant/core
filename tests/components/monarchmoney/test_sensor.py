"""Test sensors."""

from unittest.mock import AsyncMock, patch

from syrupy import SnapshotAssertion

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, snapshot_platform


async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_config_api: AsyncMock,
) -> None:
    """Test all entities."""
    with patch("homeassistant.components.monarchmoney.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


# @pytest.mark.asyncio
# async def test_login(mock_api):
#     """Test the login method of the MonarchMoney class."""
#     # Arrange
#     monarch_client = mock_api
#
#     # Act
#     try:
#         await monarch_client.login(
#             email="test@example.com",
#             password="password",
#             save_session=False,
#             use_saved_session=False,
#             mfa_secret_key="mfa_secret_key",
#         )
#     except LoginFailedException as exc:
#         raise LoginFailedException from exc
#
#     # Assert
#     monarch_client.login.assert_awaited_once_with(
#         email="test@example.com",
#         password="password",
#         save_session=False,
#         use_saved_session=False,
#         mfa_secret_key="mfa_secret_key",
#     )
