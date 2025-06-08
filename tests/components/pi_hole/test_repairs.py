"""Test pi_hole component."""

from unittest.mock import AsyncMock

import pytest

import homeassistant
from homeassistant.components import pi_hole
from homeassistant.const import CONF_API_VERSION
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir

from . import (
    CONFIG_DATA_DEFAULTS,
    V6_RESPONSE_TO_V5_ENPOINT,
    ZERO_DATA,
    _create_mocked_hole,
    _patch_init_hole,
)

from tests.common import MockConfigEntry


async def test_change_api_5_to_6(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> None:
    """Tests a user with an API version 5 config entry that is updated to API version 6."""
    mocked_hole = _create_mocked_hole(api_version=5)

    # setu up a valid API version 5 config entry
    entry = MockConfigEntry(
        domain=pi_hole.DOMAIN,
        data={**CONFIG_DATA_DEFAULTS, CONF_API_VERSION: 5},
    )
    entry.add_to_hass(hass)
    with _patch_init_hole(mocked_hole):
        assert await hass.config_entries.async_setup(entry.entry_id)

        assert mocked_hole.instances[-1].data == ZERO_DATA
        # Change the mock's state after setup
        mocked_hole.instances[-1].hole_version = 6
        mocked_hole.instances[-1].api_token = "wrong_token"

        # Patch the method on the coordinator's api reference directly
        pihole_data = entry.runtime_data
        assert pihole_data.api == mocked_hole.instances[-1]
        pihole_data.api.get_data = AsyncMock(
            side_effect=lambda: setattr(
                pihole_data.api, "data", V6_RESPONSE_TO_V5_ENPOINT
            )
        )

        # Now trigger the update
        with pytest.raises(homeassistant.exceptions.ConfigEntryAuthFailed):
            await pihole_data.coordinator.update_method()
        assert pihole_data.api.data == V6_RESPONSE_TO_V5_ENPOINT

        # ensure an issue is created for the API version change
        assert len(issue_registry.issues) == 0
        assert (
            issue_registry.async_get_issue(
                issue_id=f"v5_to_v6_migration_{pihole_data.api.base_url}",
                domain=pi_hole.DOMAIN,
            )
            is not None
        )
