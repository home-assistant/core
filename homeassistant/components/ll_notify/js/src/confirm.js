import alertify from "alertifyjs"
import { handleActions } from "./actions"

/**
 *
 * @param {*} event
 *  event.data:
 *      title:        [optional] <strimg>
 *      message:      [required] <string>
 *      after_ok:     [optional] ActionsList
 *      after_cancel: [optional] ActionsList
 *      settings:     [optional] Object of settings (key:value). Seee below
 *
 * Settings
 *  any settiings object will be passed directly to alertify
 *  eg: alertify.alert("Message").settings(settingsObject)
 *
 *  Use this to set things like 'frameless' or 'padding'
 */
export function doConfirm(event) {
  console.log("doConfirm", event.data)
  let title = event.data.title
  let message = event.data.message
  if (!message) {
    message = "Invalid usage: No message set!"
  }

  function callback(type) {
    if (!event.data[type]) {
      return
    } else {
      return handleActions(event.data[type])
    }
  }
  let cb_ok = () => {
      callback("after_ok")
    },
    cb_cancel = () => {
      callback("after_cancel")
    }

  let settingsObj = event.data.settings ? event.data.settings : {}
  alertify.confirm(title, message, cb_ok, cb_cancel).setting(settingsObj)
}

export function subscribeConfirmEvents(hassConn) {
  hassConn.subscribeEvents(event => {
    return doConfirm(event)
  }, `ll_notify/confirm`)
}
