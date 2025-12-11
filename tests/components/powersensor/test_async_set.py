"""Tests related to homeassistant.components.AsyncSet (an Async Locked set)."""

import pytest
import pytest_asyncio

from homeassistant.components.powersensor.AsyncSet import AsyncSet


class MockLock:
    """Helper to count lock enter/exit calls.

    AsyncMock was no help due to the weird way python handles "async with",
    ignoring the lock instance and instead looking up __aenter__/__aexit__ on
    the class. As such, we resort to class variables and careful resetting of
    those in fixtures.
    """

    aenter = 0
    aexit = 0

    async def __aenter__(self):
        """Increment the `aenter` counter and return self."""
        MockLock.aenter += 1

    async def __aexit__(self, typ, exc, tb):
        """Increment the `aexit` counter."""
        MockLock.aexit += 1

    @staticmethod
    def reset():
        """Reset the `aenter` and `aexit` counters to zero."""
        MockLock.aenter = 0
        MockLock.aexit = 0

    @staticmethod
    def expect_called(call_count):
        """Assert that both `__aenter__` and `__aexit__` have been called the specified number of times.

        Args:
            call_count (int): The expected number of calls to both `__aenter__` and `__aexit__`.

        Raises:
            AssertionError: If either `__aenter__` or `__aexit__` has not been called the expected number of times.
        """
        assert MockLock.aenter == call_count
        assert MockLock.aexit == call_count


### Fixtures #############################################


@pytest.fixture
def mocklocked_asyncset(monkeypatch: pytest.MonkeyPatch):
    """Provide a fixture that returns an instance of `AsyncSet` with its `_lock` attribute replaced by a `MockLock`."""

    MockLock.reset()
    a = AsyncSet()
    monkeypatch.setattr(a, "_lock", MockLock())
    return a


@pytest_asyncio.fixture
async def preset(mocklocked_asyncset):
    """Provide a fixture that sets up an instance of `AsyncSet` with predefined values and asserts lock calls.

    This fixture takes the `mocklocked_asyncset` fixture as input, adds several values to the `AsyncSet`, and then
    asserts that the `_lock` attribute has been entered and exited the expected number of times. Finally, it resets
    the lock counters and returns the modified instance of `AsyncSet`.

    Yields:
        AsyncSet: An instance of `AsyncSet` with predefined values added and lock calls asserted.

    Raises:
        AssertionError: If the `_lock` attribute has not been entered and exited the expected number of times.
    """
    a = mocklocked_asyncset
    for v in (1, 2, 3, 5, 8, 11):
        await a.add(v)
    a._lock.expect_called(6)
    MockLock.reset()
    return a


### Tests ################################################


@pytest.mark.asyncio
async def test_basics(mocklocked_asyncset) -> None:
    """Test basic functionality of the AsyncSet.

    This test checks that values can be added to the `AsyncSet` and retrieved correctly. It also verifies that
    the `_lock` attribute has been entered and exited the expected number of times after adding the values.

    Raises:
        AssertionError: If any assertions fail, indicating a problem with the AsyncSet or lock behavior.
    """
    a = mocklocked_asyncset
    await a.add(1)
    await a.add(3)

    assert 1 in a
    assert 2 not in a
    assert 3 in a
    assert len(a) == 2
    a._lock.expect_called(2)


@pytest.mark.asyncio
async def test_discard(preset) -> None:
    """Test the `discard` method of the AsyncSet.

    This test checks that values can be discarded from the `AsyncSet` and that the presence of those values is
    correctly updated. It also verifies that the `_lock` attribute has been entered and exited the expected number of times after discarding a value.

    Raises:
        AssertionError: If any assertions fail, indicating a problem with the AsyncSet or lock behavior.
    """
    assert 3 in preset
    await preset.discard(3)
    assert 3 not in preset
    preset._lock.expect_called(1)


@pytest.mark.asyncio
async def test_discard_missing(preset) -> None:
    """Test discarding a missing value from the AsyncSet.

    This test checks that attempting to discard a non-existent value from the `AsyncSet` does not raise an error
    and that the `_lock` attribute has been entered and exited the expected number of times.

    Raises:
        AssertionError: If any assertions fail, indicating a problem with the AsyncSet or lock behavior.
    """

    assert 31 not in preset, "Value 31 should not be in the set before discarding"
    await preset.discard(31)  # Attempt to discard a non-existent value
    preset._lock.expect_called(1)  # Assert that _lock was entered and exited 1 time


@pytest.mark.asyncio
async def test_remove(preset) -> None:
    """Test the `remove` method of the AsyncSet.

    This test checks that values can be removed from the `AsyncSet` and that the presence of those values is
    correctly updated. It also verifies that the `_lock` attribute has been entered and exited the expected number of times after removing a value.

    Raises:
        AssertionError: If any assertions fail, indicating a problem with the AsyncSet or lock behavior.
    """

    assert 5 in preset, "Value 5 should be in the set before removal"
    await preset.remove(5)  # Remove value 5 from the AsyncSet
    assert 5 not in preset, "Value 5 should not be in the set after removal"

    preset._lock.expect_called(1)  # Assert that _lock was entered and exited 1 time


@pytest.mark.asyncio
async def test_remove_missing(preset) -> None:
    """Test removing a missing value from the AsyncSet.

    This test checks that attempting to remove a non-existent value from the `AsyncSet` raises a `KeyError`
    and that the `_lock` attribute has been entered and exited the expected number of times.

    Raises:
        AssertionError: If any assertions fail, indicating a problem with the AsyncSet or lock behavior.
    """

    assert 51 not in preset, "Value 51 should not be in the set before removal"
    with pytest.raises(KeyError):
        await preset.remove(51)  # Attempt to remove a non-existent value
    preset._lock.expect_called(1)  # Assert that _lock was entered and exited 1 time


@pytest.mark.asyncio
async def test_pop(preset) -> None:
    """Test the `pop` method of the AsyncSet.

    This test checks that values can be popped from the `AsyncSet`, and that both the presence of those values
    and the length of the set are correctly updated. It also verifies that the `_lock` attribute has been entered and exited the expected number of times after popping a value.

    Raises:
        AssertionError: If any assertions fail, indicating a problem with the AsyncSet or lock behavior.
    """

    length_of_preset = len(preset)  # Get the current length of the set
    x = await preset.pop()  # Pop a value from the set

    assert x not in preset, "The popped value should no longer be in the set"
    assert len(preset) == length_of_preset - 1, (
        "The length of the set should be one less after popping"
    )

    preset._lock.expect_called(1)  # Assert that _lock was entered and exited 1 time


@pytest.mark.asyncio
async def test_clear(preset) -> None:
    """Test the `clear` method of the AsyncSet.

    This test checks that all values can be cleared from the `AsyncSet`, and that the length of the set is correctly updated to zero.
    It also verifies that the `_lock` attribute has been entered and exited the expected number of times after clearing the set.

    Raises:
        AssertionError: If any assertions fail, indicating a problem with the AsyncSet or lock behavior.
    """

    assert len(preset) > 0, "The set should not be empty before clearing"
    await preset.clear()  # Clear all values from the set

    assert len(preset) == 0, "The length of the set should be zero after clearing"

    preset._lock.expect_called(1)  # Assert that _lock was entered and exited 1 time


@pytest.mark.asyncio
async def test_copy(preset) -> None:
    """Test the `clear` method of the AsyncSet.

    This test checks that all values can be cleared from the `AsyncSet`, and that the length of the set is correctly updated to zero.
    It also verifies that the `_lock` attribute has been entered and exited the expected number of times after clearing the set.

    Raises:
        AssertionError: If any assertions fail, indicating a problem with the AsyncSet or lock behavior.
    """

    assert len(preset) > 0, "The set should not be empty before clearing"
    await preset.clear()  # Clear all values from the set

    assert len(preset) == 0, "The length of the set should be zero after clearing"

    preset._lock.expect_called(1)  # Assert that _lock was entered and exited 1 time


def test_empty(preset) -> None:
    """Test the behavior of an empty `AsyncSet`.

    This test checks that a non-empty `AsyncSet` is truthy, and an empty `AsyncSet` is falsy.

    Raises:
        AssertionError: If any assertions fail, indicating a problem with the AsyncSet's implementation.
    """

    assert preset, "A non-empty set should be truthy"
    assert not AsyncSet(), "An empty set should be falsy"
