/**
 * Get hassConn
 *
 * Taken from here: https://github.com/thomasloven/hass-browser_mod/blob/master/js/connection.js
 */

const delay = t => new Promise(resolve => setTimeout(resolve, t))


export function getHassConn(){
  return new Promise((resolve) => {
    if(!window.hassConnection) {
      return delay(getHassConn())
    } else {
      window.hassConnection
        .then((hc)=>{
          resolve(hc.conn)
        })
    }
  })

}
