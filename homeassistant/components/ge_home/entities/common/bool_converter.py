from typing import Any

from gehomesdk import ErdOnOff

class BoolConverter:
    def boolify(self, value: Any) -> bool:
        return bool(value)
    def true_value(self) -> Any:
        return True
    def false_value(self) -> Any:
        return False

class ErdOnOffBoolConverter(BoolConverter):
    def boolify(self, value: ErdOnOff) -> bool:
        return value.boolify()
    def true_value(self) -> Any:
        return ErdOnOff.ON
    def false_value(self) -> Any:
        return ErdOnOff.OFF