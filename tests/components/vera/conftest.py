"""Fixtures for tests."""

from mock import patch
import pytest

from .common import ComponentFactory


@pytest.fixture()
def vera_component_factory(request):
    """Return a factory for initializing the vera component."""
    init_controller_patch = patch("pyvera.init_controller")
    init_controller_mock = init_controller_patch.start()

    def fin():
        nonlocal init_controller_patch
        init_controller_patch.stop()

    request.addfinalizer(fin)

    return ComponentFactory(init_controller_mock)
