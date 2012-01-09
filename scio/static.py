from urllib2 import urlopen

from scio import client


class Client(client.Client):
    def __init__(self, transport=None):
        if transport is None:
            transport = urlopen
        self.transport = transport


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
