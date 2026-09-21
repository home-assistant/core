from pathlib import Path
p = Path("homeassistant/components/recorder/core.py")
t = p.read_text()
old1 = (
    "            # InterfaceError is a DBAPIError, not a DatabaseError.\n"
    "            if isinstance(\n"
    "                err, (exc.InterfaceError, exc.OperationalError, exc.InternalError)\n"
    "            ):"
)
new1 = (
    "            # InterfaceError is a DBAPIError, not a DatabaseError. Only reconnect\n"
    "            # when SQLAlchemy marked the connection invalidated; OperationalError\n"
    "            # / InternalError also cover locks, deadlocks, and disk-full on a\n"
    "            # live connection, which must keep using _reopen_event_session().\n"
    "            if (\n"
    "                isinstance(\n"
    "                    err, (exc.InterfaceError, exc.OperationalError, exc.InternalError)\n"
    "                )\n"
    "                and err.connection_invalidated\n"
    "            ):"
)
old2 = (
    "    def _reconnect_database(self) -> None:\n"
    '        """Reconnect after a mid-session connection failure.\n'
    "\n"
    "        Startup uses a finite retry budget so a missing or misconfigured\n"
    "        database does not block Home Assistant forever. After the recorder\n"
    "        has already been running, keep retrying until the database is\n"
    "        reachable again or Home Assistant is stopping.\n"
    '        """'
)
new2 = (
    "    def _reconnect_database(self) -> None:\n"
    '        """Reconnect after a mid-session invalidated connection.\n'
    "\n"
    "        Startup uses a finite retry budget so a missing or misconfigured\n"
    "        database does not block Home Assistant forever. After the recorder\n"
    "        has already been running, keep retrying until the database is\n"
    "        reachable again or Home Assistant is stopping. Duration is\n"
    "        intentionally unbounded: capping would reintroduce a recorder that\n"
    "        stays down until Home Assistant restarts (#180041). Queue growth\n"
    "        during the wait is already bounded by `_reached_max_backlog()` /\n"
    "        the backlog watcher, which stops `_event_listener`; on success\n"
    "        `_finish_reconnect_attempt()` re-binds it when needed.\n"
    '        """'
)
assert old1 in t, "old1 missing"
assert old2 in t, "old2 missing"
t = t.replace(old1, new1, 1).replace(old2, new2, 1)
p.write_text(t)
assert "and err.connection_invalidated" in t
assert "intentionally unbounded" in t
assert p.stat().st_size > 60000
print("ok", p.stat().st_size)
