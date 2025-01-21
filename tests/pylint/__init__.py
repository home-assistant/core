"""Tests for pylint."""

from collections.abc import Generator
import contextlib

from pylint.testutils.unittest_linter import UnittestLinter


@contextlib.contextmanager
def assert_no_messages(
    linter: UnittestLinter, *, ignore_codes: list[str] | None = None
) -> Generator[None]:
    """Assert that no messages are added by the given method."""
    with assert_adds_messages(linter, ignore_codes=ignore_codes):
        yield


@contextlib.contextmanager
def assert_adds_messages(
    linter: UnittestLinter, *messages, ignore_codes: list[str] | None = None
) -> Generator[None]:
    """Assert that exactly the given method adds the given messages.

    The list of messages must exactly match *all* the messages added by the
    method. Additionally, we check to see whether the args in each message can
    actually be substituted into the message string.
    """
    yield
    got = linter.release_messages()
    if ignore_codes:
        got = [msg for msg in got if msg.msg_id not in ignore_codes]
    no_msg = "No message."
    expected = "\n".join(repr(m) for m in messages) or no_msg
    got_str = "\n".join(repr(m) for m in got) or no_msg
    msg = (
        "Expected messages did not match actual.\n"
        f"\nExpected:\n{expected}\n\nGot:\n{got_str}\n"
    )
    assert got == list(messages), msg
