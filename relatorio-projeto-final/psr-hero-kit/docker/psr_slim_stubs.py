"""Placeholders for Genesis dependencies that the HeRo scenarios never call.

Genesis imports these packages at module level, but the simulator only uses
rigid bodies with primitive collision shapes. The slim image leaves them out and
this finder (loaded by psr_slim_stubs.pth) serves an empty module for any of
them, including submodules. Anything that actually calls into one raises a clear
error instead of failing at import time.
"""
import importlib.abc
import importlib.machinery
import sys
import types

MISSING = {
    "DracoPy", "Imath", "OpenEXR", "av", "coacd", "fast_simplification", "igl",
    "matplotlib", "pygel3d", "pygltflib", "skimage", "tetgen", "xacro", "z3",
}


class _Missing:
    def __init__(self, path):
        self._path = path

    def __getattr__(self, attr):
        if attr.startswith("__"):
            raise AttributeError(attr)
        return _Missing(self._path + "." + attr)

    def __getitem__(self, key):
        return self

    def __mro_entries__(self, bases):  # allows "class X(missing.Base)"
        return (object,)

    def __call__(self, *args, **kwargs):
        raise RuntimeError("'%s' was called, but it is not installed in the PSR slim image" % self._path)


class _StubModule(types.ModuleType):
    def __getattr__(self, attr):
        if attr.startswith("__"):
            raise AttributeError(attr)
        return _Missing(self.__name__ + "." + attr)


class _Finder(importlib.abc.MetaPathFinder, importlib.abc.Loader):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split(".")[0] in MISSING:
            return importlib.machinery.ModuleSpec(fullname, self, is_package=True)
        return None

    def create_module(self, spec):
        module = _StubModule(spec.name)
        module.__path__ = []
        module.__version__ = "0.0.0"  # reads as too old, so optional features stay off
        return module

    def exec_module(self, module):
        pass


sys.meta_path.append(_Finder())  # last: a real installation always wins
