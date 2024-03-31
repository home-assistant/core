"""Test Home Assistant util methods."""

from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from homeassistant import util
import homeassistant.util.dt as dt_util


def test_raise_if_invalid_filename() -> None:
    """Test raise_if_invalid_filename."""
    assert util.raise_if_invalid_filename("test") is None

    with pytest.raises(ValueError):
        util.raise_if_invalid_filename("/test")

    with pytest.raises(ValueError):
        util.raise_if_invalid_filename("..test")

    with pytest.raises(ValueError):
        util.raise_if_invalid_filename("\\test")

    with pytest.raises(ValueError):
        util.raise_if_invalid_filename("\\../test")


def test_raise_if_invalid_path() -> None:
    """Test raise_if_invalid_path."""
    assert util.raise_if_invalid_path("test/path") is None

    with pytest.raises(ValueError):
        assert util.raise_if_invalid_path("~test/path")

    with pytest.raises(ValueError):
        assert util.raise_if_invalid_path("~/../test/path")


def test_slugify() -> None:
    """Test slugify."""
    assert util.slugify("T-!@#$!#@$!$est") == "t_est"
    assert util.slugify("Test More") == "test_more"
    assert util.slugify("Test_(More)") == "test_more"
    assert util.slugify("Tèst_Mörê") == "test_more"
    assert util.slugify("B8:27:EB:00:00:00") == "b8_27_eb_00_00_00"
    assert util.slugify("test.com") == "test_com"
    assert util.slugify("greg_phone - exp_wayp1") == "greg_phone_exp_wayp1"
    assert (
        util.slugify("We are, we are, a... Test Calendar")
        == "we_are_we_are_a_test_calendar"
    )
    assert util.slugify("Tèst_äöüß_ÄÖÜ") == "test_aouss_aou"
    assert util.slugify("影師嗎") == "ying_shi_ma"
    assert util.slugify("けいふぉんと") == "keihuonto"
    assert util.slugify("$") == "unknown"
    assert util.slugify("Ⓐ") == "a"
    assert util.slugify("ⓑ") == "b"
    assert util.slugify("$$$") == "unknown"
    assert util.slugify("$something") == "something"
    assert util.slugify("") == ""
    assert util.slugify(None) == ""


def test_repr_helper() -> None:
    """Test repr_helper."""
    assert util.repr_helper("A") == "A"
    assert util.repr_helper(5) == "5"
    assert util.repr_helper(True) == "True"
    assert util.repr_helper({"test": 1}) == "test=1"

    tz = dt_util.get_time_zone("Europe/Copenhagen")
    with patch("homeassistant.util.dt.DEFAULT_TIME_ZONE", tz):
        assert (
            util.repr_helper(datetime(1986, 7, 9, 12, 0, 0))
            == "1986-07-09T12:00:00+02:00"
        )


def test_convert() -> None:
    """Test convert."""
    assert util.convert("5", int) == 5
    assert util.convert("5", float) == 5.0
    assert util.convert("True", bool) is True
    assert util.convert("NOT A NUMBER", int, 1) == 1
    assert util.convert(None, int, 1) == 1
    assert util.convert(object, int, 1) == 1


def test_ensure_unique_string() -> None:
    """Test ensure_unique_string."""
    assert util.ensure_unique_string("Beer", ["Beer", "Beer_2"]) == "Beer_3"
    assert util.ensure_unique_string("Beer", ["Wine", "Soda"]) == "Beer"


def test_throttle() -> None:
    """Test the add cooldown decorator."""
    calls1 = []
    calls2 = []

    @util.Throttle(timedelta(seconds=4))
    def test_throttle1():
        calls1.append(1)

    @util.Throttle(timedelta(seconds=4), timedelta(seconds=2))
    def test_throttle2():
        calls2.append(1)

    now = dt_util.utcnow()
    plus3 = now + timedelta(seconds=3)
    plus5 = plus3 + timedelta(seconds=2)

    # Call first time and ensure methods got called
    test_throttle1()
    test_throttle2()

    assert len(calls1) == 1
    assert len(calls2) == 1

    # Call second time. Methods should not get called
    test_throttle1()
    test_throttle2()

    assert len(calls1) == 1
    assert len(calls2) == 1

    # Call again, overriding throttle, only first one should fire
    test_throttle1(no_throttle=True)
    test_throttle2(no_throttle=True)

    assert len(calls1) == 2
    assert len(calls2) == 1

    with patch("homeassistant.util.utcnow", return_value=plus3):
        test_throttle1()
        test_throttle2()

    assert len(calls1) == 2
    assert len(calls2) == 1

    with patch("homeassistant.util.utcnow", return_value=plus5):
        test_throttle1()
        test_throttle2()

    assert len(calls1) == 3
    assert len(calls2) == 2


def test_throttle_per_instance() -> None:
    """Test that the throttle method is done per instance of a class."""

    class Tester:
        """A tester class for the throttle."""

        @util.Throttle(timedelta(seconds=1))
        def hello(self):
            """Test the throttle."""
            return True

    assert Tester().hello()
    assert Tester().hello()


def test_throttle_on_method() -> None:
    """Test that throttle works when wrapping a method."""

    class Tester:
        """A tester class for the throttle."""

        def hello(self):
            """Test the throttle."""
            return True

    tester = Tester()
    throttled = util.Throttle(timedelta(seconds=1))(tester.hello)

    assert throttled()
    assert throttled() is None


def test_throttle_on_two_method() -> None:
    """Test that throttle works when wrapping two methods."""

    class Tester:
        """A test class for the throttle."""

        @util.Throttle(timedelta(seconds=1))
        def hello(self):
            """Test the throttle."""
            return True

        @util.Throttle(timedelta(seconds=1))
        def goodbye(self):
            """Test the throttle."""
            return True

    tester = Tester()

    assert tester.hello()
    assert tester.goodbye()


@patch.object(util, "random")
def test_get_random_string(mock_random) -> None:
    """Test get random string."""
    results = ["A", "B", "C"]

    def mock_choice(choices):
        return results.pop(0)

    generator = MagicMock()
    generator.choice.side_effect = mock_choice
    mock_random.SystemRandom.return_value = generator

    assert util.get_random_string(length=3) == "ABC"


async def test_throttle_async() -> None:
    """Test Throttle decorator with async method."""

    @util.Throttle(timedelta(seconds=2))
    async def test_method():
        """Only first call should return a value."""
        return True

    assert (await test_method()) is True
    assert (await test_method()) is None

    @util.Throttle(timedelta(seconds=2), timedelta(seconds=0.1))
    async def test_method2():
        """Only first call should return a value."""
        return True

    assert (await test_method2()) is True
    assert (await test_method2()) is None
