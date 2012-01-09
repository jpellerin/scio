from urllib2 import urlopen

from scio import client


class Client(client.Client):
    def __init__(self, transport=None):
        if transport is None:
            transport = urlopen
        self.transport = transport

    @property
    def service(self):
        return self._service(self)


class Attribute(object):
    def __init__(self, name, type_, min, max, namespace):
        self.name = name
        self.type = type_
        self.min = min
        self.max = max
        self.namespace = namespace


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


def safe_id(name):
    return name.replace('.', '_').replace('$', '__S__')



class Ref(object):
    def __init__(self, name):
        self.name = name


class TypeRegistry(object):
    """Registry of types and references"""

    ref = Ref

    def __init__(self):
        self._types = {}

    def register(self, cls):
        self._types[cls.__name__] = cls
        if cls._name != cls.__name__:
            self._types[cls._name] = cls
        return cls

    def types(self, client):
        return Types(client, self._types)

    def resolve_refs(self):
        for cn, t in self._types.items():
            print " * %s" % cn
            for entry in dir(t):
                item = getattr(t, entry)
                if isinstance(item, self.ref):
                    # example: _content_type
                    setattr(t, entry, self._types[item.name])
                elif hasattr(item, 'type'):
                    # example: AttributeDescriptor.type
                    if isinstance(item.type, self.ref):
                        item.type = self._types[item.type.name]



class Types(object):
    """Access to types in a client"""
    def __init__(self, client, types):
        self.client = client
        self._types = types

    def __getattr__(self, attr):
        # FIXME handle anytype
        try:
            return self._types[attr]
        except KeyError:
            raise AttributeError("No %s in types registry" % attr)
