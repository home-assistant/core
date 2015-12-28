from homeassistant.util.filters import custom_filter
import jsonpath_rw
import json

@custom_filter('jsonpath')
def jsonpath(value, path):
    expr = jsonpath_rw.parse(path)
    match = expr.find(json.loads(value))
    return match[0].value if len(match) > 0 else None

