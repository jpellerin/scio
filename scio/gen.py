# gen.py -- soap classes for input and output
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

import logging
import os
import sys

import jinja2

import scio.client
from scio import static

log = logging.getLogger(__name__)
TEMPLATE = os.path.abspath(
    os.path.join(os.path.dirname(__file__), 'static_client.tpl'))

def main():
    """Generate client classes

    Generate client classes for all WSDL files listed on the command line.
    Note that the class name generated is always "Client", so if you
    generate more than one, you should split the output up into
    multiple modules.

    """
    logging.basicConfig(level=logging.DEBUG)
    for wsdl_file in sys.argv[1:]:
        with open(wsdl_file, 'r') as fh:
            client = scio.client.Client(fh)
            print gen(client)


def gen(client, template=TEMPLATE):
    """Generate code for a :class:`scio.client.Client` class.

    :param client: A `scio.client.Client` class generated from a
                   WSDL file.
    :param template: The jinja2 template to use for code generation.
    :returns: Code string.

    """
    template = jinja2.Template(open(template, 'r').read())
    ctx = {}
    ctx['methods'] = [methodinfo(getattr(client.service, s).method)
                      for s in dir(client.service)
                      if (not s.startswith('_') and not
                          s == 'method_class')]
    # this will fail if any base classes are in circular relationships
    types = list(sort_deps([typeinfo(entry, getattr(client.type, entry))
                            for entry in dir(client.type)
                            if not entry.startswith('_')]))
    # now sort again to catch circular refs in attributes
    types = list(sort_deps(types,
                           key=lambda t: t['deps'] + t['refs'],
                           allow_refs=True))
    log.debug("type order: %s", [t['class_name'] for t in types])
    ctx['circular_refs'] = mark_resolved_refs(types)
    ctx['types'] = types
    return template.render(**ctx)


def typeinfo(name, typecls):
    info = {}
    info['name'] = name
    info['deps'] = []  # classes this class absolutely depends on
    info['class_name'] = static.safe_id(typecls.__name__)
    # is this class just an alias to another class?
    # eg 'char' being another name for StringType
    info['is_alias'] = name != typecls.__name__
    info['qualified_name'] = svc_qual_classname(typecls)
    info['bases'] = [dep_class(x, info['deps']) for x in typecls.__bases__]
    info['refs'] = []  # other type classes I refer to
    info['unresolved'] = set()  # class references not resolved by sorting
    info['fields'] = fields = []
    if hasattr(typecls, '_schema'):
        info['schema'] = typecls._schema
    quoted_fields = ('xsd_type', '_tag', '_namespace', '_values',
                     '_type_attr', '_type_value', '_abstract', 'any_attribute')
    for field in quoted_fields:
        if field in typecls.__dict__:
            fields.append((field, repr(getattr(typecls, field))))

    children = []
    if hasattr(typecls, '_children'):
        for ch in typecls._children:
            children.append(static.safe_id(ch.name))
            fields.append((static.safe_id(ch.name),
                           Attr(ch.name, Ref(dep_class(ch.type, info['refs'])),
                                ch.min, ch.max, ch.namespace))
                          )
    if children:
        fields.append(('_children', '[%s]' % ', '.join(children)))

    attributes = []
    if hasattr(typecls, '_attributes'):
        for ch in typecls._attributes:
            attributes.append(static.safe_id(ch.name))
            fields.append((static.safe_id(ch.name),
                           Attr(ch.name, Ref(dep_class(ch.type, info['refs'])),
                                ch.min, ch.max, ch.namespace))
                          )
    if attributes:
        fields.append(('_attributes', '[%s]' % ', '.join(attributes)))

    if hasattr(typecls, '_substitutions'):
        subs = {}
        for name, scls in typecls._substitutions.items():
            subs[name] = Ref(dep_class(scls, info['refs']))
        if subs:
            fields.append(('_substitutions', subs))

    type_fields = ('_content_type', '_arrayType')
    for field in type_fields:
        if hasattr(typecls, field) and getattr(typecls, field) is not None:
            info[field] = Ref(dep_class(getattr(typecls, field), info['refs']))
            fields.append((field, info[field]))

    # enum values
    if hasattr(typecls, '_values'):
        for val in typecls._values:
            fields.append((static.safe_id(val), repr(val)))

    return info


def mark_resolved_refs(types):
    unresolved = False
    for t in types:
        if not t['unresolved']:
            continue
        for field, val in t['fields']:
            if isinstance(val, Attr):
                if val.ref_type.ref_type in t['unresolved']:
                    val.ref_type.resolved = False
                    unresolved = True
            elif isinstance(val, dict):
                # _substitutions
                for k, v in val.items():
                    if isinstance(v, Ref):
                        if v.ref_type in t['unresolved']:
                            v.resolved = False
                            unresolved = True
    return unresolved


class Ref(object):
    def __init__(self, ref_type):
        self.ref_type = ref_type
        self.resolved = True

    def __str__(self):
        if self.resolved:
            return self.ref_type
        else:
            return 'Client.ref(%r)' % self.ref_type

    def __repr__(self):
        return self.__str__()


class Attr(object):
    def __init__(self, name, ref_type, min, max, namespace):
        self.name = name
        self.ref_type = ref_type
        self.min = min
        self.max = max
        self.namespace = namespace

    def __str__(self):
        info = {
            'name': self.name,
            'min': self.min,
            'max': self.max,
            'namespace': self.namespace,
            'type': self.ref_type
            }

        tpl = 'client.AttributeDescriptor(name=%(name)r, type_=%(type)s'
        if self.min is not None:
            tpl += ', min=%(min)r'
        if self.max is not None:
            tpl += ', max=%(max)r'
        if self.namespace is not None:
            tpl += ', namespace=%(namespace)r'
        tpl += ')'
        return tpl % info

def dep_class(cls, deplist):
    """Class reference that must be resolved before code output"""
    qn = qualifed_classname(cls)
    if (not qn.lower().startswith('client.') and
        qn != 'None' and
        qn not in __builtins__):
        deplist.append(qn)
    return qn


def svc_qual_classname(cls):
    qn = qualifed_classname(cls)
    if qn == 'None':
        return qn
    if qn.lower().startswith('client.'):
        return qn
    return 'client_.type.%s' % qn


def qualifed_classname(cls):
    if cls is None:
        return 'None'
    if isinstance(cls, scio.client.AnyType):
        # special case, these are instances not subclasses
        return 'Client._types.AnyType'
    if cls.__name__ in dir(scio.client):
        return "client.%s" % cls.__name__
    return static.safe_id(cls.__name__)


def sort_deps(types, key=lambda t: t['deps'], allow_refs=False):
    ready = []
    deps = []
    pushed = set()
    for t in types:
        if key(t):
            deps.append(t)
        else:
            ready.append(t)
    if not deps:
        for t in types:
            yield t
        return

    while ready:
        t = ready.pop()
        if not t['class_name'] in pushed:
            yield t
            pushed.add(t['class_name'])
            log.debug(" * %s" % t['class_name'])
        for dt in deps:
            if dt['class_name'] in pushed:
                continue
            if _ready(dt, key, pushed):
                ready.append(dt)
                log.debug("  -> %s" % dt['class_name'])
    # check for unresolved refs (cycles in the graph)
    not_pushed = set([t['class_name'] for t in deps]) - pushed
    if not_pushed:
        log.debug("Some classes not pushed: %s", set(not_pushed))
        unresolved = {}
        missing_types = []
        for t in deps:
            missing = set(key(t)) - pushed
            if missing:
                t['unresolved'] = missing
                unresolved[t['class_name']] = sorted(list(missing))
                missing_types.append(t)
        if not allow_refs:
            raise RuntimeError("Unresolved class dependencies: %s" % unresolved)
        for t in missing_types:
            yield t


def _ready(t, key, pushed):
    if set(key(t)) - pushed:
        return False
    return True


def methodinfo(m):
    info = {'location': m.location,
            'name': m.name,
            'action': m.action,
            'input': {'tag': m.input.tag,
                      'namespace': m.input.namespace,
                      'style': m.input.style,
                      'literal': m.input.literal,
                      'parts': [(p[0], svc_qual_classname(p[1]))
                                for p in m.input.parts],
                      'headers': [(p[0], svc_qual_classname(p[1]))
                                for p in m.input.headers]},
            'output': {'tag': m.output.tag,
                       'namespace': m.output.namespace,
                       'parts': [(p[0], svc_qual_classname(p[1]))
                                 for p in m.output.parts],
                       'headers': [(p[0], svc_qual_classname(p[1]))
                                   for p in m.output.headers]
                       }
            }
    return info


if __name__ == '__main__':
    main()
