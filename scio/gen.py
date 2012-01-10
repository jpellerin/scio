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

import logging
import sys

import jinja2

import scio.client
from scio import static

log = logging.getLogger(__name__)


def main():
    """Generate client classes

    Generate client classes for all WSDL files listed on the command line.
    Note that the class name generated is always "Client", so if you
    generate more than one, you should split the output up into
    multiple modules.

    """
    for wsdl_file in sys.argv[1:]:
        with open(wsdl_file, 'r') as fh:
            client = scio.client.Client(fh)
            print gen(client)


def gen(client, template='scio/static_client.tpl'):
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
    types = [typeinfo(p, getattr(client.type, p))
             for p in dir(client.type)
             if not p.startswith('_')]
    ctx['types'] = [t for t in sort_deps(types)]
    return template.render(**ctx)


def typeinfo(n, p):
    info = {}
    info['name'] = p.__name__
    info['deps'] = [] # classes this class depends on
    info['class_name'] = static.safe_id(p.__name__)
    info['bases'] = [dep_class(x, info['deps']) for x in p.__bases__]
    info['fields'] = fields = []
    if hasattr(p, '_schema'):
        info['schema'] = p._schema
    quoted_fields = ('xsd_type', '_tag', '_namespace', '_values',
                     '_type_attr', '_type_value')
    for field in quoted_fields:
        if field in p.__dict__:
            fields.append((field, repr(getattr(p, field))))

    children = []
    if hasattr(p, '_children'):
        for ch in p._children:
            children.append(static.safe_id(ch.name))
            fields.append((static.safe_id(ch.name), 'client.AttributeDescriptor(name=%r, type_=%s, min=%r, max=%r, namespace=%r)' % (ch.name, ref_class(ch.type), ch.min, ch.max, ch.namespace)))
    fields.append(('_children', '[%s]' % ', '.join(children)))

    attributes = []
    if hasattr(p, '_attributes'):
        for ch in p._attributes:
            attributes.append(static.safe_id(ch.name))
            fields.append((static.safe_id(ch.name), 'client.AttributeDescriptor(name=%r, type_=%s, min=%r, max=%r, namespace=%r)' % (ch.name, ref_class(ch.type), ch.min, ch.max, ch.namespace)))
    fields.append(('_attributes', '[%s]' % ', '.join(attributes)))

    if hasattr(p, '_substitutions'):
        subs = {}
        for name, scls in p._substitutions.items():
            subs[name] = ref_class(scls)
        fields.append(('_substitutions', subs))

    type_fields = ('_content_type', '_arrayType')
    for field in type_fields:
        if hasattr(p, field) and getattr(p, field) is not None:
            info[field] = ref_class(getattr(p, field))
            fields.append((field, info[field]))
    return info


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


def ref_class(cls):
    """Class reference that may be resolved late"""
    qn = qualifed_classname(cls)
    if qn.startswith('client.') or qn == 'None':
        return qn
    elif qn == 'AnyType':
        return 'Client._types.AnyType'
    return 'Client.ref(%r)' % qn


def dep_class(cls, deplist):
    """Class reference that must be resolved before code output"""
    qn = qualifed_classname(cls)
    if not qn.startswith('client.') or qn == 'None':
        deplist.append(qn)
    return qn


def svc_qual_classname(cls):
    qn = qualifed_classname(cls)
    if qn == 'None':
        return qn
    if qn.startswith('client.'):
        return qn
    if qn == 'AnyType':
        return 'Client._types.AnyType'
    return 'client_.type.%s' % qn


def qualifed_classname(cls):
    if cls is None:
        return 'None'
    if isinstance(cls, scio.client.AnyType):
        # special case, these are instances not subclasses
        return 'AnyType'
    if cls.__name__ in dir(scio.client):
        return "client.%s" % cls.__name__
    return static.safe_id(cls.__name__)


def sort_deps(types):
    ready = []
    deps = []
    pushed = set()
    for t in types:
        if t['deps']:
            deps.append(t)
        else:
            ready.append(t)
    if not deps:
        for t in types:
            yield t

    while ready:
        t = ready.pop()
        yield t
        pushed.add(t['class_name'])
        log.debug(" * %s" % t['class_name'])
        for dt in deps:
            if dt['class_name'] in pushed:
                continue
            if _ready(dt, pushed):
                ready.append(dt)
                log.debug(" + %s" % dt['class_name'])
    # one more time in case the last thing pushed
    not_pushed = set([t['class_name'] for t in deps]) - pushed
    if not_pushed:
        log.debug("Some classes not pushed: %s", set(not_pushed))
        unresolved = {}
        for t in deps:
            missing = set(t['deps']) - pushed
            if missing:
                unresolved[t['class_name']] = sorted(list(missing))
        raise RuntimeError("Unresolved class dependencies: %s" % unresolved)


def _ready(t, pushed):
    if set(t['deps']) - pushed:
        return False
    return True


if __name__ == '__main__':
    main()
