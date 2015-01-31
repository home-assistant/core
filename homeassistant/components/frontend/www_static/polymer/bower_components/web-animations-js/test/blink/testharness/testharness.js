/*global self*/
/*jshint latedef: nofunc*/
/*
Distributed under both the W3C Test Suite License [1] and the W3C
3-clause BSD License [2]. To contribute to a W3C Test Suite, see the
policies and contribution forms [3].

[1] http://www.w3.org/Consortium/Legal/2008/04-testsuite-license
[2] http://www.w3.org/Consortium/Legal/2008/03-bsd-license
[3] http://www.w3.org/2004/10/27-testcases
*/

/* Documentation is in docs/api.md */

(function ()
{
    var debug = false;
    // default timeout is 10 seconds, test can override if needed
    var settings = {
        output:true,
        harness_timeout:{
            "normal":10000,
            "long":60000
        },
        test_timeout:null
    };

    var xhtml_ns = "http://www.w3.org/1999/xhtml";

    // script_prefix is used by Output.prototype.show_results() to figure out
    // where to get testharness.css from.  It's enclosed in an extra closure to
    // not pollute the library's namespace with variables like "src".
    var script_prefix = null;
    (function ()
    {
        var scripts = document.getElementsByTagName("script");
        for (var i = 0; i < scripts.length; i++) {
            var src;
            if (scripts[i].src) {
                src = scripts[i].src;
            } else if (scripts[i].href) {
                //SVG case
                src = scripts[i].href.baseVal;
            }

            if (src && src.slice(src.length - "testharness.js".length) === "testharness.js") {
                script_prefix = src.slice(0, src.length - "testharness.js".length);
                break;
            }
        }
    })();

    /*
     * API functions
     */

    var name_counter = 0;
    function next_default_name()
    {
        //Don't use document.title to work around an Opera bug in XHTML documents
        var title = document.getElementsByTagName("title")[0];
        var prefix = (title && title.firstChild && title.firstChild.data) || "Untitled";
        var suffix = name_counter > 0 ? " " + name_counter : "";
        name_counter++;
        return prefix + suffix;
    }

    function test(func, name, properties)
    {
        var test_name = name ? name : next_default_name();
        properties = properties ? properties : {};
        var test_obj = new Test(test_name, properties);
        test_obj.step(func, test_obj, test_obj);
        if (test_obj.phase === test_obj.phases.STARTED) {
            test_obj.done();
        }
    }

    function async_test(func, name, properties)
    {
        if (typeof func !== "function") {
            properties = name;
            name = func;
            func = null;
        }
        var test_name = name ? name : next_default_name();
        properties = properties ? properties : {};
        var test_obj = new Test(test_name, properties);
        if (func) {
            test_obj.step(func, test_obj, test_obj);
        }
        return test_obj;
    }

    function setup(func_or_properties, maybe_properties)
    {
        var func = null;
        var properties = {};
        if (arguments.length === 2) {
            func = func_or_properties;
            properties = maybe_properties;
        } else if (func_or_properties instanceof Function) {
            func = func_or_properties;
        } else {
            properties = func_or_properties;
        }
        tests.setup(func, properties);
        output.setup(properties);
    }

    function done() {
        if (tests.tests.length === 0) {
            tests.set_file_is_test();
        }
        if (tests.file_is_test) {
            tests.tests[0].done();
        }
        tests.end_wait();
    }

    function generate_tests(func, args, properties) {
        forEach(args, function(x, i)
                {
                    var name = x[0];
                    test(function()
                         {
                             func.apply(this, x.slice(1));
                         },
                         name,
                         Array.isArray(properties) ? properties[i] : properties);
                });
    }

    function on_event(object, event, callback)
    {
        object.addEventListener(event, callback, false);
    }

    expose(test, 'test');
    expose(async_test, 'async_test');
    expose(generate_tests, 'generate_tests');
    expose(setup, 'setup');
    expose(done, 'done');
    expose(on_event, 'on_event');

    /*
     * Return a string truncated to the given length, with ... added at the end
     * if it was longer.
     */
    function truncate(s, len)
    {
        if (s.length > len) {
            return s.substring(0, len - 3) + "...";
        }
        return s;
    }

    /*
     * Return true if object is probably a Node object.
     */
    function is_node(object)
    {
        // I use duck-typing instead of instanceof, because
        // instanceof doesn't work if the node is from another window (like an
        // iframe's contentWindow):
        // http://www.w3.org/Bugs/Public/show_bug.cgi?id=12295
        if ("nodeType" in object &&
            "nodeName" in object &&
            "nodeValue" in object &&
            "childNodes" in object) {
            try {
                object.nodeType;
            } catch (e) {
                // The object is probably Node.prototype or another prototype
                // object that inherits from it, and not a Node instance.
                return false;
            }
            return true;
        }
        return false;
    }

    /*
     * Convert a value to a nice, human-readable string
     */
    function format_value(val, seen)
    {
        if (!seen) {
            seen = [];
        }
        if (typeof val === "object" && val !== null) {
            if (seen.indexOf(val) >= 0) {
                return "[...]";
            }
            seen.push(val);
        }
        if (Array.isArray(val)) {
            return "[" + val.map(function(x) {return format_value(x, seen);}).join(", ") + "]";
        }

        switch (typeof val) {
        case "string":
            val = val.replace("\\", "\\\\");
            for (var i = 0; i < 32; i++) {
                var replace = "\\";
                switch (i) {
                case 0: replace += "0"; break;
                case 1: replace += "x01"; break;
                case 2: replace += "x02"; break;
                case 3: replace += "x03"; break;
                case 4: replace += "x04"; break;
                case 5: replace += "x05"; break;
                case 6: replace += "x06"; break;
                case 7: replace += "x07"; break;
                case 8: replace += "b"; break;
                case 9: replace += "t"; break;
                case 10: replace += "n"; break;
                case 11: replace += "v"; break;
                case 12: replace += "f"; break;
                case 13: replace += "r"; break;
                case 14: replace += "x0e"; break;
                case 15: replace += "x0f"; break;
                case 16: replace += "x10"; break;
                case 17: replace += "x11"; break;
                case 18: replace += "x12"; break;
                case 19: replace += "x13"; break;
                case 20: replace += "x14"; break;
                case 21: replace += "x15"; break;
                case 22: replace += "x16"; break;
                case 23: replace += "x17"; break;
                case 24: replace += "x18"; break;
                case 25: replace += "x19"; break;
                case 26: replace += "x1a"; break;
                case 27: replace += "x1b"; break;
                case 28: replace += "x1c"; break;
                case 29: replace += "x1d"; break;
                case 30: replace += "x1e"; break;
                case 31: replace += "x1f"; break;
                }
                val = val.replace(RegExp(String.fromCharCode(i), "g"), replace);
            }
            return '"' + val.replace(/"/g, '\\"') + '"';
        case "boolean":
        case "undefined":
            return String(val);
        case "number":
            // In JavaScript, -0 === 0 and String(-0) == "0", so we have to
            // special-case.
            if (val === -0 && 1/val === -Infinity) {
                return "-0";
            }
            return String(val);
        case "object":
            if (val === null) {
                return "null";
            }

            // Special-case Node objects, since those come up a lot in my tests.  I
            // ignore namespaces.
            if (is_node(val)) {
                switch (val.nodeType) {
                case Node.ELEMENT_NODE:
                    var ret = "<" + val.localName;
                    for (var i = 0; i < val.attributes.length; i++) {
                        ret += " " + val.attributes[i].name + '="' + val.attributes[i].value + '"';
                    }
                    ret += ">" + val.innerHTML + "</" + val.localName + ">";
                    return "Element node " + truncate(ret, 60);
                case Node.TEXT_NODE:
                    return 'Text node "' + truncate(val.data, 60) + '"';
                case Node.PROCESSING_INSTRUCTION_NODE:
                    return "ProcessingInstruction node with target " + format_value(truncate(val.target, 60)) + " and data " + format_value(truncate(val.data, 60));
                case Node.COMMENT_NODE:
                    return "Comment node <!--" + truncate(val.data, 60) + "-->";
                case Node.DOCUMENT_NODE:
                    return "Document node with " + val.childNodes.length + (val.childNodes.length == 1 ? " child" : " children");
                case Node.DOCUMENT_TYPE_NODE:
                    return "DocumentType node";
                case Node.DOCUMENT_FRAGMENT_NODE:
                    return "DocumentFragment node with " + val.childNodes.length + (val.childNodes.length == 1 ? " child" : " children");
                default:
                    return "Node object of unknown type";
                }
            }

        /* falls through */
        default:
            return typeof val + ' "' + truncate(String(val), 60) + '"';
        }
    }
    expose(format_value, "format_value");

    /*
     * Assertions
     */

    function assert_true(actual, description)
    {
        assert(actual === true, "assert_true", description,
                                "expected true got ${actual}", {actual:actual});
    }
    expose(assert_true, "assert_true");

    function assert_false(actual, description)
    {
        assert(actual === false, "assert_false", description,
                                 "expected false got ${actual}", {actual:actual});
    }
    expose(assert_false, "assert_false");

    function same_value(x, y) {
        if (y !== y) {
            //NaN case
            return x !== x;
        }
        if (x === 0 && y === 0) {
            //Distinguish +0 and -0
            return 1/x === 1/y;
        }
        return x === y;
    }

    function assert_equals(actual, expected, description)
    {
         /*
          * Test if two primitives are equal or two objects
          * are the same object
          */
        if (typeof actual != typeof expected) {
            assert(false, "assert_equals", description,
                          "expected (" + typeof expected + ") ${expected} but got (" + typeof actual + ") ${actual}",
                          {expected:expected, actual:actual});
            return;
        }
        assert(same_value(actual, expected), "assert_equals", description,
                                             "expected ${expected} but got ${actual}",
                                             {expected:expected, actual:actual});
    }
    expose(assert_equals, "assert_equals");

    function assert_not_equals(actual, expected, description)
    {
         /*
          * Test if two primitives are unequal or two objects
          * are different objects
          */
        assert(!same_value(actual, expected), "assert_not_equals", description,
                                              "got disallowed value ${actual}",
                                              {actual:actual});
    }
    expose(assert_not_equals, "assert_not_equals");

    function assert_in_array(actual, expected, description)
    {
        assert(expected.indexOf(actual) != -1, "assert_in_array", description,
                                               "value ${actual} not in array ${expected}",
                                               {actual:actual, expected:expected});
    }
    expose(assert_in_array, "assert_in_array");

    function assert_object_equals(actual, expected, description)
    {
         //This needs to be improved a great deal
         function check_equal(actual, expected, stack)
         {
             stack.push(actual);

             var p;
             for (p in actual) {
                 assert(expected.hasOwnProperty(p), "assert_object_equals", description,
                                                    "unexpected property ${p}", {p:p});

                 if (typeof actual[p] === "object" && actual[p] !== null) {
                     if (stack.indexOf(actual[p]) === -1) {
                         check_equal(actual[p], expected[p], stack);
                     }
                 } else {
                     assert(same_value(actual[p], expected[p]), "assert_object_equals", description,
                                                       "property ${p} expected ${expected} got ${actual}",
                                                       {p:p, expected:expected, actual:actual});
                 }
             }
             for (p in expected) {
                 assert(actual.hasOwnProperty(p),
                        "assert_object_equals", description,
                        "expected property ${p} missing", {p:p});
             }
             stack.pop();
         }
         check_equal(actual, expected, []);
    }
    expose(assert_object_equals, "assert_object_equals");

    function assert_array_equals(actual, expected, description)
    {
        assert(actual.length === expected.length,
               "assert_array_equals", description,
               "lengths differ, expected ${expected} got ${actual}",
               {expected:expected.length, actual:actual.length});

        for (var i = 0; i < actual.length; i++) {
            assert(actual.hasOwnProperty(i) === expected.hasOwnProperty(i),
                   "assert_array_equals", description,
                   "property ${i}, property expected to be $expected but was $actual",
                   {i:i, expected:expected.hasOwnProperty(i) ? "present" : "missing",
                   actual:actual.hasOwnProperty(i) ? "present" : "missing"});
            assert(same_value(expected[i], actual[i]),
                   "assert_array_equals", description,
                   "property ${i}, expected ${expected} but got ${actual}",
                   {i:i, expected:expected[i], actual:actual[i]});
        }
    }
    expose(assert_array_equals, "assert_array_equals");

    function assert_approx_equals(actual, expected, epsilon, description)
    {
        /*
         * Test if two primitive numbers are equal withing +/- epsilon
         */
        assert(typeof actual === "number",
               "assert_approx_equals", description,
               "expected a number but got a ${type_actual}",
               {type_actual:typeof actual});

        assert(Math.abs(actual - expected) <= epsilon,
               "assert_approx_equals", description,
               "expected ${expected} +/- ${epsilon} but got ${actual}",
               {expected:expected, actual:actual, epsilon:epsilon});
    }
    expose(assert_approx_equals, "assert_approx_equals");

    function assert_less_than(actual, expected, description)
    {
        /*
         * Test if a primitive number is less than another
         */
        assert(typeof actual === "number",
               "assert_less_than", description,
               "expected a number but got a ${type_actual}",
               {type_actual:typeof actual});

        assert(actual < expected,
               "assert_less_than", description,
               "expected a number less than ${expected} but got ${actual}",
               {expected:expected, actual:actual});
    }
    expose(assert_less_than, "assert_less_than");

    function assert_greater_than(actual, expected, description)
    {
        /*
         * Test if a primitive number is greater than another
         */
        assert(typeof actual === "number",
               "assert_greater_than", description,
               "expected a number but got a ${type_actual}",
               {type_actual:typeof actual});

        assert(actual > expected,
               "assert_greater_than", description,
               "expected a number greater than ${expected} but got ${actual}",
               {expected:expected, actual:actual});
    }
    expose(assert_greater_than, "assert_greater_than");

    function assert_less_than_equal(actual, expected, description)
    {
        /*
         * Test if a primitive number is less than or equal to another
         */
        assert(typeof actual === "number",
               "assert_less_than_equal", description,
               "expected a number but got a ${type_actual}",
               {type_actual:typeof actual});

        assert(actual <= expected,
               "assert_less_than", description,
               "expected a number less than or equal to ${expected} but got ${actual}",
               {expected:expected, actual:actual});
    }
    expose(assert_less_than_equal, "assert_less_than_equal");

    function assert_greater_than_equal(actual, expected, description)
    {
        /*
         * Test if a primitive number is greater than or equal to another
         */
        assert(typeof actual === "number",
               "assert_greater_than_equal", description,
               "expected a number but got a ${type_actual}",
               {type_actual:typeof actual});

        assert(actual >= expected,
               "assert_greater_than_equal", description,
               "expected a number greater than or equal to ${expected} but got ${actual}",
               {expected:expected, actual:actual});
    }
    expose(assert_greater_than_equal, "assert_greater_than_equal");

    function assert_regexp_match(actual, expected, description) {
        /*
         * Test if a string (actual) matches a regexp (expected)
         */
        assert(expected.test(actual),
               "assert_regexp_match", description,
               "expected ${expected} but got ${actual}",
               {expected:expected, actual:actual});
    }
    expose(assert_regexp_match, "assert_regexp_match");

    function assert_class_string(object, class_string, description) {
        assert_equals({}.toString.call(object), "[object " + class_string + "]",
                      description);
    }
    expose(assert_class_string, "assert_class_string");


    function _assert_own_property(name) {
        return function(object, property_name, description)
        {
            assert(object.hasOwnProperty(property_name),
                   name, description,
                   "expected property ${p} missing", {p:property_name});
        };
    }
    expose(_assert_own_property("assert_exists"), "assert_exists");
    expose(_assert_own_property("assert_own_property"), "assert_own_property");

    function assert_not_exists(object, property_name, description)
    {
        assert(!object.hasOwnProperty(property_name),
               "assert_not_exists", description,
               "unexpected property ${p} found", {p:property_name});
    }
    expose(assert_not_exists, "assert_not_exists");

    function _assert_inherits(name) {
        return function (object, property_name, description)
        {
            assert(typeof object === "object",
                   name, description,
                   "provided value is not an object");

            assert("hasOwnProperty" in object,
                   name, description,
                   "provided value is an object but has no hasOwnProperty method");

            assert(!object.hasOwnProperty(property_name),
                   name, description,
                   "property ${p} found on object expected in prototype chain",
                   {p:property_name});

            assert(property_name in object,
                   name, description,
                   "property ${p} not found in prototype chain",
                   {p:property_name});
        };
    }
    expose(_assert_inherits("assert_inherits"), "assert_inherits");
    expose(_assert_inherits("assert_idl_attribute"), "assert_idl_attribute");

    function assert_readonly(object, property_name, description)
    {
         var initial_value = object[property_name];
         try {
             //Note that this can have side effects in the case where
             //the property has PutForwards
             object[property_name] = initial_value + "a"; //XXX use some other value here?
             assert(same_value(object[property_name], initial_value),
                    "assert_readonly", description,
                    "changing property ${p} succeeded",
                    {p:property_name});
         } finally {
             object[property_name] = initial_value;
         }
    }
    expose(assert_readonly, "assert_readonly");

    function assert_throws(code, func, description)
    {
        try {
            func.call(this);
            assert(false, "assert_throws", description,
                   "${func} did not throw", {func:func});
        } catch (e) {
            if (e instanceof AssertionError) {
                throw e;
            }
            if (code === null) {
                return;
            }
            if (typeof code === "object") {
                assert(typeof e == "object" && "name" in e && e.name == code.name,
                       "assert_throws", description,
                       "${func} threw ${actual} (${actual_name}) expected ${expected} (${expected_name})",
                                    {func:func, actual:e, actual_name:e.name,
                                     expected:code,
                                     expected_name:code.name});
                return;
            }

            var code_name_map = {
                INDEX_SIZE_ERR: 'IndexSizeError',
                HIERARCHY_REQUEST_ERR: 'HierarchyRequestError',
                WRONG_DOCUMENT_ERR: 'WrongDocumentError',
                INVALID_CHARACTER_ERR: 'InvalidCharacterError',
                NO_MODIFICATION_ALLOWED_ERR: 'NoModificationAllowedError',
                NOT_FOUND_ERR: 'NotFoundError',
                NOT_SUPPORTED_ERR: 'NotSupportedError',
                INVALID_STATE_ERR: 'InvalidStateError',
                SYNTAX_ERR: 'SyntaxError',
                INVALID_MODIFICATION_ERR: 'InvalidModificationError',
                NAMESPACE_ERR: 'NamespaceError',
                INVALID_ACCESS_ERR: 'InvalidAccessError',
                TYPE_MISMATCH_ERR: 'TypeMismatchError',
                SECURITY_ERR: 'SecurityError',
                NETWORK_ERR: 'NetworkError',
                ABORT_ERR: 'AbortError',
                URL_MISMATCH_ERR: 'URLMismatchError',
                QUOTA_EXCEEDED_ERR: 'QuotaExceededError',
                TIMEOUT_ERR: 'TimeoutError',
                INVALID_NODE_TYPE_ERR: 'InvalidNodeTypeError',
                DATA_CLONE_ERR: 'DataCloneError'
            };

            var name = code in code_name_map ? code_name_map[code] : code;

            var name_code_map = {
                IndexSizeError: 1,
                HierarchyRequestError: 3,
                WrongDocumentError: 4,
                InvalidCharacterError: 5,
                NoModificationAllowedError: 7,
                NotFoundError: 8,
                NotSupportedError: 9,
                InvalidStateError: 11,
                SyntaxError: 12,
                InvalidModificationError: 13,
                NamespaceError: 14,
                InvalidAccessError: 15,
                TypeMismatchError: 17,
                SecurityError: 18,
                NetworkError: 19,
                AbortError: 20,
                URLMismatchError: 21,
                QuotaExceededError: 22,
                TimeoutError: 23,
                InvalidNodeTypeError: 24,
                DataCloneError: 25,

                UnknownError: 0,
                ConstraintError: 0,
                DataError: 0,
                TransactionInactiveError: 0,
                ReadOnlyError: 0,
                VersionError: 0
            };

            if (!(name in name_code_map)) {
                throw new AssertionError('Test bug: unrecognized DOMException code "' + code + '" passed to assert_throws()');
            }

            var required_props = { code: name_code_map[name] };

            if (required_props.code === 0 ||
               ("name" in e && e.name !== e.name.toUpperCase() && e.name !== "DOMException")) {
                // New style exception: also test the name property.
                required_props.name = name;
            }

            //We'd like to test that e instanceof the appropriate interface,
            //but we can't, because we don't know what window it was created
            //in.  It might be an instanceof the appropriate interface on some
            //unknown other window.  TODO: Work around this somehow?

            assert(typeof e == "object",
                   "assert_throws", description,
                   "${func} threw ${e} with type ${type}, not an object",
                   {func:func, e:e, type:typeof e});

            for (var prop in required_props) {
                assert(typeof e == "object" && prop in e && e[prop] == required_props[prop],
                       "assert_throws", description,
                       "${func} threw ${e} that is not a DOMException " + code + ": property ${prop} is equal to ${actual}, expected ${expected}",
                       {func:func, e:e, prop:prop, actual:e[prop], expected:required_props[prop]});
            }
        }
    }
    expose(assert_throws, "assert_throws");

    function assert_unreached(description) {
         assert(false, "assert_unreached", description,
                "Reached unreachable code");
    }
    expose(assert_unreached, "assert_unreached");

    function assert_any(assert_func, actual, expected_array)
    {
        var args = [].slice.call(arguments, 3);
        var errors = [];
        var passed = false;
        forEach(expected_array,
                function(expected)
                {
                    try {
                        assert_func.apply(this, [actual, expected].concat(args));
                        passed = true;
                    } catch (e) {
                        errors.push(e.message);
                    }
                });
        if (!passed) {
            throw new AssertionError(errors.join("\n\n"));
        }
    }
    expose(assert_any, "assert_any");

    function Test(name, properties)
    {
        if (tests.file_is_test && tests.tests.length) {
            throw new Error("Tried to create a test with file_is_test");
        }
        this.name = name;

        this.phases = {
            INITIAL:0,
            STARTED:1,
            HAS_RESULT:2,
            COMPLETE:3
        };
        this.phase = this.phases.INITIAL;

        this.status = this.NOTRUN;
        this.timeout_id = null;

        this.properties = properties;
        var timeout = properties.timeout ? properties.timeout : settings.test_timeout;
        if (timeout != null) {
            this.timeout_length = timeout * tests.timeout_multiplier;
        } else {
            this.timeout_length = null;
        }

        this.message = null;

        this.steps = [];

        this.cleanup_callbacks = [];

        tests.push(this);
    }

    Test.statuses = {
        PASS:0,
        FAIL:1,
        TIMEOUT:2,
        NOTRUN:3
    };

    Test.prototype = merge({}, Test.statuses);

    Test.prototype.structured_clone = function()
    {
        if (!this._structured_clone) {
            var msg = this.message;
            msg = msg ? String(msg) : msg;
            this._structured_clone = merge({
                name:String(this.name),
                status:this.status,
                message:msg
            }, Test.statuses);
        }
        return this._structured_clone;
    };

    Test.prototype.step = function(func, this_obj)
    {
        if (this.phase > this.phases.STARTED) {
            return;
        }
        this.phase = this.phases.STARTED;
        //If we don't get a result before the harness times out that will be a test timout
        this.set_status(this.TIMEOUT, "Test timed out");

        tests.started = true;

        if (this.timeout_id === null) {
            this.set_timeout();
        }

        this.steps.push(func);

        if (arguments.length === 1) {
            this_obj = this;
        }

        try {
            return func.apply(this_obj, Array.prototype.slice.call(arguments, 2));
        } catch (e) {
            if (this.phase >= this.phases.HAS_RESULT) {
                return;
            }
            var message = (typeof e === "object" && e !== null) ? e.message : e;
            if (typeof e.stack != "undefined" && typeof e.message == "string") {
                //Try to make it more informative for some exceptions, at least
                //in Gecko and WebKit.  This results in a stack dump instead of
                //just errors like "Cannot read property 'parentNode' of null"
                //or "root is null".  Makes it a lot longer, of course.
                message += "(stack: " + e.stack + ")";
            }
            this.set_status(this.FAIL, message);
            this.phase = this.phases.HAS_RESULT;
            this.done();
        }
    };

    Test.prototype.step_func = function(func, this_obj)
    {
        var test_this = this;

        if (arguments.length === 1) {
            this_obj = test_this;
        }

        return function()
        {
            return test_this.step.apply(test_this, [func, this_obj].concat(
                Array.prototype.slice.call(arguments)));
        };
    };

    Test.prototype.step_func_done = function(func, this_obj)
    {
        var test_this = this;

        if (arguments.length === 1) {
            this_obj = test_this;
        }

        return function()
        {
            if (func) {
                test_this.step.apply(test_this, [func, this_obj].concat(
                    Array.prototype.slice.call(arguments)));
            }
            test_this.done();
        };
    };

    Test.prototype.unreached_func = function(description)
    {
        return this.step_func(function() {
            assert_unreached(description);
        });
    };

    Test.prototype.add_cleanup = function(callback) {
        this.cleanup_callbacks.push(callback);
    };

    Test.prototype.force_timeout = function() {
        this.set_status(this.TIMEOUT);
        this.phase = this.phases.HAS_RESULT;
    }

    Test.prototype.set_timeout = function()
    {
        if (this.timeout_length !== null) {
            var this_obj = this;
            this.timeout_id = setTimeout(function()
                                         {
                                             this_obj.timeout();
                                         }, this.timeout_length);
        }
    };

    Test.prototype.set_status = function(status, message)
    {
        this.status = status;
        this.message = message;
    };

    Test.prototype.timeout = function()
    {
        this.timeout_id = null;
        this.set_status(this.TIMEOUT, "Test timed out");
        this.phase = this.phases.HAS_RESULT;
        this.done();
    };

    Test.prototype.done = function()
    {
        if (this.phase == this.phases.COMPLETE) {
            return;
        }

        if (this.phase <= this.phases.STARTED) {
            this.set_status(this.PASS, null);
        }

        if (this.status == this.NOTRUN) {
            alert(this.phase);
        }

        this.phase = this.phases.COMPLETE;

        clearTimeout(this.timeout_id);
        tests.result(this);
        this.cleanup();
    };

    Test.prototype.cleanup = function() {
        forEach(this.cleanup_callbacks,
                function(cleanup_callback) {
                    cleanup_callback();
                });
    };

    /*
     * Harness
     */

    function TestsStatus()
    {
        this.status = null;
        this.message = null;
    }

    TestsStatus.statuses = {
        OK:0,
        ERROR:1,
        TIMEOUT:2
    };

    TestsStatus.prototype = merge({}, TestsStatus.statuses);

    TestsStatus.prototype.structured_clone = function()
    {
        if (!this._structured_clone) {
            var msg = this.message;
            msg = msg ? String(msg) : msg;
            this._structured_clone = merge({
                status:this.status,
                message:msg
            }, TestsStatus.statuses);
        }
        return this._structured_clone;
    };

    function Tests()
    {
        this.tests = [];
        this.num_pending = 0;

        this.phases = {
            INITIAL:0,
            SETUP:1,
            HAVE_TESTS:2,
            HAVE_RESULTS:3,
            COMPLETE:4
        };
        this.phase = this.phases.INITIAL;

        this.properties = {};

        //All tests can't be done until the load event fires
        this.all_loaded = false;
        this.wait_for_finish = false;
        this.processing_callbacks = false;

        this.allow_uncaught_exception = false;

        this.file_is_test = false;

        this.timeout_multiplier = 1;
        this.timeout_length = this.get_timeout();
        this.timeout_id = null;

        this.start_callbacks = [];
        this.test_done_callbacks = [];
        this.all_done_callbacks = [];

        this.status = new TestsStatus();

        var this_obj = this;

        on_event(window, "load",
                 function()
                 {
                     this_obj.all_loaded = true;
                     if (this_obj.all_done())
                     {
                         this_obj.complete();
                     }
                 });

        this.set_timeout();
    }

    Tests.prototype.setup = function(func, properties)
    {
        if (this.phase >= this.phases.HAVE_RESULTS) {
            return;
        }

        if (this.phase < this.phases.SETUP) {
            this.phase = this.phases.SETUP;
        }

        this.properties = properties;

        for (var p in properties) {
            if (properties.hasOwnProperty(p)) {
                var value = properties[p];
                if (p == "allow_uncaught_exception") {
                    this.allow_uncaught_exception = value;
                } else if (p == "explicit_done" && value) {
                    this.wait_for_finish = true;
                } else if (p == "explicit_timeout" && value) {
                    this.timeout_length = null;
                    if (this.timeout_id)
                    {
                        clearTimeout(this.timeout_id);
                    }
                } else if (p == "timeout_multiplier") {
                    this.timeout_multiplier = value;
                }
            }
        }

        if (func) {
            try {
                func();
            } catch (e) {
                this.status.status = this.status.ERROR;
                this.status.message = String(e);
            }
        }
        this.set_timeout();
    };

    Tests.prototype.set_file_is_test = function() {
        if (this.tests.length > 0) {
            throw new Error("Tried to set file as test after creating a test");
        }
        this.wait_for_finish = true;
        this.file_is_test = true;
        // Create the test, which will add it to the list of tests
        async_test();
    };

    Tests.prototype.get_timeout = function() {
        var metas = document.getElementsByTagName("meta");
        for (var i = 0; i < metas.length; i++) {
            if (metas[i].name == "timeout") {
                if (metas[i].content == "long") {
                    return settings.harness_timeout.long;
                }
                break;
            }
        }
        return settings.harness_timeout.normal;
    };

    Tests.prototype.set_timeout = function() {
        var this_obj = this;
        clearTimeout(this.timeout_id);
        if (this.timeout_length !== null) {
            this.timeout_id = setTimeout(function() {
                                             this_obj.timeout();
                                         }, this.timeout_length);
        }
    };

    Tests.prototype.timeout = function() {
        if (this.status.status === null) {
            this.status.status = this.status.TIMEOUT;
        }
        this.complete();
    };

    Tests.prototype.end_wait = function()
    {
        this.wait_for_finish = false;
        if (this.all_done()) {
            this.complete();
        }
    };

    Tests.prototype.push = function(test)
    {
        if (this.phase < this.phases.HAVE_TESTS) {
            this.start();
        }
        this.num_pending++;
        this.tests.push(test);
    };

    Tests.prototype.all_done = function() {
        return (this.tests.length > 0 && this.all_loaded && this.num_pending === 0 &&
                !this.wait_for_finish && !this.processing_callbacks);
    };

    Tests.prototype.start = function() {
        this.phase = this.phases.HAVE_TESTS;
        this.notify_start();
    };

    Tests.prototype.notify_start = function() {
        var this_obj = this;
        forEach (this.start_callbacks,
                 function(callback)
                 {
                     callback(this_obj.properties);
                 });
        forEach_windows(
                function(w, is_same_origin)
                {
                    if (is_same_origin && w.start_callback) {
                        try {
                            w.start_callback(this_obj.properties);
                        } catch (e) {
                            if (debug) {
                                throw e;
                            }
                        }
                    }
                    if (supports_post_message(w) && w !== self) {
                        w.postMessage({
                            type: "start",
                            properties: this_obj.properties
                        }, "*");
                    }
                });
    };

    Tests.prototype.result = function(test)
    {
        if (this.phase > this.phases.HAVE_RESULTS) {
            return;
        }
        this.phase = this.phases.HAVE_RESULTS;
        this.num_pending--;
        this.notify_result(test);
    };

    Tests.prototype.notify_result = function(test) {
        var this_obj = this;
        this.processing_callbacks = true;
        forEach(this.test_done_callbacks,
                function(callback)
                {
                    callback(test, this_obj);
                });

        forEach_windows(
                function(w, is_same_origin)
                {
                    if (is_same_origin && w.result_callback) {
                        try {
                            w.result_callback(test);
                        } catch (e) {
                            if (debug) {
                                throw e;
                            }
                        }
                    }
                    if (supports_post_message(w) && w !== self) {
                        w.postMessage({
                            type: "result",
                            test: test.structured_clone()
                        }, "*");
                    }
                });
        this.processing_callbacks = false;
        if (this_obj.all_done()) {
            this_obj.complete();
        }
    };

    Tests.prototype.complete = function() {
        if (this.phase === this.phases.COMPLETE) {
            return;
        }
        this.phase = this.phases.COMPLETE;
        var this_obj = this;
        this.tests.forEach(
            function(x)
            {
                if (x.status === x.NOTRUN) {
                    this_obj.notify_result(x);
                    x.cleanup();
                }
            }
        );
        this.notify_complete();
    };

    Tests.prototype.notify_complete = function()
    {
        clearTimeout(this.timeout_id);
        var this_obj = this;
        var tests = map(this_obj.tests,
                        function(test)
                        {
                            return test.structured_clone();
                        });
        if (this.status.status === null) {
            this.status.status = this.status.OK;
        }

        forEach (this.all_done_callbacks,
                 function(callback)
                 {
                     callback(this_obj.tests, this_obj.status);
                 });

        forEach_windows(
                function(w, is_same_origin)
                {
                    if (is_same_origin && w.completion_callback) {
                        try {
                            w.completion_callback(this_obj.tests, this_obj.status);
                        } catch (e) {
                            if (debug) {
                                throw e;
                            }
                        }
                    }
                    if (supports_post_message(w) && w !== self) {
                        w.postMessage({
                            type: "complete",
                            tests: tests,
                            status: this_obj.status.structured_clone()
                        }, "*");
                    }
                });
    };

    var tests = new Tests();

    addEventListener("error", function(e) {
        if (tests.file_is_test) {
            var test = tests.tests[0];
            if (test.phase >= test.phases.HAS_RESULT) {
                return;
            }
            var message = e.message;
            test.set_status(test.FAIL, message);
            test.phase = test.phases.HAS_RESULT;
            test.done();
            done();
        } else if (!tests.allow_uncaught_exception) {
            tests.status.status = tests.status.ERROR;
            tests.status.message = e.message;
        }
    });

    function timeout() {
        if (tests.timeout_length === null) {
            tests.timeout();
        }
    }
    expose(timeout, 'timeout');

    function add_start_callback(callback) {
        tests.start_callbacks.push(callback);
    }

    function add_result_callback(callback)
    {
        tests.test_done_callbacks.push(callback);
    }

    function add_completion_callback(callback)
    {
       tests.all_done_callbacks.push(callback);
    }

    expose(add_start_callback, 'add_start_callback');
    expose(add_result_callback, 'add_result_callback');
    expose(add_completion_callback, 'add_completion_callback');

    /*
     * Output listener
    */

    function Output() {
        this.output_document = document;
        this.output_node = null;
        this.done_count = 0;
        this.enabled = settings.output;
        this.phase = this.INITIAL;
    }

    Output.prototype.INITIAL = 0;
    Output.prototype.STARTED = 1;
    Output.prototype.HAVE_RESULTS = 2;
    Output.prototype.COMPLETE = 3;

    Output.prototype.setup = function(properties) {
        if (this.phase > this.INITIAL) {
            return;
        }

        //If output is disabled in testharnessreport.js the test shouldn't be
        //able to override that
        this.enabled = this.enabled && (properties.hasOwnProperty("output") ?
                                        properties.output : settings.output);
    };

    Output.prototype.init = function(properties) {
        if (this.phase >= this.STARTED) {
            return;
        }
        if (properties.output_document) {
            this.output_document = properties.output_document;
        } else {
            this.output_document = document;
        }
        this.phase = this.STARTED;
    };

    Output.prototype.resolve_log = function() {
        var output_document;
        if (typeof this.output_document === "function") {
            output_document = this.output_document.apply(undefined);
        } else {
            output_document = this.output_document;
        }
        if (!output_document) {
            return;
        }
        var node = output_document.getElementById("log");
        if (!node) {
            if (!document.body || document.readyState == "loading") {
                return;
            }
            node = output_document.createElement("div");
            node.id = "log";
            output_document.body.appendChild(node);
        }
        this.output_document = output_document;
        this.output_node = node;
    };

    Output.prototype.show_status = function() {
        if (this.phase < this.STARTED) {
            this.init();
        }
        if (!this.enabled) {
            return;
        }
        if (this.phase < this.HAVE_RESULTS) {
            this.resolve_log();
            this.phase = this.HAVE_RESULTS;
        }
        this.done_count++;
        if (this.output_node) {
            if (this.done_count < 100 ||
                (this.done_count < 1000 && this.done_count % 100 === 0) ||
                this.done_count % 1000 === 0) {
                this.output_node.textContent = "Running, " +
                    this.done_count + " complete, " +
                    tests.num_pending + " remain";
            }
        }
    };

    Output.prototype.show_results = function (tests, harness_status) {
        if (this.phase >= this.COMPLETE) {
            return;
        }
        if (!this.enabled) {
            return;
        }
        if (!this.output_node) {
            this.resolve_log();
        }
        this.phase = this.COMPLETE;

        var log = this.output_node;
        if (!log) {
            return;
        }
        var output_document = this.output_document;

        while (log.lastChild) {
            log.removeChild(log.lastChild);
        }

        if (script_prefix != null) {
            var stylesheet = output_document.createElementNS(xhtml_ns, "link");
            stylesheet.setAttribute("rel", "stylesheet");
            stylesheet.setAttribute("href", script_prefix + "testharness.css");
            var heads = output_document.getElementsByTagName("head");
            if (heads.length) {
                heads[0].appendChild(stylesheet);
            }
        }

        var status_text_harness = {};
        status_text_harness[harness_status.OK] = "OK";
        status_text_harness[harness_status.ERROR] = "Error";
        status_text_harness[harness_status.TIMEOUT] = "Timeout";

        var status_text = {};
        status_text[Test.prototype.PASS] = "Pass";
        status_text[Test.prototype.FAIL] = "Fail";
        status_text[Test.prototype.TIMEOUT] = "Timeout";
        status_text[Test.prototype.NOTRUN] = "Not Run";

        var status_number = {};
        forEach(tests,
                function(test) {
                    var status = status_text[test.status];
                    if (status_number.hasOwnProperty(status)) {
                        status_number[status] += 1;
                    } else {
                        status_number[status] = 1;
                    }
                });

        function status_class(status)
        {
            return status.replace(/\s/g, '').toLowerCase();
        }

        var summary_template = ["section", {"id":"summary"},
                                ["h2", {}, "Summary"],
                                function()
                                {

                                    var status = status_text_harness[harness_status.status];
                                    var rv = [["section", {},
                                               ["p", {},
                                                "Harness status: ",
                                                ["span", {"class":status_class(status)},
                                                 status
                                                ],
                                               ]
                                              ]];

                                    if (harness_status.status === harness_status.ERROR) {
                                        rv[0].push(["pre", {}, harness_status.message]);
                                    }
                                    return rv;
                                },
                                ["p", {}, "Found ${num_tests} tests"],
                                function() {
                                    var rv = [["div", {}]];
                                    var i = 0;
                                    while (status_text.hasOwnProperty(i)) {
                                        if (status_number.hasOwnProperty(status_text[i])) {
                                            var status = status_text[i];
                                            rv[0].push(["div", {"class":status_class(status)},
                                                        ["label", {},
                                                         ["input", {type:"checkbox", checked:"checked"}],
                                                         status_number[status] + " " + status]]);
                                        }
                                        i++;
                                    }
                                    return rv;
                                },
                               ];

        log.appendChild(render(summary_template, {num_tests:tests.length}, output_document));

        forEach(output_document.querySelectorAll("section#summary label"),
                function(element)
                {
                    on_event(element, "click",
                             function(e)
                             {
                                 if (output_document.getElementById("results") === null) {
                                     e.preventDefault();
                                     return;
                                 }
                                 var result_class = element.parentNode.getAttribute("class");
                                 var style_element = output_document.querySelector("style#hide-" + result_class);
                                 var input_element = element.querySelector("input");
                                 if (!style_element && !input_element.checked) {
                                     style_element = output_document.createElementNS(xhtml_ns, "style");
                                     style_element.id = "hide-" + result_class;
                                     style_element.textContent = "table#results > tbody > tr."+result_class+"{display:none}";
                                     output_document.body.appendChild(style_element);
                                 } else if (style_element && input_element.checked) {
                                     style_element.parentNode.removeChild(style_element);
                                 }
                             });
                });

        // This use of innerHTML plus manual escaping is not recommended in
        // general, but is necessary here for performance.  Using textContent
        // on each individual <td> adds tens of seconds of execution time for
        // large test suites (tens of thousands of tests).
        function escape_html(s)
        {
            return s.replace(/\&/g, "&amp;")
                .replace(/</g, "&lt;")
                .replace(/"/g, "&quot;")
                .replace(/'/g, "&#39;");
        }

        function has_assertions()
        {
            for (var i = 0; i < tests.length; i++) {
                if (tests[i].properties.hasOwnProperty("assert")) {
                    return true;
                }
            }
            return false;
        }

        function get_assertion(test)
        {
            if (test.properties.hasOwnProperty("assert")) {
                if (Array.isArray(test.properties.assert)) {
                    return test.properties.assert.join(' ');
                }
                return test.properties.assert;
            }
            return '';
        }

        log.appendChild(document.createElementNS(xhtml_ns, "section"));
        var assertions = has_assertions();
        var html = "<h2>Details</h2><table id='results' " + (assertions ? "class='assertions'" : "" ) + ">" +
            "<thead><tr><th>Result</th><th>Test Name</th>" +
            (assertions ? "<th>Assertion</th>" : "") +
            "<th>Message</th></tr></thead>" +
            "<tbody>";
        for (var i = 0; i < tests.length; i++) {
            html += '<tr class="' +
                escape_html(status_class(status_text[tests[i].status])) +
                '"><td>' +
                escape_html(status_text[tests[i].status]) +
                "</td><td>" +
                escape_html(tests[i].name) +
                "</td><td>" +
                (assertions ? escape_html(get_assertion(tests[i])) + "</td><td>" : "") +
                escape_html(tests[i].message ? tests[i].message : " ") +
                "</td></tr>";
        }
        html += "</tbody></table>";
        try {
            log.lastChild.innerHTML = html;
        } catch (e) {
            log.appendChild(document.createElementNS(xhtml_ns, "p"))
               .textContent = "Setting innerHTML for the log threw an exception.";
            log.appendChild(document.createElementNS(xhtml_ns, "pre"))
               .textContent = html;
        }
    };

    var output = new Output();
    add_start_callback(function (properties) {output.init(properties);});
    add_result_callback(function () {output.show_status();});
    add_completion_callback(function (tests, harness_status) {output.show_results(tests, harness_status);});

    /*
     * Template code
     *
     * A template is just a javascript structure. An element is represented as:
     *
     * [tag_name, {attr_name:attr_value}, child1, child2]
     *
     * the children can either be strings (which act like text nodes), other templates or
     * functions (see below)
     *
     * A text node is represented as
     *
     * ["{text}", value]
     *
     * String values have a simple substitution syntax; ${foo} represents a variable foo.
     *
     * It is possible to embed logic in templates by using a function in a place where a
     * node would usually go. The function must either return part of a template or null.
     *
     * In cases where a set of nodes are required as output rather than a single node
     * with children it is possible to just use a list
     * [node1, node2, node3]
     *
     * Usage:
     *
     * render(template, substitutions) - take a template and an object mapping
     * variable names to parameters and return either a DOM node or a list of DOM nodes
     *
     * substitute(template, substitutions) - take a template and variable mapping object,
     * make the variable substitutions and return the substituted template
     *
     */

    function is_single_node(template)
    {
        return typeof template[0] === "string";
    }

    function substitute(template, substitutions)
    {
        if (typeof template === "function") {
            var replacement = template(substitutions);
            if (!replacement) {
                return null;
            }

            return substitute(replacement, substitutions);
        }

        if (is_single_node(template)) {
            return substitute_single(template, substitutions);
        }

        return filter(map(template, function(x) {
                              return substitute(x, substitutions);
                          }), function(x) {return x !== null;});
    }

    function substitute_single(template, substitutions)
    {
        var substitution_re = /\$\{([^ }]*)\}/g;

        function do_substitution(input) {
            var components = input.split(substitution_re);
            var rv = [];
            for (var i = 0; i < components.length; i += 2) {
                rv.push(components[i]);
                if (components[i + 1]) {
                    rv.push(String(substitutions[components[i + 1]]));
                }
            }
            return rv;
        }

        function substitute_attrs(attrs, rv)
        {
            rv[1] = {};
            for (var name in template[1]) {
                if (attrs.hasOwnProperty(name)) {
                    var new_name = do_substitution(name).join("");
                    var new_value = do_substitution(attrs[name]).join("");
                    rv[1][new_name] = new_value;
                }
            }
        }

        function substitute_children(children, rv)
        {
            for (var i = 0; i < children.length; i++) {
                if (children[i] instanceof Object) {
                    var replacement = substitute(children[i], substitutions);
                    if (replacement !== null) {
                        if (is_single_node(replacement)) {
                            rv.push(replacement);
                        } else {
                            extend(rv, replacement);
                        }
                    }
                } else {
                    extend(rv, do_substitution(String(children[i])));
                }
            }
            return rv;
        }

        var rv = [];
        rv.push(do_substitution(String(template[0])).join(""));

        if (template[0] === "{text}") {
            substitute_children(template.slice(1), rv);
        } else {
            substitute_attrs(template[1], rv);
            substitute_children(template.slice(2), rv);
        }

        return rv;
    }

    function make_dom_single(template, doc)
    {
        var output_document = doc || document;
        var element;
        if (template[0] === "{text}") {
            element = output_document.createTextNode("");
            for (var i = 1; i < template.length; i++) {
                element.data += template[i];
            }
        } else {
            element = output_document.createElementNS(xhtml_ns, template[0]);
            for (var name in template[1]) {
                if (template[1].hasOwnProperty(name)) {
                    element.setAttribute(name, template[1][name]);
                }
            }
            for (var i = 2; i < template.length; i++) {
                if (template[i] instanceof Object) {
                    var sub_element = make_dom(template[i]);
                    element.appendChild(sub_element);
                } else {
                    var text_node = output_document.createTextNode(template[i]);
                    element.appendChild(text_node);
                }
            }
        }

        return element;
    }



    function make_dom(template, substitutions, output_document)
    {
        if (is_single_node(template)) {
            return make_dom_single(template, output_document);
        }

        return map(template, function(x) {
                       return make_dom_single(x, output_document);
                   });
    }

    function render(template, substitutions, output_document)
    {
        return make_dom(substitute(template, substitutions), output_document);
    }

    /*
     * Utility funcions
     */
    function assert(expected_true, function_name, description, error, substitutions)
    {
        if (tests.tests.length === 0) {
            tests.set_file_is_test();
        }
        if (expected_true !== true) {
            var msg = make_message(function_name, description,
                                   error, substitutions);
            throw new AssertionError(msg);
        }
    }

    function AssertionError(message)
    {
        this.message = message;
    }

    AssertionError.prototype.toString = function() {
        return this.message;
    };

    function make_message(function_name, description, error, substitutions)
    {
        for (var p in substitutions) {
            if (substitutions.hasOwnProperty(p)) {
                substitutions[p] = format_value(substitutions[p]);
            }
        }
        var node_form = substitute(["{text}", "${function_name}: ${description}" + error],
                                   merge({function_name:function_name,
                                          description:(description?description + " ":"")},
                                          substitutions));
        return node_form.slice(1).join("");
    }

    function filter(array, callable, thisObj) {
        var rv = [];
        for (var i = 0; i < array.length; i++) {
            if (array.hasOwnProperty(i)) {
                var pass = callable.call(thisObj, array[i], i, array);
                if (pass) {
                    rv.push(array[i]);
                }
            }
        }
        return rv;
    }

    function map(array, callable, thisObj)
    {
        var rv = [];
        rv.length = array.length;
        for (var i = 0; i < array.length; i++) {
            if (array.hasOwnProperty(i)) {
                rv[i] = callable.call(thisObj, array[i], i, array);
            }
        }
        return rv;
    }

    function extend(array, items)
    {
        Array.prototype.push.apply(array, items);
    }

    function forEach (array, callback, thisObj)
    {
        for (var i = 0; i < array.length; i++) {
            if (array.hasOwnProperty(i)) {
                callback.call(thisObj, array[i], i, array);
            }
        }
    }

    function merge(a,b)
    {
        var rv = {};
        var p;
        for (p in a) {
            rv[p] = a[p];
        }
        for (p in b) {
            rv[p] = b[p];
        }
        return rv;
    }

    function expose(object, name)
    {
        var components = name.split(".");
        var target = window;
        for (var i = 0; i < components.length - 1; i++) {
            if (!(components[i] in target)) {
                target[components[i]] = {};
            }
            target = target[components[i]];
        }
        target[components[components.length - 1]] = object;
    }

    function forEach_windows(callback) {
        // Iterate of the the windows [self ... top, opener]. The callback is passed
        // two objects, the first one is the windows object itself, the second one
        // is a boolean indicating whether or not its on the same origin as the
        // current window.
        var cache = forEach_windows.result_cache;
        if (!cache) {
            cache = [[self, true]];
            var w = self;
            var i = 0;
            var so;
            var origins = location.ancestorOrigins;
            while (w != w.parent) {
                w = w.parent;
                // In WebKit, calls to parent windows' properties that aren't on the same
                // origin cause an error message to be displayed in the error console but
                // don't throw an exception. This is a deviation from the current HTML5
                // spec. See: https://bugs.webkit.org/show_bug.cgi?id=43504
                // The problem with WebKit's behavior is that it pollutes the error console
                // with error messages that can't be caught.
                //
                // This issue can be mitigated by relying on the (for now) proprietary
                // `location.ancestorOrigins` property which returns an ordered list of
                // the origins of enclosing windows. See:
                // http://trac.webkit.org/changeset/113945.
                if (origins) {
                    so = (location.origin == origins[i]);
                } else {
                    so = is_same_origin(w);
                }
                cache.push([w, so]);
                i++;
            }
            w = window.opener;
            if (w) {
                // window.opener isn't included in the `location.ancestorOrigins` prop.
                // We'll just have to deal with a simple check and an error msg on WebKit
                // browsers in this case.
                cache.push([w, is_same_origin(w)]);
            }
            forEach_windows.result_cache = cache;
        }

        forEach(cache,
                function(a)
                {
                    callback.apply(null, a);
                });
    }

    function is_same_origin(w) {
        try {
            'random_prop' in w;
            return true;
        } catch (e) {
            return false;
        }
    }

    function supports_post_message(w)
    {
        var supports;
        var type;
        // Given IE  implements postMessage across nested iframes but not across
        // windows or tabs, you can't infer cross-origin communication from the presence
        // of postMessage on the current window object only.
        //
        // Touching the postMessage prop on a window can throw if the window is
        // not from the same origin AND post message is not supported in that
        // browser. So just doing an existence test here won't do, you also need
        // to wrap it in a try..cacth block.
        try {
            type = typeof w.postMessage;
            if (type === "function") {
                supports = true;
            }

            // IE8 supports postMessage, but implements it as a host object which
            // returns "object" as its `typeof`.
            else if (type === "object") {
                supports = true;
            }

            // This is the case where postMessage isn't supported AND accessing a
            // window property across origins does NOT throw (e.g. old Safari browser).
            else {
                supports = false;
            }
        } catch (e) {
            // This is the case where postMessage isn't supported AND accessing a
            // window property across origins throws (e.g. old Firefox browser).
            supports = false;
        }
        return supports;
    }
})();
// vim: set expandtab shiftwidth=4 tabstop=4:
