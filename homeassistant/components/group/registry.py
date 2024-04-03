"""Provide the functionality to group entities."""

from __future__ import annotations

from contextvars import ContextVar
from typing import Protocol

from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.integration_platform import (
    async_process_integration_platforms,
)

from .const import DOMAIN, REG_KEY

current_domain: ContextVar[str] = ContextVar("current_domain")


async def async_setup(hass: HomeAssistant) -> None:
    """Set up the Group integration registry of integration platforms."""
    hass.data[REG_KEY] = GroupIntegrationRegistry()

    await async_process_integration_platforms(
        hass, DOMAIN, _process_group_platform, wait_for_platforms=True
    )


class GroupProtocol(Protocol):
    """Define the format of group platforms."""

    def async_describe_on_off_states(
        self, hass: HomeAssistant, registry: GroupIntegrationRegistry
    ) -> None:
        """Describe group on off states."""


@callback
def _process_group_platform(
    hass: HomeAssistant, domain: str, platform: GroupProtocol
) -> None:
    """Process a group platform."""
    current_domain.set(domain)
    registry: GroupIntegrationRegistry = hass.data[REG_KEY]
    platform.async_describe_on_off_states(hass, registry)


class GroupIntegrationRegistry:
    """Class to hold a registry of integrations."""

    on_off_mapping: dict[str, str] = {STATE_ON: STATE_OFF}
    off_on_mapping: dict[str, str] = {STATE_OFF: STATE_ON}
    on_states_by_domain: dict[str, set] = {}
    exclude_domains: set = set()

    def exclude_domain(self) -> None:
        """Exclude the current domain."""
        self.exclude_domains.add(current_domain.get())

    def on_off_states(self, on_states: set, off_state: str) -> None:
        """Register on and off states for the current domain."""
        for on_state in on_states:
            if on_state not in self.on_off_mapping:
                self.on_off_mapping[on_state] = off_state

        if len(on_states) == 1 and off_state not in self.off_on_mapping:
            self.off_on_mapping[off_state] = list(on_states)[0]

        self.on_states_by_domain[current_domain.get()] = set(on_states)
