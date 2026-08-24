"""Test the freezegun modifications in tests.patch_time."""

from collections.abc import Generator
import datetime
import sys
import types

from freezegun import freeze_time
import pytest


@pytest.fixture
def lazy_module() -> Generator[types.ModuleType]:
    """Register a module which only resolves its attributes when they are read."""
    module = types.ModuleType("freezegun_lazy_module")
    module.probed = []

    def module_getattr(name: str) -> object:
        module.probed.append(name)
        raise AttributeError(name)

    module.__getattr__ = module_getattr
    module.__dir__ = lambda: ["lazy_attribute"]

    sys.modules[module.__name__] = module
    yield module
    del sys.modules[module.__name__]


def test_freezing_time_does_not_resolve_lazy_attributes(
    lazy_module: types.ModuleType,
) -> None:
    """Test freezing time does not read attributes which are not set yet."""
    with freeze_time("2023-01-01"):
        pass

    assert lazy_module.probed == []


def test_freezing_time_rescans_a_changed_module(
    lazy_module: types.ModuleType,
) -> None:
    """Test an attribute set after the first freeze is patched by the next one."""
    real_datetime = datetime.datetime

    with freeze_time("2023-01-01"):
        pass

    lazy_module.datetime = real_datetime

    with freeze_time("2023-01-01"):
        assert lazy_module.datetime is not real_datetime
        assert lazy_module.datetime.now() == real_datetime(2023, 1, 1)

    assert lazy_module.datetime is real_datetime
