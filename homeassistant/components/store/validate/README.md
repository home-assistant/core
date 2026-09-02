# Repository validation

This is where the validation rules that run against the various repository categories live.

## Structure

- There is one file pr. rule.
- All rule needs tests to verify every possible outcome for the rule.
- It's better with multiple files than a big rule.
- All rules uses `ActionValidationBase` as the base class.
- Only use `validate` or `async_validate` methods to define validation rules.
- If a rule should fail, raise `ValidationException` with the failure message.


## Example

```python
from .base import (
    ActionValidationBase,
    ValidationBase,
    ValidationException,
)

class SuperAwesomeRepository(ActionValidationBase):
    category = "integration"

    async def async_validate(self):
        if self.repository != "super-awesome":
            raise ValidationException("The repository is not super-awesome")
```