/**
 * Handle actions.
 *
 * Alertify has callbacks. That won't work for HASS.
 *
 * Instead, when something is done, you can signal other watchers:
 *
 * 1. call_service
 * 2. fire event in hass
 * 3. fire JS event
 *
 * Schema
 * action: <ActionList>|<Action>
 * ActionList: [Action1, Action2, ...]
 * Action: <CallService>|<FireHassEvent>|<FireJSEvent>
 * CallService:
 *      action: "call_service"
 *      domain: <string>
 *      service: <string>
 *      service_data [optional]: <Object>
 *
 * FireHassEvent:
 *      action: "fire_event"
 *      event_name: <string>
 *      event_data [optional]: <Object>
 *
 * FireJSEvent:
 *      action: "js_fire_event"
 *      event_name: <string>
 *      event_data [optional]: <Object>
 */

import alertify from "alertifyjs"
// import { assert } from "assert" // Struggling to get this to work with rollup!
function assert(expr) {
  return Boolean(expr)
}
import _has from "lodash.has"

export function handleActions(eventConfig) {
  let config = eventConfig instanceof Array ? eventConfig : [eventConfig]
  let hassConn = document.querySelector("home-assistant").hass.connection

  config.forEach((cfg) => {
    _handleAction(hassConn, cfg)
  })
}

/**
 * Returns bool. Will not throw.
 * Will log errors to console.
 * Will try alertify.error() (But catch errors.)
 * @param {*} config
 * @returns {boolean}
 */
function _validateConfig(config) {
  try {
    let action = config.action

    switch (action) {
    case "call_service":
      assert(_has(config, "domain"))
      assert(_has(config, "service"))
      break
    case "fire_event":
      assert(_has(config, "event_name"))
      break
    case "js_fire_event":
      assert(_has(config, "event_name"))
      break
    default:
      throw "Invalid Event"
    }
  } catch (err) {
    let msg = `Invalid action configuration for ll_notify: ${JSON.stringify(
      config
    )}`
    try {
      alertify.error(msg)
    } finally {
      console.error(msg)
    }
    return false
  }

  return true
}

function _handleAction(hassConn, config) {
  if (!_validateConfig(config)) {
    return
  }

  try {
    let action = config.action

    console.log(`notify Action called`, action, config)
    switch (action) {
    case "call_service":
      hassConn
        .sendMessagePromise({
          type: "call_service",
          domain: config.domain,
          service: config.service,
          service_data: config.service_data,
        })
        .catch((err) => {
          console.error("FAIL: call_service", err)
        })
      break
    case "fire_event":
      hassConn
        .sendMessagePromise({
          type: "call_service",
          domain: "ll_notify",
          service: "fire_event",
          service_data: {
            event_name: config.event_name,
            event_data: config.event_data,
          },
        })
        .catch((err) => {
          console.error("FAIL: fire_event", err)
        })
      break
    case "js_fire_event":
      document.dispatchEvent(
        new CustomEvent(config.event_name, { detail: config.event_data })
      )
      break
    default:
      throw "Invalid Event"
    }
  } catch (err) {
    let msg = `Unable to process ll_notify action. Config: ${config}. Err: ${err}`
    try {
      alertify.error(msg)
    } finally {
      console.error(msg)
    }
  }
}
