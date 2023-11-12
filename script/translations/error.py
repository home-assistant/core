"""Errors for translations."""
import json


class ExitApp(Exception):
    """Exception to indicate app should exit."""

    def __init__(self, reason, exit_code=1):
        """Initialize the exit app exception."""
        self.reason = reason
        self.exit_code = exit_code


class JSONDecodeErrorWithPath(json.JSONDecodeError):
    """Subclass of JSONDecodeError with additional properties.

    Additional properties:
      path: Path to the JSON document being parsed
    """

    def __init__(self, msg, doc, pos, path):
        """Initialize."""
        lineno = doc.count("\n", 0, pos) + 1
        colno = pos - doc.rfind("\n", 0, pos)
        errmsg = f"{msg}: file: {path} line {lineno} column {colno} (char {pos})"
        ValueError.__init__(self, errmsg)
        self.msg = msg
        self.doc = doc
        self.pos = pos
        self.lineno = lineno
        self.colno = colno
        self.path = path

    def __reduce__(self):
        """Reduce."""
        return self.__class__, (self.msg, self.doc, self.pos, self.path)
