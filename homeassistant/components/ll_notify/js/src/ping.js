
export function subscribePingEvent(hassConn) {
  hassConn.subscribeEvents((event) => {
    console.log(`ll_notify/ping. Data: `, event.data)
  }, "ll_notify/ping")
}
