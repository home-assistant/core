"""Tests for Synology DSM select entities."""

from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.synology_dsm.const import DOMAIN
from homeassistant.const import (
    CONF_HOST,
    CONF_MAC,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SSL,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .common import mock_dsm_hardware, mock_dsm_information
from .consts import HOST, MACS, PASSWORD, PORT, SERIAL, USE_SSL, USERNAME

from tests.common import MockConfigEntry, snapshot_platform


@pytest.fixture
def mock_dsm():
    """Mock a successful service."""
    with patch("homeassistant.components.synology_dsm.common.SynologyDSM") as dsm:
        dsm.login = AsyncMock(return_value=True)
        dsm.update = AsyncMock(return_value=True)

        dsm.surveillance_station.update = AsyncMock(return_value=True)
        dsm.upgrade.update = AsyncMock(return_value=True)
        dsm.network = Mock(
            update=AsyncMock(return_value=True), macs=MACS, hostname=HOST
        )
        dsm.hardware = mock_dsm_hardware()
        dsm.information = mock_dsm_information()
        dsm.file = Mock(get_shared_folders=AsyncMock(return_value=None))
        dsm.logout = AsyncMock(return_value=True)
        yield dsm


async def test_fan_speed(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_dsm: MagicMock,
) -> None:
    """Test Synology DSM without USB."""
    with (
        patch(
            "homeassistant.components.synology_dsm.common.SynologyDSM",
            return_value=mock_dsm,
        ),
        patch("homeassistant.components.synology_dsm.PLATFORMS", ["select"]),
    ):
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={
                CONF_HOST: HOST,
                CONF_PORT: PORT,
                CONF_SSL: USE_SSL,
                CONF_USERNAME: USERNAME,
                CONF_PASSWORD: PASSWORD,
                CONF_MAC: MACS[0],
            },
            unique_id=SERIAL,
        )
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    await snapshot_platform(hass, entity_registry, snapshot, entry.entry_id)
