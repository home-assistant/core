"""The tests for the Vacuum entity integration."""
from __future__ import annotations

from collections.abc import Generator

import pytest

from homeassistant.components.vacuum import DOMAIN as VACUUM_DOMAIN, VacuumEntity
from homeassistant.config_entries import ConfigEntry, ConfigFlow
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from tests.common import (
    MockConfigEntry,
    MockModule,
    MockPlatform,
    mock_config_flow,
    mock_integration,
    mock_platform,
)

TEST_DOMAIN = "test"


class MockFlow(ConfigFlow):
    """Test flow."""


@pytest.fixture(autouse=True)
def config_flow_fixture(hass: HomeAssistant) -> Generator[None, None, None]:
    """Mock config flow."""
    mock_platform(hass, f"{TEST_DOMAIN}.config_flow")

    with mock_config_flow(TEST_DOMAIN, MockFlow):
        yield


async def test_deprecated_base_class(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test warnings when adding VacuumEntity to the state machine."""

    async def async_setup_entry_init(
        hass: HomeAssistant, config_entry: ConfigEntry
    ) -> bool:
        """Set up test config entry."""
        await hass.config_entries.async_forward_entry_setup(config_entry, VACUUM_DOMAIN)
        return True

    mock_platform(hass, f"{TEST_DOMAIN}.config_flow")
    mock_integration(
        hass,
        MockModule(
            TEST_DOMAIN,
            async_setup_entry=async_setup_entry_init,
        ),
    )

    entity1 = VacuumEntity()
    entity1.entity_id = "vacuum.test1"

    async def async_setup_entry_platform(
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        async_add_entities: AddEntitiesCallback,
    ) -> None:
        """Set up test stt platform via config entry."""
        async_add_entities([entity1])

    mock_platform(
        hass,
        f"{TEST_DOMAIN}.{VACUUM_DOMAIN}",
        MockPlatform(async_setup_entry=async_setup_entry_platform),
    )

    config_entry = MockConfigEntry(domain=TEST_DOMAIN)
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get(entity1.entity_id)

    assert (
        "test::VacuumEntity is extending the deprecated base class VacuumEntity"
        in caplog.text
    )

    issue_registry = ir.async_get(hass)
    issue = issue_registry.async_get_issue(
        VACUUM_DOMAIN, f"deprecated_vacuum_base_class_{TEST_DOMAIN}"
    )
    assert issue.issue_domain == TEST_DOMAIN
