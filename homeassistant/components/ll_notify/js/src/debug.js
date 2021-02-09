export function set_globals() {
  // for debugging
  window.hass = document.querySelector("home-assistant").hass
  window.hassConn = document.querySelector("home-assistant").hass.connection
}

export function do_5sec_test() {
  let hassConn = document.querySelector("home-assistant").hass.connection
  window.setInterval(() => {
    hassConn.sendMessage({
      type: "call_service",
      domain: "ll_notify",
      service: "success",
      service_data: {
        message: "TEST: from FRONTEND",
        wait: 5
      }
    })
  }, 5000)
}
