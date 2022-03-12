"""SamsungTV Encrypted."""
# flake8: noqa
# pylint: disable=[missing-class-docstring,missing-function-docstring]
from __future__ import annotations

import json
from typing import Any


class SamsungTVEncryptedCommand:
    def __init__(self, method: str, body: dict[str, Any]) -> None:
        self.method = method
        self.body = body

    def as_dict(self) -> dict[str, Any]:
        return {
            "method": self.method,
            "body": self.body,
        }

    def get_payload(self) -> str:
        return json.dumps(self.as_dict())


class SamsungTVEncryptedPostCommand(SamsungTVEncryptedCommand):
    def __init__(self, body: dict[str, Any]) -> None:
        super().__init__("POST", body)
