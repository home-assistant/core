"""Test BMW coordinator for general availability/unavailability of entities and raising issues."""

from copy import deepcopy
from unittest.mock import patch

from bimmer_connected.models import (
    MyBMWAPIError,
    MyBMWAuthError,
    MyBMWCaptchaMissingError,
)
from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.bmw_connected_drive import DOMAIN as BMW_DOMAIN
from homeassistant.components.bmw_connected_drive.const import (
    CONF_REFRESH_TOKEN,
    SCAN_INTERVALS,
)
from homeassistant.const import CONF_REGION
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.helpers import issue_registry as ir

from . import BIMMER_CONNECTED_VEHICLE_PATCH, FIXTURE_CONFIG_ENTRY

from tests.common import MockConfigEntry, async_fire_time_changed

FIXTURE_ENTITY_STATES = {
    "binary_sensor.m340i_xdrive_door_lock_state": "off",
    "lock.m340i_xdrive_lock": "locked",
    "lock.i3_rex_lock": "unlocked",
    "number.ix_xdrive50_target_soc": "80",
    "sensor.ix_xdrive50_rear_left_tire_pressure": "2.61",
    "sensor.ix_xdrive50_rear_right_tire_pressure": "2.69",
}
FIXTURE_DEFAULT_REGION = FIXTURE_CONFIG_ENTRY["data"][CONF_REGION]


@pytest.mark.usefixtures("bmw_fixture")
async def test_config_entry_update(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test if the coordinator updates the refresh token in config entry."""
    config_entry_fixure = deepcopy(FIXTURE_CONFIG_ENTRY)
    config_entry_fixure["data"][CONF_REFRESH_TOKEN] = "old_token"
    config_entry = MockConfigEntry(**config_entry_fixure)
    config_entry.add_to_hass(hass)

    assert (
        hass.config_entries.async_get_entry(config_entry.entry_id).data[
            CONF_REFRESH_TOKEN
        ]
        == "old_token"
    )

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert (
        hass.config_entries.async_get_entry(config_entry.entry_id).data[
            CONF_REFRESH_TOKEN
        ]
        == "another_token_string"
    )


@pytest.mark.usefixtures("bmw_fixture")
async def test_update_failed(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a failing API call."""
    config_entry = MockConfigEntry(**FIXTURE_CONFIG_ENTRY)
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    # Test if entities show data correctly
    for entity_id, state in FIXTURE_ENTITY_STATES.items():
        assert hass.states.get(entity_id).state == state

    # On API error, entities should be unavailable
    freezer.tick(SCAN_INTERVALS[FIXTURE_DEFAULT_REGION])
    with patch(
        BIMMER_CONNECTED_VEHICLE_PATCH,
        side_effect=MyBMWAPIError("Test error"),
    ):
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

    for entity_id in FIXTURE_ENTITY_STATES:
        assert hass.states.get(entity_id).state == "unavailable"

    # And should recover on next update
    freezer.tick(SCAN_INTERVALS[FIXTURE_DEFAULT_REGION])
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    for entity_id, state in FIXTURE_ENTITY_STATES.items():
        assert hass.states.get(entity_id).state == state


@pytest.mark.usefixtures("bmw_fixture")
async def test_auth_failed_as_update_failed(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test a single auth failure not initializing reauth flow."""
    config_entry = MockConfigEntry(**FIXTURE_CONFIG_ENTRY)
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    # Test if entities show data correctly
    for entity_id, state in FIXTURE_ENTITY_STATES.items():
        assert hass.states.get(entity_id).state == state

    # Due to flaky API, we allow one retry on AuthError and raise as UpdateFailed
    freezer.tick(SCAN_INTERVALS[FIXTURE_DEFAULT_REGION])
    with patch(
        BIMMER_CONNECTED_VEHICLE_PATCH,
        side_effect=MyBMWAuthError("Test error"),
    ):
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

    for entity_id in FIXTURE_ENTITY_STATES:
        assert hass.states.get(entity_id).state == "unavailable"

    # And should recover on next update
    freezer.tick(SCAN_INTERVALS[FIXTURE_DEFAULT_REGION])
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    for entity_id, state in FIXTURE_ENTITY_STATES.items():
        assert hass.states.get(entity_id).state == state

    # Verify that no issues are raised and no reauth flow is initialized
    assert len(issue_registry.issues) == 0
    assert len(hass.config_entries.flow.async_progress_by_handler(BMW_DOMAIN)) == 0


@pytest.mark.usefixtures("bmw_fixture")
async def test_auth_failed_init_reauth(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test a two subsequent auth failures initializing reauth flow."""

    config_entry = MockConfigEntry(**FIXTURE_CONFIG_ENTRY)
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    # Test if entities show data correctly
    for entity_id, state in FIXTURE_ENTITY_STATES.items():
        assert hass.states.get(entity_id).state == state
    assert len(issue_registry.issues) == 0

    # Due to flaky API, we allow one retry on AuthError and raise as UpdateFailed
    freezer.tick(SCAN_INTERVALS[FIXTURE_DEFAULT_REGION])
    with patch(
        BIMMER_CONNECTED_VEHICLE_PATCH,
        side_effect=MyBMWAuthError("Test error"),
    ):
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

    for entity_id in FIXTURE_ENTITY_STATES:
        assert hass.states.get(entity_id).state == "unavailable"
    assert len(issue_registry.issues) == 0

    # On second failure, we should initialize reauth flow
    freezer.tick(SCAN_INTERVALS[FIXTURE_DEFAULT_REGION])
    with patch(
        BIMMER_CONNECTED_VEHICLE_PATCH,
        side_effect=MyBMWAuthError("Test error"),
    ):
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

    for entity_id in FIXTURE_ENTITY_STATES:
        assert hass.states.get(entity_id).state == "unavailable"
    assert len(issue_registry.issues) == 1

    reauth_issue = issue_registry.async_get_issue(
        HOMEASSISTANT_DOMAIN,
        f"config_entry_reauth_{BMW_DOMAIN}_{config_entry.entry_id}",
    )
    assert reauth_issue.active is True

    # Check if reauth flow is initialized correctly
    flow = hass.config_entries.flow.async_get(reauth_issue.data["flow_id"])
    assert flow["handler"] == BMW_DOMAIN
    assert flow["context"]["source"] == "reauth"
    assert flow["context"]["unique_id"] == config_entry.unique_id


@pytest.mark.usefixtures("bmw_fixture")
async def test_captcha_reauth(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test a CaptchaError initializing reauth flow."""
    config_entry = MockConfigEntry(**FIXTURE_CONFIG_ENTRY)
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    # Test if entities show data correctly
    for entity_id, state in FIXTURE_ENTITY_STATES.items():
        assert hass.states.get(entity_id).state == state

    # If library decides a captcha is needed, we should initialize reauth flow
    freezer.tick(SCAN_INTERVALS[FIXTURE_DEFAULT_REGION])
    with patch(
        BIMMER_CONNECTED_VEHICLE_PATCH,
        side_effect=MyBMWCaptchaMissingError("Missing hCaptcha token"),
    ):
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

    for entity_id in FIXTURE_ENTITY_STATES:
        assert hass.states.get(entity_id).state == "unavailable"
    assert len(issue_registry.issues) == 1

    reauth_issue = issue_registry.async_get_issue(
        HOMEASSISTANT_DOMAIN,
        f"config_entry_reauth_{BMW_DOMAIN}_{config_entry.entry_id}",
    )
    assert reauth_issue.active is True

    # Check if reauth flow is initialized correctly
    flow = hass.config_entries.flow.async_get(reauth_issue.data["flow_id"])
    assert flow["handler"] == BMW_DOMAIN
    assert flow["context"]["source"] == "reauth"
    assert flow["context"]["unique_id"] == config_entry.unique_id
