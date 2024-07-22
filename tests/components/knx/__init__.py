"""Tests for the KNX integration."""

from collections.abc import Awaitable, Callable

from homeassistant.helpers import entity_registry as er

KnxEntityGenerator = Callable[..., Awaitable[er.RegistryEntry]]
