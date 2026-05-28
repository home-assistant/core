"""Tests for the home-assistant-enforce-utcnow checker."""

import astroid
from pylint.checkers import BaseChecker
from pylint.testutils.unittest_linter import UnittestLinter
from pylint.utils.ast_walker import ASTWalker
import pytest

from . import assert_no_messages


@pytest.mark.parametrize(
    "code",
    [
        pytest.param(
            """
        from homeassistant.util import dt as dt_util

        now = dt_util.utcnow()
        """,
            id="utcnow_helper",
        ),
        pytest.param(
            # Calling ``datetime.now()`` with no argument returns local time.
            """
        from datetime import datetime

        now = datetime.now()
        """,
            id="now_no_args",
        ),
        pytest.param(
            # ``now`` with a non-UTC time zone is allowed.
            """
        from datetime import datetime
        from zoneinfo import ZoneInfo

        now = datetime.now(ZoneInfo("Europe/Stockholm"))
        """,
            id="now_with_other_tz",
        ),
        pytest.param(
            # ``tz=`` with a non-UTC time zone is allowed.
            """
        from datetime import datetime
        from zoneinfo import ZoneInfo

        now = datetime.now(tz=ZoneInfo("Europe/Stockholm"))
        """,
            id="now_kwarg_with_other_tz",
        ),
        pytest.param(
            # Calling ``.now`` on something that is not ``datetime.datetime``
            # must not be flagged.
            """
        from datetime import UTC

        class Counter:
            def now(self, tz):
                return 0

        Counter().now(UTC)
        """,
            id="other_now_method",
        ),
    ],
)
def test_enforce_utcnow_good(
    linter: UnittestLinter,
    enforce_utcnow_checker: BaseChecker,
    code: str,
) -> None:
    """Good test cases -- no message expected."""
    root_node = astroid.parse(code, "homeassistant.components.pylint_test")
    walker = ASTWalker(linter)
    walker.add_checker(enforce_utcnow_checker)

    with assert_no_messages(linter):
        walker.walk(root_node)


@pytest.mark.parametrize(
    "code",
    [
        pytest.param(
            """
        from datetime import datetime, UTC

        now = datetime.now(UTC)
        """,
            id="from_import_datetime_utc",
        ),
        pytest.param(
            """
        import datetime

        now = datetime.datetime.now(datetime.UTC)
        """,
            id="qualified_datetime_utc",
        ),
        pytest.param(
            # Combined import exercises the non-``datetime`` branch in
            # ``visit_module`` while still binding ``datetime``.
            """
        import os, datetime

        os.environ
        now = datetime.datetime.now(datetime.UTC)
        """,
            id="combined_import_with_unrelated_module",
        ),
        pytest.param(
            """
        import datetime as dt

        now = dt.datetime.now(dt.UTC)
        """,
            id="aliased_datetime_utc",
        ),
        pytest.param(
            """
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc)
        """,
            id="from_import_datetime_timezone_utc",
        ),
        pytest.param(
            """
        import datetime

        now = datetime.datetime.now(datetime.timezone.utc)
        """,
            id="qualified_datetime_timezone_utc",
        ),
        pytest.param(
            """
        from datetime import datetime, UTC

        now = datetime.now(tz=UTC)
        """,
            id="kwarg_datetime_utc",
        ),
        pytest.param(
            """
        from datetime import datetime, timezone

        now = datetime.now(tz=timezone.utc)
        """,
            id="kwarg_datetime_timezone_utc",
        ),
        pytest.param(
            """
        import datetime

        now = datetime.datetime.now(tz=datetime.UTC)
        """,
            id="kwarg_qualified_datetime_utc",
        ),
        pytest.param(
            """
        from datetime import datetime
        from zoneinfo import ZoneInfo

        now = datetime.now(ZoneInfo("UTC"))
        """,
            id="zoneinfo_utc",
        ),
        pytest.param(
            """
        from datetime import datetime
        from zoneinfo import ZoneInfo

        now = datetime.now(tz=ZoneInfo("UTC"))
        """,
            id="kwarg_zoneinfo_utc",
        ),
    ],
)
def test_enforce_utcnow_bad(
    linter: UnittestLinter,
    enforce_utcnow_checker: BaseChecker,
    code: str,
) -> None:
    """Bad test cases -- one message expected per call."""
    root_node = astroid.parse(code, "homeassistant.components.pylint_test")
    walker = ASTWalker(linter)
    walker.add_checker(enforce_utcnow_checker)

    walker.walk(root_node)
    messages = linter.release_messages()
    assert len(messages) == 1
    assert messages[0].msg_id == "home-assistant-enforce-utcnow"


def test_enforce_utcnow_skips_util_dt(
    linter: UnittestLinter,
    enforce_utcnow_checker: BaseChecker,
) -> None:
    """``homeassistant.util.dt`` defines ``utcnow`` itself, so it is skipped."""
    code = """
        from datetime import datetime, UTC

        utcnow = datetime.now(UTC)
        """
    root_node = astroid.parse(code, "homeassistant.util.dt")
    walker = ASTWalker(linter)
    walker.add_checker(enforce_utcnow_checker)

    with assert_no_messages(linter):
        walker.walk(root_node)
