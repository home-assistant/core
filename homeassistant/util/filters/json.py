from homeassistant.util.filters import custom_filter
import json


@custom_filter('json')
def tojson(value):
  return json.loads(value)

