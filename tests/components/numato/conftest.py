"""Fixtures for numato tests."""

from copy import deepcopy

import pytest

from homeassistant.components import numato

from . import numato_mock
from .common import NUMATO_CFG


@pytest.fixture
def config():
    """Provide a copy of the numato domain's test configuration.

    This helps to quickly change certain aspects of the configuration scoped
    to each individual test.
    """
    return deepcopy(NUMATO_CFG)


@pytest.fixture
def numato_fixture(monkeypatch):
    """Inject the numato mockup into numato homeassistant module."""
    module_mock = numato_mock.NumatoModuleMock()
    monkeypatch.setattr(numato, "gpio", module_mock)
    return module_mock
