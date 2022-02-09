from typing import Any, List, Optional

class OptionsConverter:
    @property
    def options(self) -> List[str]:
        return []
    def from_option_string(self, value: str) -> Any:
        return value
    def to_option_string(self, value: Any) -> Optional[str]:
        return str(value)
