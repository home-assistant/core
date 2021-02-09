import alertify from "alertifyjs"
import { handleActions } from "./actions"

export function doNotifyDismissAll() {
  alertify.dismissAll()
}

/**
 *
 * @param {*} event
 *  event.data:
 *      message:     [required] <string>
 *      type:        [optional] "success"|"error"|<custom string>
 *      wait:        [optional] <number>
 *      after_close: [optional] ActionsList
 * @param {*} event_type
 *  [optional] "success"|"error"|<custom string>
 */
export function doNotify(event, event_type) {
  let type = event_type ? event_type : event.data.type
  if (typeof type === "undefined") {
    console.error("Invalid usage: doNotify requires a type or empty string.")
    return
  }
  let wait = event.data.wait
  if (typeof wait !== "number") {
    wait = alertify.defaults.notifier.delay
  }
  let message = event.data.message
  if (!message) {
    message = "Invalid usage: No message set!"
  }

  function callback() {
    if (!event.data.after_close) {
      return
    } else {
      return handleActions(event.data.after_close)
    }
  }

  alertify.notify(message, type, wait, callback)
}

export function subscribeNotifyEvents(hassConn) {
  hassConn.subscribeEvents(doNotifyDismissAll, "ll_notify/dismiss_all")
  hassConn.subscribeEvents(doNotify, "ll_notify/notify")

  let wsEvents = ["success", "error", "warning", "message"]
  wsEvents.forEach(eventName => {
    hassConn.subscribeEvents(event => {
      return doNotify(event, eventName)
    }, `ll_notify/${eventName}`)
  })
}
