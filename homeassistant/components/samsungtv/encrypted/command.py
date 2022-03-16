"""SamsungTV Encrypted."""
import json
from typing import Any, Dict


class SamsungTVEncryptedCommand:
    def __init__(self, method: str, body: Dict[str, Any]) -> None:
        self.method = method
        self.body = body

    def as_dict(self) -> Dict[str, Any]:
        return {
            "method": self.method,
            "body": self.body,
        }

    def get_payload(self) -> str:
        return json.dumps(self.as_dict())


class SamsungTVEncryptedPostCommand(SamsungTVEncryptedCommand):
    def __init__(self, body: Dict[str, Any]) -> None:
        super().__init__("POST", body)
