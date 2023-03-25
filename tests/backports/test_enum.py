"""Test Home Assistant enum utils."""

from enum import auto

import pytest

from homeassistant.backports.enum import StrEnum


def test_strenum() -> None:
    """Test StrEnum."""

    class TestEnum(StrEnum):
        Test = "test"

    assert str(TestEnum.Test) == "test"
    assert TestEnum.Test == "test"
    assert TestEnum("test") is TestEnum.Test
    assert TestEnum(TestEnum.Test) is TestEnum.Test

    with pytest.raises(ValueError):
        TestEnum(42)

    with pytest.raises(ValueError):
        TestEnum("str but unknown")

    with pytest.raises(TypeError):

        class FailEnum(StrEnum):
            Test = 42

    with pytest.raises(TypeError):

        class FailEnum2(StrEnum):
            Test = auto()
