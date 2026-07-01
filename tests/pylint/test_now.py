"""Tests for the home-assistant-enforce-now checker."""

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

        now = dt_util.now()
        """,
            id="now_helper",
        ),
        pytest.param(
            # Calling ``datetime.now()`` with no argument returns naive local
            # time, which is not equivalent to ``dt_util.now()``.
            """
        from datetime import datetime

        now = datetime.now()
        """,
            id="now_no_args",
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
            """
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc)
        """,
            id="now_with_timezone_utc",
        ),
        pytest.param(
            """
        import datetime

        now = datetime.datetime.now(datetime.UTC)
        """,
            id="qualified_now_with_utc",
        ),
        pytest.param(
            """
        from datetime import datetime
        from zoneinfo import ZoneInfo

        now = datetime.now(ZoneInfo("UTC"))
        """,
            id="now_with_zoneinfo_utc",
        ),
        pytest.param(
            """
        from datetime import datetime, UTC

        now = datetime.now(tz=UTC)
        """,
            id="kwarg_now_with_utc",
        ),
        pytest.param(
            # ``UTC`` re-exported from ``homeassistant.util.dt`` is still the
            # UTC case, handled by the ``enforce-utcnow`` checker.
            """
        import datetime

        from homeassistant.util import dt as dt_util

        now = datetime.datetime.now(dt_util.UTC)
        """,
            id="dt_util_utc",
        ),
        pytest.param(
            """
        import datetime

        from homeassistant.util import dt as dt_util

        now = datetime.datetime.now(tz=dt_util.UTC)
        """,
            id="kwarg_dt_util_utc",
        ),
        pytest.param(
            """
        from datetime import datetime
        from homeassistant.util.dt import UTC

        now = datetime.now(UTC)
        """,
            id="from_util_dt_import_utc",
        ),
        pytest.param(
            """
        import datetime

        import homeassistant.util.dt as dt_util

        now = datetime.datetime.now(dt_util.UTC)
        """,
            id="import_util_dt_as_dt_util_utc",
        ),
        pytest.param(
            # Calling ``.now`` on something that is not ``datetime.datetime``
            # must not be flagged.
            """
        from zoneinfo import ZoneInfo

        class Counter:
            def now(self, tz):
                return 0

        Counter().now(ZoneInfo("Europe/Stockholm"))
        """,
            id="other_now_method",
        ),
    ],
)
def test_enforce_now_good(
    linter: UnittestLinter,
    enforce_now_checker: BaseChecker,
    code: str,
) -> None:
    """Good test cases -- no message expected."""
    root_node = astroid.parse(code, "homeassistant.components.pylint_test")
    walker = ASTWalker(linter)
    walker.add_checker(enforce_now_checker)

    with assert_no_messages(linter):
        walker.walk(root_node)


@pytest.mark.parametrize(
    "code",
    [
        pytest.param(
            """
        from datetime import datetime
        from zoneinfo import ZoneInfo

        now = datetime.now(ZoneInfo("Europe/Stockholm"))
        """,
            id="from_import_zoneinfo",
        ),
        pytest.param(
            """
        from datetime import datetime
        from zoneinfo import ZoneInfo

        now = datetime.now(tz=ZoneInfo("Europe/Stockholm"))
        """,
            id="kwarg_zoneinfo",
        ),
        pytest.param(
            """
        import datetime
        import zoneinfo

        now = datetime.datetime.now(zoneinfo.ZoneInfo("Europe/Stockholm"))
        """,
            id="qualified_datetime",
        ),
        pytest.param(
            """
        import datetime as dt
        from zoneinfo import ZoneInfo

        now = dt.datetime.now(ZoneInfo("Europe/Stockholm"))
        """,
            id="aliased_datetime",
        ),
        pytest.param(
            # A time zone passed in as a variable is still flagged.
            """
        from datetime import datetime, tzinfo

        def get_now(time_zone: tzinfo) -> datetime:
            return datetime.now(time_zone)
        """,
            id="variable_tz",
        ),
        pytest.param(
            """
        from datetime import datetime, tzinfo

        def get_now(time_zone: tzinfo) -> datetime:
            return datetime.now(tz=time_zone)
        """,
            id="kwarg_variable_tz",
        ),
        pytest.param(
            # The ``datetime`` class reached through ``homeassistant.util.dt``
            # (which does ``import datetime as dt``) is still the stdlib class.
            """
        from homeassistant.util import dt as dt_util
        from zoneinfo import ZoneInfo

        now = dt_util.dt.datetime.now(ZoneInfo("Europe/Stockholm"))
        """,
            id="util_dt_datetime_class",
        ),
        pytest.param(
            """
        import homeassistant.util.dt as dt_util
        from zoneinfo import ZoneInfo

        now = dt_util.dt.datetime.now(ZoneInfo("Europe/Stockholm"))
        """,
            id="import_util_dt_datetime_class",
        ),
    ],
)
def test_enforce_now_bad(
    linter: UnittestLinter,
    enforce_now_checker: BaseChecker,
    code: str,
) -> None:
    """Bad test cases -- one message expected per call."""
    root_node = astroid.parse(code, "homeassistant.components.pylint_test")
    walker = ASTWalker(linter)
    walker.add_checker(enforce_now_checker)

    walker.walk(root_node)
    messages = linter.release_messages()
    assert len(messages) == 1
    assert messages[0].msg_id == "home-assistant-enforce-now"


@pytest.mark.parametrize(
    "code",
    [
        pytest.param(
            """
        from datetime import datetime
        from zoneinfo import ZoneInfo

        now = datetime.now(ZoneInfo("Europe/Stockholm"))
        """,
            id="from_import_datetime",
        ),
        pytest.param(
            # The form actually used in ``homeassistant/util/dt.py``.
            """
        import datetime as dt

        def now(time_zone: dt.tzinfo | None = None) -> dt.datetime:
            return dt.datetime.now(time_zone or DEFAULT_TIME_ZONE)
        """,
            id="util_dt_source_form",
        ),
    ],
)
def test_enforce_now_skips_util_dt(
    linter: UnittestLinter,
    enforce_now_checker: BaseChecker,
    code: str,
) -> None:
    """``homeassistant.util.dt`` defines ``now`` itself, so it is skipped."""
    root_node = astroid.parse(code, "homeassistant.util.dt")
    walker = ASTWalker(linter)
    walker.add_checker(enforce_now_checker)

    with assert_no_messages(linter):
        walker.walk(root_node)
