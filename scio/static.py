# client.py -- soap classes for input and output
#
# Copyright (c) 2011, Leapfrog Online, LLC
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#     * Redistributions of source code must retain the above copyright
#       notice, this list of conditions and the following disclaimer.
#     * Redistributions in binary form must reproduce the above copyright
#       notice, this list of conditions and the following disclaimer in the
#       documentation and/or other materials provided with the distribution.
#     * Neither the name of the Leapfrog Online, LLC nor the
#       names of its contributors may be used to endorse or promote products
#       derived from this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
# ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL <COPYRIGHT HOLDER> BE LIABLE FOR ANY
# DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
# (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
# ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
# SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

from urllib2 import urlopen

from scio import client


class Client(client.Client):
    """Base class for statically-generated SOAP clients

    Statically-generated SOAP client classes are all subclasses
    of this class.

    :param transport: The transport mechanism for communicating with
                      target services. Default: :func:`urlopen`.
    """
    methodCallClass = client.MethodCall
    methodClass = client.Method
    inputClass = client.InputMessage
    outputClass = client.OutputMessage
    # Note: _types is a class-level entity but only defined in
    # subclasses to avoid borging typemap into all subclasses
    # subclasses must set _types = static.TypeRegistry()
    _types = None

    def __init__(self, transport=None):
        if transport is None:
            transport = urlopen
        self.transport = transport

    @property
    def service(self):
        return self._service(self)

    @property
    def type(self):
        return self._types(self)

    @classmethod
    def register(cls, name, type_):
        """Register a type under the given name"""
        return cls._types.register(name, type_)

    @classmethod
    def ref(cls, name):
        return cls._types.ref(name)

    @classmethod
    def resolve_refs(cls):
        cls._types.resolve_refs()


class Schema(client.Schema):
    def __init__(self, nsmap, targetNamespace, qualified):
        self._nsmap = nsmap
        self._targetNamespace = targetNamespace
        self._qualified = qualified

    @property
    def nsmap(self):
        return self._nsmap

    @property
    def targetNamespace(self):
        return self._targetNamespace

    @property
    def qualified(self):
        return self._qualified


class Ref(object):
    def __init__(self, name):
        self.name = name


class TypeRegistry(object):
    """Registry of types and references"""

    ref = Ref

    def __init__(self):
        self._types = client.Factory._typemap.copy()

    def __call__(self, client):
        return Types(client, self._types)

    def register(self, name, cls):
        self._types[name] = cls
        cls._resolver = self

    def resolve_refs(self):
        for cn, t in self._types.items():
            for entry in dir(t):
                item = getattr(t, entry)
                if isinstance(item, self.ref):
                    # example: _content_type
                    setattr(t, entry, self._find(item.name))
                elif hasattr(item, 'type'):
                    # example: AttributeDescriptor.type
                    if isinstance(item.type, self.ref):
                        item.type = self._find(item.type.name)
                elif entry == '_substitutions' and item:
                    for k, v in item.items():
                        if isinstance(v, self.ref):
                            item[k] = self._find(v.name)

    def _find(self, valtype):
        return self._types[valtype]

    @property
    def AnyType(self):
        return AnyType(self)


class Types(object):
    """Access to types in a client"""
    def __init__(self, client, types):
        self._client = client
        self._types = types

    def __getattr__(self, attr):
        try:
            return self._types[attr]
        except KeyError:
            raise AttributeError("No %s in types registry" % attr)


class AnyType(client.AnyType):
    def __call__(self, value=None, **kw):
        if value is None:
            return
        valtype = client.xsi_type(value)
        if not valtype:
            return
        # "client" not really -- it's the type registry
        valcls = self.client._find(valtype)
        return valcls(value, **kw)


def safe_id(name):
    if name == 'None':
        return 'None_'
    return name.replace('.', '_').replace('$', '__S__')
