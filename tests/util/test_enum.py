"""Test Home Assistant enum utils."""

import pytest

from homeassistant.util.enum import StrEnum


def test_strenum():
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
