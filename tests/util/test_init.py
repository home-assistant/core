"""Test Home Assistant util methods."""
import unittest
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta

from homeassistant import util
import homeassistant.util.dt as dt_util
import pytest


class TestUtil(unittest.TestCase):
    """Test util methods."""

    def test_sanitize_filename(self):
        """Test sanitize_filename."""
        assert "test" == util.sanitize_filename("test")
        assert "test" == util.sanitize_filename("/test")
        assert "test" == util.sanitize_filename("..test")
        assert "test" == util.sanitize_filename("\\test")
        assert "test" == util.sanitize_filename("\\../test")

    def test_sanitize_path(self):
        """Test sanitize_path."""
        assert "test/path" == util.sanitize_path("test/path")
        assert "test/path" == util.sanitize_path("~test/path")
        assert "//test/path" == util.sanitize_path("~/../test/path")

    def test_slugify(self):
        """Test slugify."""
        assert "t_est" == util.slugify("T-!@#$!#@$!$est")
        assert "test_more" == util.slugify("Test More")
        assert "test_more" == util.slugify("Test_(More)")
        assert "test_more" == util.slugify("Tèst_Mörê")
        assert "b8_27_eb_00_00_00" == util.slugify("B8:27:EB:00:00:00")
        assert "test_com" == util.slugify("test.com")
        assert "greg_phone_exp_wayp1" == \
            util.slugify("greg_phone - exp_wayp1")
        assert "we_are_we_are_a_test_calendar" == \
            util.slugify("We are, we are, a... Test Calendar")
        assert "test_aouss_aou" == util.slugify("Tèst_äöüß_ÄÖÜ")
        assert "ying_shi_ma" == util.slugify("影師嗎")
        assert "keihuonto" == util.slugify("けいふぉんと")

    def test_repr_helper(self):
        """Test repr_helper."""
        assert "A" == util.repr_helper("A")
        assert "5" == util.repr_helper(5)
        assert "True" == util.repr_helper(True)
        assert "test=1" == util.repr_helper({"test": 1})
        assert "1986-07-09T12:00:00+00:00" == \
            util.repr_helper(datetime(1986, 7, 9, 12, 0, 0))

    def test_convert(self):
        """Test convert."""
        assert 5 == util.convert("5", int)
        assert 5.0 == util.convert("5", float)
        assert util.convert("True", bool) is True
        assert 1 == util.convert("NOT A NUMBER", int, 1)
        assert 1 == util.convert(None, int, 1)
        assert 1 == util.convert(object, int, 1)

    def test_ensure_unique_string(self):
        """Test ensure_unique_string."""
        assert "Beer_3" == \
            util.ensure_unique_string("Beer", ["Beer", "Beer_2"])
        assert "Beer" == \
            util.ensure_unique_string("Beer", ["Wine", "Soda"])

    def test_ordered_enum(self):
        """Test the ordered enum class."""
        class TestEnum(util.OrderedEnum):
            """Test enum that can be ordered."""

            FIRST = 1
            SECOND = 2
            THIRD = 3

        assert TestEnum.SECOND >= TestEnum.FIRST
        assert TestEnum.SECOND >= TestEnum.SECOND
        assert not (TestEnum.SECOND >= TestEnum.THIRD)

        assert TestEnum.SECOND > TestEnum.FIRST
        assert not (TestEnum.SECOND > TestEnum.SECOND)
        assert not (TestEnum.SECOND > TestEnum.THIRD)

        assert not (TestEnum.SECOND <= TestEnum.FIRST)
        assert TestEnum.SECOND <= TestEnum.SECOND
        assert TestEnum.SECOND <= TestEnum.THIRD

        assert not (TestEnum.SECOND < TestEnum.FIRST)
        assert not (TestEnum.SECOND < TestEnum.SECOND)
        assert TestEnum.SECOND < TestEnum.THIRD

        # Python will raise a TypeError if the <, <=, >, >= methods
        # raise a NotImplemented error.
        with pytest.raises(TypeError):
            TestEnum.FIRST < 1

        with pytest.raises(TypeError):
            TestEnum.FIRST <= 1

        with pytest.raises(TypeError):
            TestEnum.FIRST > 1

        with pytest.raises(TypeError):
            TestEnum.FIRST >= 1

    def test_ordered_set(self):
        """Test ordering of set."""
        set1 = util.OrderedSet([1, 2, 3, 4])
        set2 = util.OrderedSet([3, 4, 5])

        assert 4 == len(set1)
        assert 3 == len(set2)

        assert 1 in set1
        assert 2 in set1
        assert 3 in set1
        assert 4 in set1
        assert 5 not in set1

        assert 1 not in set2
        assert 2 not in set2
        assert 3 in set2
        assert 4 in set2
        assert 5 in set2

        set1.add(5)
        assert 5 in set1

        set1.discard(5)
        assert 5 not in set1

        # Try again while key is not in
        set1.discard(5)
        assert 5 not in set1

        assert [1, 2, 3, 4] == list(set1)
        assert [4, 3, 2, 1] == list(reversed(set1))

        assert 1 == set1.pop(False)
        assert [2, 3, 4] == list(set1)

        assert 4 == set1.pop()
        assert [2, 3] == list(set1)

        assert 'OrderedSet()' == str(util.OrderedSet())
        assert 'OrderedSet([2, 3])' == str(set1)

        assert set1 == util.OrderedSet([2, 3])
        assert set1 != util.OrderedSet([3, 2])
        assert set1 == set([2, 3])
        assert set1 == {3, 2}
        assert set1 == [2, 3]
        assert set1 == [3, 2]
        assert set1 != {2}

        set3 = util.OrderedSet(set1)
        set3.update(set2)

        assert [3, 4, 5, 2] == set3
        assert [3, 4, 5, 2] == set1 | set2
        assert [3] == set1 & set2
        assert [2] == set1 - set2

        set1.update([1, 2], [5, 6])
        assert [2, 3, 1, 5, 6] == set1

    def test_throttle(self):
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

        assert 1 == len(calls1)
        assert 1 == len(calls2)

        # Call second time. Methods should not get called
        test_throttle1()
        test_throttle2()

        assert 1 == len(calls1)
        assert 1 == len(calls2)

        # Call again, overriding throttle, only first one should fire
        test_throttle1(no_throttle=True)
        test_throttle2(no_throttle=True)

        assert 2 == len(calls1)
        assert 1 == len(calls2)

        with patch('homeassistant.util.utcnow', return_value=plus3):
            test_throttle1()
            test_throttle2()

        assert 2 == len(calls1)
        assert 1 == len(calls2)

        with patch('homeassistant.util.utcnow', return_value=plus5):
            test_throttle1()
            test_throttle2()

        assert 3 == len(calls1)
        assert 2 == len(calls2)

    def test_throttle_per_instance(self):
        """Test that the throttle method is done per instance of a class."""
        class Tester:
            """A tester class for the throttle."""

            @util.Throttle(timedelta(seconds=1))
            def hello(self):
                """Test the throttle."""
                return True

        assert Tester().hello()
        assert Tester().hello()

    def test_throttle_on_method(self):
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

    def test_throttle_on_two_method(self):
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

    @patch.object(util, 'random')
    def test_get_random_string(self, mock_random):
        """Test get random string."""
        results = ['A', 'B', 'C']

        def mock_choice(choices):
            return results.pop(0)

        generator = MagicMock()
        generator.choice.side_effect = mock_choice
        mock_random.SystemRandom.return_value = generator

        assert util.get_random_string(length=3) == 'ABC'


async def test_throttle_async():
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
