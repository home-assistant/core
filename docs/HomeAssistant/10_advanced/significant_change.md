---
title: "Significant change"
---

Home Assistant doesn't only collect data, it also exports data to various services. Not all of these services are interested in every change. To help these services filter insignificant changes, your entity integration can add significant change support.

This support is added by creating a `significant_change.py` platform file with a function `async_check_significant_change`.

```python
from typing import Any, Optional
from homeassistant.core import HomeAssistant, callback

@callback
def async_check_significant_change(
    hass: HomeAssistant,
    old_state: str,
    old_attrs: dict,
    new_state: str,
    new_attrs: dict,
    **kwargs: Any,
) -> bool | None:
```

This function is passed a state that was previously considered significant and the new state. It is not just passing the last 2 known states in. The function should return a boolean if it is significant or not, or `None` if the function doesn't know.

When deciding on significance, make sure you take all known attributes into account. Use device classes to differentiate between entity types.

Here are some examples of insignificant changes:

 - A battery that loses 0.1 % charge
 - A temperature sensor that changes 0.1 Celsius
 - A light that changes 2 brightness

Home Assistant will automatically handle cases like `unknown` and `unavailable`.

To add significant state support to an entity integration, run `python3 -m script.scaffold significant_change`.
