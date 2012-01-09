import logging
import sys

import jinja2

import scio.client
from scio import static

log = logging.getLogger(__name__)


def main(wsdl_file, template='scio/static_client.tpl'):
    with open(wsdl_file, 'r') as fh:
        client = scio.client.Client(fh)
        print gen(client, template)


def gen(client, template='scio/static_client.tpl'):
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
            fields.append((static.safe_id(ch.name), 'client.AttributeDescriptor(name=%r, type_=%s, min=%r, max=%r, namespace=%r)' % (ch.name, dep_class(ch.type, info['deps']), ch.min, ch.max, ch.namespace)))
    fields.append(('_children', '[%s]' % ', '.join(children)))

    attributes = []
    if hasattr(p, '_attributes'):
        for ch in p._attributes:
            attributes.append(static.safe_id(ch.name))
            fields.append((static.safe_id(ch.name), 'client.AttributeDescriptor(name=%r, type_=%s, min=%r, max=%r, namespace=%r)' % (ch.name, dep_class(ch.type, info['deps']), ch.min, ch.max, ch.namespace)))
    fields.append(('_attributes', '[%s]' % ', '.join(attributes)))

    type_fields = ('_content_type', '_arrayType')
    for field in type_fields:
        if hasattr(p, field) and getattr(p, field) is not None:
            info[field] = dep_class(getattr(p, field), info['deps'])
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


def dep_class(cls, deplist):
    qn = qualifed_classname(cls)
    if not qn.startswith('client.'):
        deplist.append(qn)
    return qn


def svc_qual_classname(cls):
    qn = qualifed_classname(cls)
    if qn == 'None':
        return qn
    if qn.startswith('client.'):
        return qn
    return 'client_.type.%s' % qn


def qualifed_classname(cls):
    if cls is None:
        return 'None'
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
    main(sys.argv[1])


# PROBLEMS
# circular dependencies
# AnyType does dynamic type lookup using client.wsdl

