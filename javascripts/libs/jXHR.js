// jXHR.js (JSON-P XHR)
// v0.1 (c) Kyle Simpson
// MIT License

(function(global){
	var SETTIMEOUT = global.setTimeout, // for better compression
		doc = global.document,
		callback_counter = 0;

	global.jXHR = function() {
		var script_url,
			script_loaded,
			jsonp_callback,
			scriptElem,
			publicAPI = null;

		function removeScript() { try { scriptElem.parentNode.removeChild(scriptElem); } catch (err) { } }

		function reset() {
			script_loaded = false;
			script_url = "";
			removeScript();
			scriptElem = null;
			fireReadyStateChange(0);
		}

		function ThrowError(msg) {
			try { publicAPI.onerror.call(publicAPI,msg,script_url); } catch (err) { throw new Error(msg); }
		}

		function handleScriptLoad() {
			if ((this.readyState && this.readyState!=="complete" && this.readyState!=="loaded") || script_loaded) { return; }
			this.onload = this.onreadystatechange = null; // prevent memory leak
			script_loaded = true;
			if (publicAPI.readyState !== 4) ThrowError("Script failed to load ["+script_url+"].");
			removeScript();
		}

		function fireReadyStateChange(rs,args) {
			args = args || [];
			publicAPI.readyState = rs;
			if (typeof publicAPI.onreadystatechange === "function") publicAPI.onreadystatechange.apply(publicAPI,args);
		}

		publicAPI = {
			onerror:null,
			onreadystatechange:null,
			readyState:0,
			open:function(method,url){
				reset();
				internal_callback = "cb"+(callback_counter++);
				(function(icb){
					global.jXHR[icb] = function() {
						try { fireReadyStateChange.call(publicAPI,4,arguments); }
						catch(err) {
							publicAPI.readyState = -1;
							ThrowError("Script failed to run ["+script_url+"].");
						}
						global.jXHR[icb] = null;
					};
				})(internal_callback);
				script_url = url.replace(/=\?/,"=jXHR."+internal_callback);
				fireReadyStateChange(1);
			},
			send:function(){
				SETTIMEOUT(function(){
					scriptElem = doc.createElement("script");
					scriptElem.setAttribute("type","text/javascript");
					scriptElem.onload = scriptElem.onreadystatechange = function(){handleScriptLoad.call(scriptElem);};
					scriptElem.setAttribute("src",script_url);
					doc.getElementsByTagName("head")[0].appendChild(scriptElem);
				},0);
				fireReadyStateChange(2);
			},
			setRequestHeader:function(){}, // noop
			getResponseHeader:function(){return "";}, // basically noop
			getAllResponseHeaders:function(){return [];} // ditto
		};

		reset();

		return publicAPI;
	};
})(window);

