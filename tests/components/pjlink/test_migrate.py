"""Tests for the PJLink config flow."""

from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components.pjlink.const import CONF_ENCODING, DOMAIN
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PASSWORD, CONF_PORT

# from homeassistant.components.pjlink.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry

NO_AUTH_RESPONSE = "PJLINK 0\r"

# pytestmark = pytest.mark.usefixtures("mock_old_config_entry")


@pytest.fixture
def mock_connection_create() -> MagicMock:
    """Return the default mocked connection.create."""
    proj = MagicMock()
    with patch(
        # "pjlink.Connection.create",
        "pypjlink.Projector.from_address",
        return_value=proj,
    ) as mock:
        yield mock


# @patch("pypjlink.Projector")
async def test_migrate_entry(
    hass: HomeAssistant,
    # mock_connection_create: MagicMock,
    # mocked_projector: AsyncMock,
) -> None:
    """Test migrating a config entry from version 1 to version 2."""
    # Create mock entry with version 1
    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "1.1.1.1",
            CONF_PORT: 4352,
            CONF_NAME: "New PJLink Projector",
            CONF_ENCODING: "utf-8",
            CONF_PASSWORD: "password",
        },
        options={
            "entity_id": "media_player.new_pjlink_projector",
        },
        # version=1,
    )

    # Set it up
    mock_entry.add_to_hass(hass)
    assert await async_setup_component(hass, DOMAIN, {}) is True
    # await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()
    await hass.config_entries.async_reload(mock_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_entry.version == 2
    assert mock_entry.unique_id
    # Check that it has a source_id now
    # updated_entry = hass.config_entries.async_get_entry(mock_entry.entry_id)
    # assert updated_entry
    # assert updated_entry.version == 2
    # assert updated_entry.data.get(CONF_SOURCE_ID) == MOCK_SOURCE_ID
