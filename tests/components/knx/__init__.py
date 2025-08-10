"""Tests for the KNX integration."""

from collections.abc import Callable, Coroutine
from typing import Any

from homeassistant.helpers import entity_registry as er

type KnxEntityGenerator = Callable[..., Coroutine[Any, Any, er.RegistryEntry]]
