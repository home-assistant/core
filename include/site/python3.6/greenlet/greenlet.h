/* vim:set noet ts=8 sw=8 : */

/* Greenlet object interface */

#ifndef Py_GREENLETOBJECT_H
#define Py_GREENLETOBJECT_H

#include <Python.h>

#ifdef __cplusplus
extern "C" {
#endif

#define GREENLET_VERSION "0.4.14"

#if PY_VERSION_HEX >= 0x030700A3
#  define GREENLET_USE_EXC_INFO
#endif

typedef struct _greenlet {
	PyObject_HEAD
	char* stack_start;
	char* stack_stop;
	char* stack_copy;
	intptr_t stack_saved;
	struct _greenlet* stack_prev;
	struct _greenlet* parent;
	PyObject* run_info;
	struct _frame* top_frame;
	int recursion_depth;
	PyObject* weakreflist;
#ifdef GREENLET_USE_EXC_INFO
	_PyErr_StackItem* exc_info;
	_PyErr_StackItem exc_state;
#else
	PyObject* exc_type;
	PyObject* exc_value;
	PyObject* exc_traceback;
#endif
	PyObject* dict;
} PyGreenlet;

#define PyGreenlet_Check(op)      PyObject_TypeCheck(op, &PyGreenlet_Type)
#define PyGreenlet_MAIN(op)       (((PyGreenlet*)(op))->stack_stop == (char*) -1)
#define PyGreenlet_STARTED(op)    (((PyGreenlet*)(op))->stack_stop != NULL)
#define PyGreenlet_ACTIVE(op)     (((PyGreenlet*)(op))->stack_start != NULL)
#define PyGreenlet_GET_PARENT(op) (((PyGreenlet*)(op))->parent)

#if (PY_MAJOR_VERSION == 2 && PY_MINOR_VERSION >= 7) || (PY_MAJOR_VERSION == 3 && PY_MINOR_VERSION >= 1) || PY_MAJOR_VERSION > 3
#define GREENLET_USE_PYCAPSULE
#endif

/* C API functions */

/* Total number of symbols that are exported */
#define PyGreenlet_API_pointers  8

#define PyGreenlet_Type_NUM       0
#define PyExc_GreenletError_NUM   1
#define PyExc_GreenletExit_NUM    2

#define PyGreenlet_New_NUM        3
#define PyGreenlet_GetCurrent_NUM 4
#define PyGreenlet_Throw_NUM      5
#define PyGreenlet_Switch_NUM     6
#define PyGreenlet_SetParent_NUM  7

#ifndef GREENLET_MODULE
/* This section is used by modules that uses the greenlet C API */
static void **_PyGreenlet_API = NULL;

#define PyGreenlet_Type (*(PyTypeObject *) _PyGreenlet_API[PyGreenlet_Type_NUM])

#define PyExc_GreenletError \
	((PyObject *) _PyGreenlet_API[PyExc_GreenletError_NUM])

#define PyExc_GreenletExit \
	((PyObject *) _PyGreenlet_API[PyExc_GreenletExit_NUM])

/*
 * PyGreenlet_New(PyObject *args)
 *
 * greenlet.greenlet(run, parent=None)
 */
#define PyGreenlet_New \
	(* (PyGreenlet * (*)(PyObject *run, PyGreenlet *parent)) \
	 _PyGreenlet_API[PyGreenlet_New_NUM])

/*
 * PyGreenlet_GetCurrent(void)
 *
 * greenlet.getcurrent()
 */
#define PyGreenlet_GetCurrent \
	(* (PyGreenlet * (*)(void)) _PyGreenlet_API[PyGreenlet_GetCurrent_NUM])

/*
 * PyGreenlet_Throw(
 *         PyGreenlet *greenlet,
 *         PyObject *typ,
 *         PyObject *val,
 *         PyObject *tb)
 *
 * g.throw(...)
 */
#define PyGreenlet_Throw \
	(* (PyObject * (*) \
	    (PyGreenlet *self, PyObject *typ, PyObject *val, PyObject *tb)) \
	 _PyGreenlet_API[PyGreenlet_Throw_NUM])

/*
 * PyGreenlet_Switch(PyGreenlet *greenlet, PyObject *args)
 *
 * g.switch(*args, **kwargs)
 */
#define PyGreenlet_Switch \
	(* (PyObject * (*)(PyGreenlet *greenlet, PyObject *args, PyObject *kwargs)) \
	 _PyGreenlet_API[PyGreenlet_Switch_NUM])

/*
 * PyGreenlet_SetParent(PyObject *greenlet, PyObject *new_parent)
 *
 * g.parent = new_parent
 */
#define PyGreenlet_SetParent \
	(* (int (*)(PyGreenlet *greenlet, PyGreenlet *nparent)) \
	 _PyGreenlet_API[PyGreenlet_SetParent_NUM])

/* Macro that imports greenlet and initializes C API */
#ifdef GREENLET_USE_PYCAPSULE
#define PyGreenlet_Import() \
{ \
	_PyGreenlet_API = (void**)PyCapsule_Import("greenlet._C_API", 0); \
}
#else
#define PyGreenlet_Import() \
{ \
	PyObject *module = PyImport_ImportModule("greenlet"); \
	if (module != NULL) { \
		PyObject *c_api_object = PyObject_GetAttrString( \
			module, "_C_API"); \
		if (c_api_object != NULL && PyCObject_Check(c_api_object)) { \
			_PyGreenlet_API = \
				(void **) PyCObject_AsVoidPtr(c_api_object); \
			Py_DECREF(c_api_object); \
		} \
		Py_DECREF(module); \
	} \
}
#endif

#endif /* GREENLET_MODULE */

#ifdef __cplusplus
}
#endif
#endif /* !Py_GREENLETOBJECT_H */
