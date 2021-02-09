import alertify from "alertifyjs"
import { handleActions } from "./actions"

/**
 *
 * @param {*} event
 *  event.data:
 *      title:        [optional] <strimg>
 *      message:     [required] <string>
 *      after_close: [optional] ActionsList
 *      settings:    [optional] Object of settings (key:value). Seee below
 *
 * Settings
 *  any settiings object will be passed directly to alertify
 *  eg: alertify.alert("Message").settings(settingsObject)
 *
 *  Use this to set things like 'frameless' or 'padding'
 */
export function doAlert(event) {
  let title = event.data.title
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

  let settingsObj = event.data.settings ? event.data.settings : {}
  alertify.alert(title, message, callback).setting(settingsObj)
}

export function subscribeAlertEvents(hassConn) {
  hassConn.subscribeEvents(event => {
    return doAlert(event)
  }, `ll_notify/alert`)
}
