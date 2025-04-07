"""Fixtures for numato tests."""

from copy import deepcopy
from typing import Any

import pytest

from homeassistant.components import numato

from .common import NUMATO_CFG
from .numato_mock import NumatoModuleMock


@pytest.fixture
def config() -> dict[str, Any]:
    """Provide a copy of the numato domain's test configuration.

    This helps to quickly change certain aspects of the configuration scoped
    to each individual test.
    """
    return deepcopy(NUMATO_CFG)


@pytest.fixture
def numato_fixture(monkeypatch: pytest.MonkeyPatch) -> NumatoModuleMock:
    """Inject the numato mockup into numato homeassistant module."""
    module_mock = NumatoModuleMock()
    monkeypatch.setattr(numato, "gpio", module_mock)
    return module_mock
