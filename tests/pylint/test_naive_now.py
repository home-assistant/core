"""Tests for the home-assistant-enforce-naive-now checker."""

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

        now = dt_util.naive_now()
        """,
            id="naive_now_helper",
        ),
        pytest.param(
            # An aware ``datetime`` with a non-UTC time zone is handled by the
            # ``enforce-now`` checker.
            """
        from datetime import datetime
        from zoneinfo import ZoneInfo

        now = datetime.now(ZoneInfo("Europe/Stockholm"))
        """,
            id="now_with_other_tz",
        ),
        pytest.param(
            # The UTC case is handled by the ``enforce-utcnow`` checker.
            """
        from datetime import datetime, UTC

        now = datetime.now(UTC)
        """,
            id="now_with_utc",
        ),
        pytest.param(
            # A time zone passed in as a variable is still aware.
            """
        from datetime import datetime, tzinfo

        def get_now(time_zone: tzinfo) -> datetime:
            return datetime.now(time_zone)
        """,
            id="variable_tz",
        ),
        pytest.param(
            # Calling ``.now`` on something that is not ``datetime.datetime``
            # must not be flagged.
            """
        class Counter:
            def now(self):
                return 0

        Counter().now()
        """,
            id="other_now_method",
        ),
    ],
)
def test_enforce_naive_now_good(
    linter: UnittestLinter,
    enforce_naive_now_checker: BaseChecker,
    code: str,
) -> None:
    """Good test cases -- no message expected."""
    root_node = astroid.parse(code, "homeassistant.components.pylint_test")
    walker = ASTWalker(linter)
    walker.add_checker(enforce_naive_now_checker)

    with assert_no_messages(linter):
        walker.walk(root_node)


@pytest.mark.parametrize(
    "code",
    [
        pytest.param(
            """
        from datetime import datetime

        now = datetime.now()
        """,
            id="from_import_datetime",
        ),
        pytest.param(
            """
        import datetime

        now = datetime.datetime.now()
        """,
            id="qualified_datetime",
        ),
        pytest.param(
            """
        import datetime as dt

        now = dt.datetime.now()
        """,
            id="aliased_datetime",
        ),
        pytest.param(
            # ``None`` (positional) returns a naive ``datetime``.
            """
        from datetime import datetime

        now = datetime.now(None)
        """,
            id="explicit_none",
        ),
        pytest.param(
            # ``tz=None`` returns a naive ``datetime``.
            """
        from datetime import datetime

        now = datetime.now(tz=None)
        """,
            id="kwarg_none",
        ),
        pytest.param(
            # The ``datetime`` class reached through ``homeassistant.util.dt``
            # (which does ``import datetime as dt``) is still the stdlib class.
            """
        from homeassistant.util import dt as dt_util

        now = dt_util.dt.datetime.now()
        """,
            id="util_dt_datetime_class",
        ),
        pytest.param(
            """
        import homeassistant.util.dt as dt_util

        now = dt_util.dt.datetime.now()
        """,
            id="import_util_dt_datetime_class",
        ),
        pytest.param(
            """
        from homeassistant.util.dt import dt

        now = dt.datetime.now()
        """,
            id="from_util_dt_import_dt",
        ),
    ],
)
def test_enforce_naive_now_bad(
    linter: UnittestLinter,
    enforce_naive_now_checker: BaseChecker,
    code: str,
) -> None:
    """Bad test cases -- one message expected per call."""
    root_node = astroid.parse(code, "homeassistant.components.pylint_test")
    walker = ASTWalker(linter)
    walker.add_checker(enforce_naive_now_checker)

    walker.walk(root_node)
    messages = linter.release_messages()
    assert len(messages) == 1
    assert messages[0].msg_id == "home-assistant-enforce-naive-now"


@pytest.mark.parametrize(
    "code",
    [
        pytest.param(
            """
        from datetime import datetime

        naive_now = datetime.now()
        """,
            id="from_import_datetime",
        ),
        pytest.param(
            # The form actually used in ``homeassistant/util/dt.py``.
            """
        import datetime as dt

        def naive_now() -> dt.datetime:
            return dt.datetime.now()
        """,
            id="util_dt_source_form",
        ),
    ],
)
def test_enforce_naive_now_skips_util_dt(
    linter: UnittestLinter,
    enforce_naive_now_checker: BaseChecker,
    code: str,
) -> None:
    """``homeassistant.util.dt`` defines ``naive_now`` itself, so it is skipped."""
    root_node = astroid.parse(code, "homeassistant.util.dt")
    walker = ASTWalker(linter)
    walker.add_checker(enforce_naive_now_checker)

    with assert_no_messages(linter):
        walker.walk(root_node)
