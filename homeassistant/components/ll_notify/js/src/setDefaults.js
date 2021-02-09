import merge from "lodash.merge"
import alertify from "alertifyjs"

export function doSetDefaults(event) {
  alertify.defaults = merge(alertify.defaults, event.data)
}
