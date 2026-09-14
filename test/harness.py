#!/usr/bin/env python3
"""Offline test harness for ReviewGuard. No chain, no network, no model, no
genlayer install — stdlib only.

The runtime stub is ported from the proven DeFiLens/Sentinel harness and kept
namespaced for the v0.6 runner: `gl.contract.Contract`, `gl.storage.TreeMap`,
`gl.storage.DynArray`, `gl.storage.allow`, `gl.message.raw`,
`gl.contract.get_at`. A stub shaped like the OLD namespace would let every test
pass against a contract the current runner cannot even load.

Two of its behaviours are load-bearing and easy to get wrong:

  * a `TreeMap` with a SCALAR value type answers a missing key with that type's
    ZERO, not with `None`, so a presence check written as `is not None` matches
    everything. Struct-valued maps DO answer `None`.
  * `DynArray.append_new_get()` returns a REFERENCE to the element the array
    holds, not a copy — a stub that returned a copy would let a test pass while
    every position written on chain stayed zero.

`gl.nondet.web.render` is stubbed against a PAGE MAP of text captured from real
rendered pages (test/fixtures/*.txt, pulled off studio-dev by the render probe).
A URL with no entry is a hard failure rather than a silent empty body, because
an unstubbed fetch returning "" looks exactly like a page with no reviews.
"""

import ast
import builtins
import json
import sys
import types
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "contracts" / "ReviewGuard.py"
CONSUMER = ROOT / "contracts" / "MarketplaceConsumer.py"
FIXTURE_DIR = ROOT / "test" / "fixtures"

GEN = 10 ** 18
MINUTE = 60
HOUR = 3600
DAY = 86400

# ---------------------------------------------------------------------------
# runtime stub
#
# Ported from the proven Sentinel/VoteGuard harness and RE-NAMESPACED for the
# v0.6 runner: `gl.contract.Contract`, `gl.storage.TreeMap`,
# `gl.storage.DynArray`, `gl.storage.allow`, `gl.message.raw`,
# `gl.contract.get_at`. A stub still shaped like the old namespace would let
# every test pass against a contract the current runner cannot even load.
#
# The TreeMap missing-key semantics in particular are load-bearing: on chain a
# map with a SCALAR value type answers a missing key with that type's ZERO, not
# with None, so a presence check written as `is not None` matches everything.
# A stub that returned None could never reproduce that bug.
# ---------------------------------------------------------------------------

_UNSET = object()


class _UserError(Exception):
    def __init__(self, message: str = ""):
        super().__init__(message)
        self.message = message


def _offline(*_a, **_k):
    raise AssertionError("offline tests must not touch the network or a model")


class _Return:
    """gl.vm.Return — a leader result carrying its calldata."""

    def __init__(self, calldata):
        self.calldata = calldata


class _Rollback:
    def __init__(self, message=""):
        self.message = message


class _Addr:
    """Address. Compared and keyed by its lowercase text, like the real one."""

    def __init__(self, value=""):
        v = str(value)
        if not v.startswith("0x") or len(v) != 42:
            raise ValueError("not an address: " + v[:60])
        self._v = v.lower()

    @property
    def as_hex(self):
        return self._v

    def __str__(self):
        return self._v

    def __repr__(self):
        return "Address(" + self._v + ")"

    def __eq__(self, other):
        return str(self) == str(other)

    def __hash__(self):
        return hash(self._v)


class _TreeMap(dict):
    """Models the runtime's TreeMap, INCLUDING what it returns for a key that is
    not there.

    On chain a `TreeMap[str, u32]` answers a missing key with the value type's
    ZERO, not with None, so `if m.get(k) is not None` is always true and a
    presence check written that way rejects everything. Struct-valued maps do
    answer None, which is why `if found is None` is correct for those."""

    _value_type = None

    @classmethod
    def __class_getitem__(cls, item):
        vt = item[1] if isinstance(item, tuple) and len(item) > 1 else None
        return type("_TreeMapOf", (cls,), {"_value_type": vt})

    def _k(self, key):
        return str(key) if isinstance(key, _Addr) else key

    def _missing(self):
        vt = type(self)._value_type
        if vt is None:
            return None
        name = getattr(vt, "__name__", str(vt))
        if name.startswith("_TreeMap") or name.startswith("_DynArray"):
            return _zero_for(vt)
        if vt is int or vt is str or vt is bool:
            return _zero_for(vt)
        if hasattr(vt, "__annotations__") and getattr(vt, "__annotations__"):
            return None
        return _zero_for(vt)

    def get(self, key, default=_UNSET):
        k = self._k(key)
        if k in self:
            return dict.__getitem__(self, k)
        if default is not _UNSET:
            return default
        return self._missing()

    def __contains__(self, key):
        return dict.__contains__(self, self._k(key))

    def __setitem__(self, key, value):
        dict.__setitem__(self, self._k(key), value)

    def __getitem__(self, key):
        return dict.__getitem__(self, self._k(key))

    def __delitem__(self, key):
        dict.__delitem__(self, self._k(key))

    def get_or_insert_default(self, key):
        k = self._k(key)
        if k not in self:
            dict.__setitem__(self, k, self._factory())
        return dict.__getitem__(self, k)


class _DynArray(list):
    """Models DynArray, INCLUDING `append_new_get()`.

    On chain a DynArray of structs cannot be appended to with a constructed
    value — storage objects are not constructible in contract code — so the
    runtime allocates a zeroed element in place and hands back a REFERENCE to
    it. Reproducing that matters for more than API coverage: the returned object
    must be the SAME object the array holds, or a later mutation through the
    reference would be invisible in the array, and a test would pass while every
    position written on chain stayed zero."""

    _elem_type = None

    @classmethod
    def __class_getitem__(cls, item):
        return type("_DynArrayOf", (cls,), {"_elem_type": item})

    def append_new_get(self):
        elem = type(self)._elem_type
        value = _make_struct(elem) if elem is not None and \
            hasattr(elem, "__annotations__") else _zero_for(elem)
        list.append(self, value)
        return value


def _zero_for(annotation):
    """The value the runtime auto-initialises a storage field to."""
    name = getattr(annotation, "__name__", str(annotation))
    if annotation is bool or name == "bool":
        return False
    if annotation is str or name == "str":
        return ""
    if name == "_Addr" or name == "Address":
        return _Addr("0x" + "0" * 40)
    if name.startswith("_TreeMap") or name == "TreeMap":
        return annotation() if isinstance(annotation, type) else _TreeMap()
    if name.startswith("_DynArray") or name == "DynArray":
        return annotation() if isinstance(annotation, type) else _DynArray()
    if name.startswith("u") or name.startswith("i"):
        return 0
    if hasattr(annotation, "__annotations__"):
        return _make_struct(annotation)
    return 0


def _make_struct(cls):
    obj = cls.__new__(cls)
    for field, ann in getattr(cls, "__annotations__", {}).items():
        setattr(obj, field, _zero_for(ann))
    return obj


class _Contract:
    """gl.contract.Contract. Storage fields are declared as class annotations and
    never assigned before use, exactly as on chain, so they are created on
    demand."""

    balance = 0

    def __getattr__(self, name):
        anns = {}
        for klass in reversed(type(self).__mro__):
            anns.update(getattr(klass, "__annotations__", {}))
        if name in anns:
            value = _zero_for(anns[name])
            if isinstance(value, _TreeMap):
                value._factory = _factory_for(type(self), name)
            object.__setattr__(self, name, value)
            return value
        raise AttributeError(name)


_STRUCT_HINTS = {}


def _factory_for(contract_cls, field):
    target = _STRUCT_HINTS.get((contract_cls.__name__, field))
    if target is None:
        return lambda: _DynArray()
    return lambda: _make_struct(target)


TRANSFERS = []


def _evm_contract_interface(cls):
    """gl.evm.contract_interface. Still stubbed because the namespace exists,
    but NOTHING in this project uses it for a payout any more — see _Proxy."""

    class _Handle:
        def __init__(self, to):
            self.to = to

    return _Handle


ORACLE = {"impl": None}


class _Proxy:
    """gl.contract.Proxy. `.view()` returns whatever instance the test wired in
    as the oracle, so a consumer test exercises the REAL DeFiLens across the
    call boundary rather than a hand-written fake that agrees with itself.

    `.emit()` is the v0.6 spelling of a write; the old `.write()` is NOT
    provided, so a contract still using it fails here rather than on chain."""

    def __init__(self, address):
        self.address = address

    def view(self, **_k):
        return ORACLE["impl"]

    def emit(self, **_k):
        """A METHOD GETTER, exactly like the runner's.

        It records NOTHING. That is the whole point: on chain, `emit()` with no
        method call after it constructs a namespace and drops it, posting no
        message. A stub that treated a bare `emit(value=…)` as a transfer would
        make the offline suite agree with a contract that silently never pays —
        which is precisely the bug that shipped and had to be caught on chain,
        by comparing the contract's real balance before and after a claim."""
        return ORACLE["impl"]

    def emit_transfer(self, value, **_k):
        if int(value) <= 0:
            raise ValueError("value must be greater than 0 for emit_transfer")
        TRANSFERS.append((str(self.address), int(value)))


def _proxy_for(address):
    return _Proxy(address)


def _contract_interface(cls):
    """gl.contract.interface — a factory that turns an address into a Proxy."""
    return _proxy_for


MESSAGE = types.SimpleNamespace(sender_address=_Addr("0x" + "a" * 40), value=0,
                                raw={"datetime": "2026-09-11T12:00:00Z"})

LAST_CONSENSUS = {}
# What the stubbed network answers. Keyed by URL; a URL with no entry is a
# hard failure rather than a silent empty body, because an unstubbed fetch that
# returned "" would look exactly like a protocol with no data.
FETCH_MAP = {}
PROMPT_ANSWERS = []
PROMPT_LOG = []


def _web_request(url, method="GET", **_k):
    if url not in FETCH_MAP:
        raise AssertionError("test fetched an unstubbed URL: " + str(url))
    status, body = FETCH_MAP[url]
    return types.SimpleNamespace(status_code=status, body=body)


# What a rendered page answers with. Keyed by the CANONICAL fetch URL the
# contract builds, never by the URL a caller submitted — so a test that stubs
# the submitted URL and forgets the canonicalisation fails loudly instead of
# quietly testing nothing.
PAGE_MAP = {}
RENDER_LOG = []


def _web_render(url, mode="text", wait_after_loaded=None, **_k):
    RENDER_LOG.append(str(url))
    if url not in PAGE_MAP:
        raise AssertionError("test rendered an unstubbed URL: " + str(url))
    page = PAGE_MAP[url]
    if isinstance(page, Exception):
        raise page
    return page


def fixture(name: str) -> str:
    """Rendered page text captured off studio-dev by the render probe. These
    are the bytes a validator ACTUALLY saw — an extraction test written against
    invented text says nothing about on-chain behaviour."""
    return (FIXTURE_DIR / (name + ".txt")).read_text(encoding="utf8")


def _exec_prompt(prompt, **_k):
    PROMPT_LOG.append(prompt)
    if not PROMPT_ANSWERS:
        raise AssertionError("model called with no queued answer")
    return PROMPT_ANSWERS.pop(0)


def _run_nondet(leader_fn, validator_fn):
    """Runs the real consensus shape offline: the leader produces a result, a
    validator is handed it as gl.vm.Return and must agree, and disagreement is
    surfaced as UNDETERMINED rather than silently ignored.

    The validator runs the SAME closure the contract gave it, so a validator
    that re-fetches really does re-fetch here too."""
    result = leader_fn()
    agreed = validator_fn(_Return(result))
    LAST_CONSENSUS["agreed"] = bool(agreed)
    LAST_CONSENSUS["leader"] = result
    if not agreed:
        raise AssertionError("UNDETERMINED: validator did not agree with leader")
    return result


def _install_stub():
    if "genlayer" in sys.modules:
        return
    mod = types.ModuleType("genlayer")
    vm = types.SimpleNamespace(UserError=_UserError, Return=_Return,
                               Result=object, Rollback=_Rollback,
                               run_nondet=_run_nondet,
                               run_nondet_unsafe=_run_nondet)
    web = types.SimpleNamespace(request=_web_request, render=_web_render,
                                get=_offline)
    nondet = types.SimpleNamespace(web=web, exec_prompt=_exec_prompt)
    public = types.SimpleNamespace()
    public.view = lambda fn: fn
    write = lambda fn: fn
    write.payable = lambda fn: fn
    public.write = write
    evm = types.SimpleNamespace(contract_interface=_evm_contract_interface)
    storage = types.SimpleNamespace(TreeMap=_TreeMap, DynArray=_DynArray,
                                    allow=lambda cls: cls)
    contract_ns = types.SimpleNamespace(Contract=_Contract,
                                        get_at=lambda a: _proxy_for(a),
                                        interface=_contract_interface)
    mod.gl = types.SimpleNamespace(vm=vm, nondet=nondet, public=public, evm=evm,
                                   storage=storage, message=MESSAGE,
                                   contract=contract_ns)
    mod.Address = _Addr
    mod.TreeMap = _TreeMap
    mod.DynArray = _DynArray
    for name in ("u8", "u16", "u32", "u64", "u128", "u256", "i8", "i16", "i32",
                 "i64", "bigint"):
        mod.__dict__[name] = int
    sys.modules["genlayer"] = mod
    sys.modules["genlayer.gl"] = mod.gl


def load_pure(path: Path, name: str) -> types.ModuleType:
    """Exec only the pure region — every top-level statement before the first
    class definition. That region never touches storage."""
    tree = ast.parse(path.read_text(encoding="utf8"))
    cut = len(tree.body)
    for i, node in enumerate(tree.body):
        if isinstance(node, ast.ClassDef):
            cut = i
            break
    tree.body = tree.body[:cut]
    module = types.ModuleType(name)
    module.__file__ = str(path)
    exec(compile(tree, str(path), "exec"), module.__dict__)
    return module


def load_full(path: Path, name: str) -> types.ModuleType:
    """Exec the WHOLE file so the contract class itself can be driven."""
    module = types.ModuleType(name)
    module.__file__ = str(path)
    exec(compile(path.read_text(encoding="utf8"), str(path), "exec"),
         module.__dict__)
    return module


# ---------------------------------------------------------------------------
# static undefined-name check
#
# The pure region can be exec'd and exercised, but a name error inside a
# @gl.public.view only fires when that view is called on chain — after a deploy,
# after a wait, on a network. This walks every scope in the file, class bodies
# and comprehensions included, and reports any Load of a name nothing bound.
# ---------------------------------------------------------------------------

def _own_nodes(scope):
    out = []

    def rec(node):
        for sub in ast.iter_child_nodes(node):
            if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef,
                                ast.Lambda)):
                continue
            out.append(sub)
            rec(sub)
    rec(scope)
    return out


def _child_scopes(scope):
    out = []

    def rec(node):
        for sub in ast.iter_child_nodes(node):
            if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef,
                                ast.Lambda)):
                out.append(sub)
            else:
                rec(sub)
    rec(scope)
    return out


def _bound_names(scope) -> set:
    out = set()
    args = getattr(scope, "args", None)
    if args is not None:
        for group in (args.posonlyargs, args.args, args.kwonlyargs):
            for a in group:
                out.add(a.arg)
        if args.vararg:
            out.add(args.vararg.arg)
        if args.kwarg:
            out.add(args.kwarg.arg)
    for sub in _own_nodes(scope):
        if isinstance(sub, ast.Name) and isinstance(sub.ctx, ast.Store):
            out.add(sub.id)
        elif isinstance(sub, ast.ExceptHandler) and sub.name:
            out.add(sub.name)
        elif isinstance(sub, (ast.Global, ast.Nonlocal)):
            out.update(sub.names)
        elif isinstance(sub, (ast.Import, ast.ImportFrom)):
            for al in sub.names:
                out.add((al.asname or al.name).split(".")[0])
        elif isinstance(sub, ast.comprehension):
            for nm in ast.walk(sub.target):
                if isinstance(nm, ast.Name):
                    out.add(nm.id)
    for sub in _child_scopes(scope):
        if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef)):
            out.add(sub.name)
    for sub in _own_nodes(scope):
        if isinstance(sub, ast.ClassDef):
            out.add(sub.name)
    return out


def undefined_names(path: Path) -> list:
    tree = ast.parse(path.read_text(encoding="utf8"))
    module_names = _bound_names(tree) | {
        "gl", "u8", "u16", "u32", "u64", "u128", "u256", "i8", "i16", "i32",
        "i64", "Address", "TreeMap", "DynArray", "bigint", "Array", "self"}
    builtin_names = set(dir(builtins))
    problems = []

    def visit(scope, enclosing, label):
        scope_names = enclosing | _bound_names(scope)
        for sub in _own_nodes(scope):
            if isinstance(sub, ast.Name) and isinstance(sub.ctx, ast.Load):
                if sub.id not in scope_names and sub.id not in builtin_names:
                    problems.append((label, sub.id, sub.lineno))
        for child in _child_scopes(scope):
            visit(child, scope_names,
                  label + "." + getattr(child, "name", "<lambda>"))

    for child in _child_scopes(tree):
        visit(child, module_names, getattr(child, "name", "<lambda>"))
    for node in _own_nodes(tree):
        if isinstance(node, ast.ClassDef):
            for child in _child_scopes(node):
                visit(child, module_names | _bound_names(node),
                      node.name + "." + getattr(child, "name", "<lambda>"))
    return problems


