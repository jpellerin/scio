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

# TODO
# - schema types can extend enums. How the heck can that work?

# FIXME namespace handling is just horrible throughout.
# - namespace/nsmap can attach to attribute descriptor
#   might be cleaner to do this everywhere rather than
#   class sometimes, other times not

from decimal import Decimal
import itertools
from lxml import etree
from urllib2 import urlopen, Request, HTTPError
from threading import RLock
from datetime import date, datetime, time
from dateutil.parser import parse as parse_date
import logging


log = logging.getLogger(__name__)

# soap contstants
NS_SOAP_ENV = "http://schemas.xmlsoap.org/soap/envelope/"
NS_SOAP_ENC = "http://schemas.xmlsoap.org/soap/encoding/"
NS_SOAP = 'http://schemas.xmlsoap.org/wsdl/soap/'
NS_SOAP12 = 'http://schemas.xmlsoap.org/wsdl/soap12/'
NS_XSI = "http://www.w3.org/2001/XMLSchema-instance"
NS_XSD = "http://www.w3.org/2001/XMLSchema"
NS_WSDL = 'http://schemas.xmlsoap.org/wsdl/'
SOAP_BODY = '{%s}Body' % NS_SOAP_ENV
SOAP_FAULT = '{%s}Fault' % NS_SOAP_ENV
SOAP_HEADER = '{%s}Header' % NS_SOAP_ENV

SOAPNS = {
    'soap-env': NS_SOAP_ENV,
    'soap-enc': NS_SOAP_ENC,
    'soap': NS_SOAP,
    'soap12': NS_SOAP12,
    'wsdl': NS_WSDL,
    'xsi': NS_XSI,
    'xsd': NS_XSD }

# singleton used by AttributeDescriptor
notset = object()

#
# SOAP client class and helpers
#
class Client(object):
    """
    WSDL client container class.

    Given an open wsdl file-like object, instantiating a Client builds
    SOAP types and service calls using a Factory, and provides access
    to them via the instance's ``type`` and ``service`` attributes.

    :param wsdl_fp: A file-like object containing the wsdl to use to
                    construct the client types and methods.
    :param transport: The transport mechanism for communicating with
                      target services. Default: :func:`urlopen`.
    :param service_class: A class that will contain services. An
                          instance of this class will be available as
                          client.service.
    :param type_class: A class that will contain types. An instance of
                       this class will be available as client.type.
    :param reduce_callback: REQUIRED TO SUPPORT PICKLING! If you want to
                            be able to pickle and unpickle scio types,
                            you must supply a function that can, given
                            a class name, return a bare instance of the
                            type. This function *must* be defined at the
                            top level of a module and must be marked as
                            __safe_for_unpickle__. The reduce callback must
                            have a signature compatible with the typical
                            definition::

                              def reviver(classname, proto=object, args=()):
                                  return proto.__new__(getattr(
                                      some_client.type, classname), *args)

                            The ``proto`` parameter will only be used for
                            a number of basic types, including int
                            and arrays (list).
    """
    def __init__(self, wsdl_fp, transport=None,
                 service_class=None, type_class=None,
                 reduce_callback=None):
        self.wsdl = Factory(wsdl_fp)
        if transport is None:
            transport = urlopen
        if service_class is None:
            service_class = ServiceContainer
        if type_class is None:
            type_class = TypeContainer
        self.transport = transport
        self.service = service_class(self)
        self.type = type_class(self)
        self.reduce_callback = reduce_callback
        self.wsdl.build(self)

    def envelope(self, request):
        """
        Given an InputMessage, wrap in in a SOAP envelope and produce
        an Element.
        """
        env = etree.Element('{%s}Envelope' % SOAPNS['soap-env'], nsmap=SOAPNS)
        if request.headers:
            header = etree.SubElement(
                env, '{%s}Header' % SOAPNS['soap-env'], nsmap=SOAPNS)
            for element in request.headerxml():
                if element is not None:
                    header.append(element)
        body = etree.SubElement(
            env, '{%s}Body' % SOAPNS['soap-env'], nsmap=SOAPNS)
        for element in request.toxml():
            if element is not None:
                body.append(element)
        return env

    def send(self, method, request):
        """
        Send the SOAP request for the given method. Don't call this directly
        (use the methods attached to a client's `service` attribute instead),
        but do override it in a subclass to mock a service or change how
        a request is sent.
        """
        response = self.transport(request).read()
        return self.handle_response(method, response)

    def handle_response(self, method, response):
        """
        Handle a seemingly successful response.
        """
        log.debug('Response xml: %s', response)
        body, header = self.parse_response(method, response)
        return method.output(body, header)

    def parse_response(self, method, response):
        """
        Parse the response xml and return the soap body and header.
        """
        parsed = etree.fromstring(response)
        body = parsed.find(SOAP_BODY)
        if body is None:
            raise NotSOAP("No SOAP body found in response", response)
        self.raise_if_fault(method, body)
        body = body[0] # hacky? get the first real element
        header = parsed.find(SOAP_HEADER)
        return body, header

    def handle_error(self, method, err):
        """
        Handle an exception raised by a method call that may be a
        SOAP Fault.
        """
        try:
            response = err.fp.read()
        except AttributeError:
            response = None
        if response:
            try:
                parsed = etree.fromstring(response)
                body = parsed.find(SOAP_BODY)
                self.raise_if_fault(method, body)
            except SyntaxError:
                pass
        raise err # FIXME loses traceback

    def raise_if_fault(self, method, body):
        """
        Raise a SOAP Fault if one is found in the response body.
        """
        if body is None:
            return
        fault = body.find(SOAP_FAULT)
        if fault is not None:
            code = fault.find('faultcode')
            if code is not None:
                code = code.text
            string = fault.find('faultstring')
            if string is not None:
                string = string.text
            detail = fault.find('detail')
            if detail is not None:
                if detail.text:
                    detail = detail.text
                else:
                    detail = etree.tostring(detail)
            raise Fault(method.location, method.name, code, string, detail)

    @property
    def _resolver(self):
        return self

    def _find(self, type_):
        return self.wsdl.resolve(type_, allow_ref=False)


class Fault(Exception):
    """
    SOAP Fault exception. The method that raised the fault, the faultcode,
    and faultstring are available as attributes of the exception.
    """
    def __init__(self, method_location, method_name, faultcode, faultstring, detail):
        self.method_location = method_location
        self.method_name = method_name
        self.faultcode = faultcode
        self.faultstring = faultstring
        self.detail = detail
        # for < 2.5 compatibility, can't call super()
        Exception.__init__(
            self, method_location, method_name, faultcode, faultstring, detail)

    def __str__(self):
        return "SOAP Fault %s:%s <%s> %s%s" % (
            self.method_location, self.method_name, self.faultcode,
            self.faultstring, self.detail and ": %s" % self.detail or '')

    def __unicode__(self):
        return unicode(str(self))


class NotSOAP(ValueError):
    """
    Exception thrown when a response is received that does not
    contain SOAP xml. The full response is available as the
    response attribute of the exception.
    """
    def __init__(self, msg, response, *arg, **kw):
        self.msg = msg
        self.response = response
        Exception.__init__(self, msg, *arg, **kw)

    def __str__(self):
        return "%s:\n%s" % (self.msg, self.response)


class TypeContainer(object):
    """
    Bucket that holds types defined in WSDL. Attached to client as `type`
    attribute.
    """
    def __init__(self, client):
        self._client = client


class MethodCall(object):
    """
    Pseudo-closure for a single SOAP method call.
    """
    def __init__(self, client, method):
        self.client = client
        self.method = method

    def __call__(self, *arg, **kw):
        request = self.format_request(*arg, **kw)
        try:
            response = self.send_request(request)
            log.debug("Response: %s", response)
            return response
        except HTTPError, e:
            if e.code in (202, 204):
                return self.client.handle_response(self.method, None)
            else:
                return self.client.handle_error(self.method, e)

    def format_request(self, *arg, **kw):
        request = self.client.envelope(self.method.input(*arg, **kw))
        req_xml = etree.tostring(request)
        log.debug("Request: %s", req_xml)
        return Request(self.method.location, req_xml, self.headers())

    def send_request(self, request):
        return self.client.send(self.method, request)

    def headers(self):
        return {'Content-Type': 'text/xml',
                'SOAPAction': self.method.action}


class Method(object):
    """
    Definition of a single SOAP method, including the location, action, name
    and input and output classes.

    TODO: add a useful repr
    """
    def __init__(self, location, name, action, input, output):
        self.location = location
        self.name = name
        self.action = action
        self.input = input
        self.output = output


class ServiceContainer(object):
    """
    Bucket that holds service methods. Attached to client as `service`
    attribute.
    """
    method_class = MethodCall
    def __init__(self, client):
        self._methods = []
        self._client = client

    def __setattr__(self, attr, val):
        if attr.startswith('_'):
            self.__dict__[attr] = val
        else:
            meth = self.method_class(self._client, val)
            self._methods.append(meth)
            self.__dict__[attr] = meth

#
# Pickling support
#
class Pickleable(object):
    _client = None

    def __reduce__(self):
        try:
            base = self._base_type()
        except AttributeError:
            base = None
        try:
            args = self.__getnewargs__()
        except AttributeError:
            args = ()
        if self._client and self._client.reduce_callback:
            return (self._client.reduce_callback,
                    (self.__class__.__name__, base, args),
                    self.__getstate__())
        return object.__reduce__(self)

    def __getstate__(self):
        d = self.__dict__.copy()
        if hasattr(self, '__slots__'):
            d.update(dict((k, getattr(self, k)) for k in self.__slots__))
        if '_client' in d:
            del d['_client']
        return d

    def __setstate__(self, dct):
        if hasattr(self, '__slots__'):
            for k in self.__slots__:
                setattr(self, k, dct.pop(k))
        self.__dict__.update(dct)

#
# Types, elements and accessors
#
class Element(object):
    """
    Base class for xml elements and attributes
    """
    _tag = None
    _schema = None
    _namespace = None
    _typemap = {} # intentional
    _position = 0

    @classmethod
    def fromxml(cls, element):
        """
        Convert value from xml. Override in typed subclasses
        to do type conversion.
        """
        return element.text

    @classmethod
    def empty(cls):
        """Return an empty instance of this class."""
        return cls()

    def toxml(self, tag=None, empty=False):
        if tag is None:
            tag = self._tag
        if tag is None:
            raise ValueError("%s has no tag" % self)
        try:
            value = unicode(self)
        except TypeError:
            value = None
        if self._namespace:
            tag = '{%s}%s' % (self._namespace, tag)
        if self._schema:
            e = etree.Element(tag, nsmap=self._schema.minimal_nsmap(self._namespace))
        else:
            e = etree.Element(tag)
        if value is not None and value != u'':
            e.text = value
        return e


class SimpleTypeMeta(type):
    """
    Metaclass that registers each simple type in the Element typemap.
    """
    def __init__(cls, name, bases, dct):
        if dct.get('xsi_type', None):
            Element._typemap[dct['xsi_type'][1]] = cls
        super(SimpleTypeMeta, cls).__init__(name, bases, dct)


class SimpleType(Element):
    """
    Base class mixin for simple types. Allows simple types to be set by
    passing xml elements to their constructors.
    """
    __metaclass__ = SimpleTypeMeta
    xsi_type = None
    def __new__(cls, *arg, **kw):
        newarg, newkw = cls.adapt_args(arg, kw)
        base = cls._base_type()
        inst = base.__new__(cls, *newarg, **newkw)
        inst.__init__(*newarg, **newkw)
        return inst

    @classmethod
    def adapt_args(cls, arg, kw):
        """
        Adapt incoming arguments -- which may include xml Elements -- to
        the argument list expected by the native class of this type.
        """
        newarg = []
        for a in arg:
            if isinstance(a, etree._Element):
                val = cls.fromxml(a)
                if val is not None:
                    newarg.append(val)
            else:
                newarg.append(a)
        return newarg, kw

    @classmethod
    def empty(cls):
        # unset simple types are None, to distinguish from
        # eg those set to empty string or 0
        """Return an empty instance of this class. Empty SimpleTypes are
        always None."""
        return None

    @classmethod
    def _base_type(cls):
        # FIXME this is pretty hacky
        for t in cls.__mro__[1:]:
            # generated client code compiled into an anonymous
            # namespace will have its classes in __builtin__
            if (t.__module__ not in (cls.__module__, 'scio.client') or
                t.__module__ == '__builtin__'):
                return t

class IntType(SimpleType, int):
    xsi_type = (NS_XSD, 'int')


class LongType(SimpleType, long):
    xsi_type = (NS_XSD, 'long')


class StringType(SimpleType, unicode):
    xsi_type = (NS_XSD, 'string')


class DecimalType(SimpleType, Decimal):
    xsi_type = (NS_XSD, 'decimal')


class FloatType(SimpleType, float):
    xsi_type = (NS_XSD, 'float')


class DateTimeType(SimpleType, datetime):
    xsi_type = (NS_XSD, 'dateTime')

    @classmethod
    def adapt_args(cls, arg, kw):
        newarg, newkw = SimpleType.adapt_args(arg, kw)
        if len(newarg) == 1:
            try:
                dt = parse_date(newarg[0])
                newarg = (dt.year, dt.month, dt.day,
                          # microsecond always 0
                          dt.hour, dt.minute, dt.second, 0,
                          dt.tzinfo)
            except ValueError:
                # may be binary date 'string' from a pickle, let it through
                pass
        return newarg, newkw

    def __str__(self):
        return str(unicode(self))

    def __unicode__(self):
        return unicode(self.isoformat('T'))


class DateType(SimpleType, date):
    xsi_type = (NS_XSD, 'date')

    @classmethod
    def adapt_args(cls, arg, kw):
        newarg, newkw = SimpleType.adapt_args(arg, kw)
        if len(newarg) == 1:
            try:
                dt = parse_date(newarg[0])
                newarg = (dt.year, dt.month, dt.day)
            except ValueError:
                # may be binary date 'string' from a pickle, let it through
                pass
        return newarg, newkw

    def __str__(self):
        return str(unicode(self))

    def __unicode__(self):
        return unicode(self.isoformat())


class TimeType(SimpleType, time):
    xsi_type = (NS_XSD, 'time')

    @classmethod
    def adapt_args(cls, arg, kw):
        newarg, newkw = SimpleType.adapt_args(arg, kw)
        if len(newarg) == 1:
            dt = parse_date(newarg[0])
            # microsecond always 0
            newarg = (dt.hour, dt.minute, dt.second, 0, dt.tzinfo)
        return newarg, newkw

    def __str__(self):
        return str(unicode(self))

    def __unicode__(self):
        return unicode(self.isoformat())


# bool is notsubclassable, so this type just normalizes to the
# string values 'true' or 'false'
class BooleanType(SimpleType, unicode):
    xsi_type = (NS_XSD, 'boolean')
    true_vals = ('true', '1', 1)

    @classmethod
    def adapt_args(cls, arg, kw):
        newarg, newkw = SimpleType.adapt_args(arg, kw)
        if len(newarg) == 1:
            if str(newarg[0]).lower() in cls.true_vals:
                newarg = ('true',)
            else:
                newarg = ('false',)
        return newarg, newkw

    def __nonzero__(self):
        return self == u'true'


class EnumType(Element, Pickleable):
    """
    Element representing a SOAP Enum. Subclasses have a defined set
    of allowed values.
    """
    _values = ()
    _attributes = ()
    _children = ()
    _content_type = None # FIXME this should be setable

    def __init__(self, val=None, **kw):
        err = False
        self.value = None
        if val is not None:
            try:
                val = val.text
            except AttributeError:
                pass
            if val in self._values:
                self.value = val
            elif ' ' in val:
                # enums may be a space-separated list of flags
                # still only one real value though -- not a true
                # list. So we just check to make sure all values
                # are legal, but store the original space-separated
                # string
                parts = val.split(' ')
                for part in parts:
                     if not part.strip() in self._values:
                         err = True
                         break
                self.value = val
            else:
                err = True
            if err:
                raise ValueError("Illegal enum value %s for %s (allowed: %s)" %
                                 (val, self.__class__.__name__, self._values))
        super(EnumType, self).__init__(**kw)

    def __unicode__(self):
        return self.value
    __str__ = __unicode__

    def __repr__(self):
        return "%s.%s" % (self.__class__.__name__, self.value)

    @classmethod
    def empty(cls):
        # Like simple types, an empty enum is just None, to avoid collisions
        # with any blank-looking enum values
        return None


class UnionType(Element, Pickleable):
    _values = ()
    _attributes = ()
    _children = ()
    _content_type = None # FIXME this should be setable

    def __init__(self, val=None, **kw):
        self.value = None
        if val is not None:
            try:
                self.value = val.text
            except AttributeError:
                self.value = val
        super(UnionType, self).__init__(**kw)

    def __unicode__(self):
        if self.value is None:
            return u''
        return unicode(self.value)
    __str__ = __unicode__

    def __repr__(self):
        return "%s.%s" % (self.__class__.__name__, self.value)

    @classmethod
    def empty(cls):
        return None


class AnyType(object):
    """
    Factory for runtime type lookups. When given an 'anyType' element, the
    client must look up the type to deserialize to from the type given
    by the element, in some attribute with a local name of 'type'.
    """
    client = None
    # needed because I get used as an Element, though I'm not really one
    _tag = _namespace = _nsmap = _prefix = None

    def __init__(self, client):
        self.client = client
        self.__name__ = '<AnyType>'

    def __call__(self, value=None, **kw):
        if value is None:
            return
        valtype = xsi_type(value)
        if not valtype:
            return
        # Can't create types at runtime, only find them
        valcls = self.client.wsdl.resolve(valtype, allow_ref=False)
        return valcls(value, **kw)

    @classmethod
    def empty(cls):
        """Return an empty instance. Like simple types, an empty anyType
        is just None."""
        return None


class AnyAttribute(object):
    """Minimal wrapper for untyped extra attributes.
    """
    def __init__(self, name):
        self.name = name


class ArrayType(list, Pickleable):
    _arrayType = None
    _client = None
    _tag = _namespace = _nsmap = _prefix = None

    def __init__(self, iterable=()):
        for item in iterable:
            self.append(self._arrayType(item))

    def __reduce__(self):
        if self._client and self._client.reduce_callback:
            return (self._client.reduce_callback,
                    (self.__class__.__name__, list),
                    self.__getstate__(),
                    iter(i for i in self))
        return object.__reduce__(self)


class ComplexType(Element, Pickleable):
    """
    Base class for SOAP complexTypes, at least the ones that look like
    classes. For each complexType in a WSDL document, the Factory creates
    a ComplexType subclass with the appropriate children and attributes.
    """
    _content = None
    _content_type = None
    _attributes = ()
    _children = ()
    _substitutions = None
    _arg = () # TODO
    _abstract = False
    _client = None
    _type_attr = None
    _type_value = None
    _child_count = 0
    any_attribute = False
    xsi_type = None

    def __new__(cls, element=None, **kw):
        # Similar to AnyType()(element), but just finds the
        # class. AnyType() calls cls(), which if done here,
        # results in obj.__init__() getting called twice.
        if cls._abstract and cls._resolver and element is not None:
            valtype = xsi_type(element)
            if valtype:
                cls = cls._resolver._find(valtype)
        return object.__new__(cls)

    def __init__(self, element=None, **kw):
        self.qns = '{%s}' % self._namespace
        # FIXME support positional args, including assignment
        # of scio classes to children via positional args
        if element is not None:
            content = None
            if isinstance(element, etree._Element):
                element = self._resolve_multiref(element)
                attrs = set(attr.name for attr in self._attributes)
                kids = set(child.name for child in self._children)
                kids_subs = self._child_substitutions()
                content = element.text
                for attr, aval in element.attrib.items():
                    if attr != local(attr):
                        continue
                    if self.any_attribute and attr not in attrs:
                        self._attributes.append(AnyAttribute(attr))
                    setattr(self, attr, aval)
                for el in element:
                    if el.text is not None or el.attrib or len(el):
                        name = local(el.tag)
                        if name in kids:
                            setattr(self, name, el)
                        else:
                            # substitutionGroups
                            real_cls, real_name = kids_subs.get(name, (None,None))
                            if real_cls:
                                setattr(self, real_name, real_cls(el))
                                # FIXME Or for unnamed subelements:
                                # setattr(self, name, real_cls(el))
                        # TODO handle any tag, ref any_attribute above
            elif isinstance(element, dict):
                for k, v in element.items():
                    setattr(self, k, v)
            else:
                content = element
            if content is not None:
                # support type conversion
                if self._content_type:
                    self._content = self._content_type(content)
                else:
                    self._content = element.text
        for k, v in kw.items():
            # This assures that subelements have correct element name
            # when they are passed in as ComplexType() instances
            if not getattr(v, '_tag', None):
                try:
                    v._name = k
                except AttributeError:
                    # builtins and such
                    pass
            setattr(self, k, v)

    def _resolve_multiref(self, element):
        href = element.get('href', None)
        if href is None:
            return element
        return self._find_multiref(element, href)

    def _find_multiref(self, element, href):
        if href.startswith('#'):
            href = href[1:]
        else:
            raise ValueError("Only id-based multirefs supported")
        root = element.getparent()
        while root is not None:
            for mr in root.findall('multiRef'):
                if mr.get('id') == href:
                    return mr
            root = root.getparent()
        raise ValueError("No multiRef found for %s (%s)" % (element, href))

    def _child_substitutions(self):
        # FIXME this is a hack, feels like I'm poking through
        # things I shouldn't be from here.
        key = '_child_substitutions_'
        if not hasattr(self.__class__, key):
            subs = {}
            for child in self._children:
                if not hasattr(child.type, '_substitutions'):
                    continue
                if not child.type._substitutions:
                    continue
                for sub_name, sub in child.type._substitutions.items():
                    subs[sub_name] = (sub, child.name)
            setattr(self.__class__, key, subs)
        return getattr(self, key)

    def _findall(self, element, child):
        # Sometimes you need to be qualified, sometimes not
        check_unqual = True
        for n in element.findall('./%s%s' % (self.qns, child.name)):
            check_unqual = False
            yield n
        if check_unqual:
            for n in element.findall("./%s" % child.name):
                yield n

    def _items(self):
        items = []
        for a in itertools.chain(self._attributes, self._children):
            # access the internal key not the real attribute to
            # avoid autovivification
            val = getattr(self, "_%s_" % a.name, None)
            if val is not None:
                items.append((a.name, val))
        return items

    def __repr__(self):
        props = []
        if self._content is not None:
            props.append('_content=%r' % self._content)
        for name, val in self._items():
            props.append('%s=%r' % (name, val))
        return '%s(%s)' % (self.__class__.__name__,
                           ', '.join(props))

    def __unicode__(self):
        if self._content is not None:
            return unicode(self._content)
        return u''

    __str__ = __unicode__

    def __nonzero__(self):
        return bool(self._content or self._items())

    def __iter__(self):
        if self:
            return iter([self])
        return iter([])

    def toxml(self, tag=None, empty=False):
        if tag is None:
            tag = self._tag
        if tag is None:
            raise ValueError("%s has no tag" % self)
        if self._content is not None:
            value = unicode(self._content)
        else:
            value = None
        if self._namespace:
            tag = '{%s}%s' % (self._namespace, tag)
        if self._schema:
            e = etree.Element(
                tag, nsmap=self._schema.minimal_nsmap(self._namespace))
        else:
            e = etree.Element(tag)
        if self._type_attr and self._type_value:
            e.attrib[self._type_attr] = self._type_value
        if isinstance(value, basestring):
            e.text = value
        elif isinstance(value, etree._Element):
            e.append(value)
        for attr in self._attributes:
            at_val = getattr(self, attr.name, None)
            if at_val is not None:
                e.attrib[attr.name] = unicode(at_val)
        for child in self._children:
            # use private accessors to avoid autovivification
            # since we're potentially passing empty=True to children
            # and we don't want to render all possible children, only
            # those with actual values.
            key = "_%s_" % child.name
            ch_val = getattr(self, key, None)
            if ch_val is not None:
                if isinstance(ch_val, list):
                    for ch in ch_val:
                        ch_el = ch.toxml(child.name, empty=empty)
                        if ch_el is not None:
                            e.append(ch_el)
                else:
                    ch_el = ch_val.toxml(child.name, empty=empty)
                    if ch_el is not None:
                        e.append(ch_el)
        if not empty and e.text is None and not e.attrib and not len(e):
            return None
        return e


class AttributeDescriptor(object):
    """
    AttributeDescriptors are used as properties of complex types each one models
    an attribute or element that is part of the complex type. The descriptor
    mediates access to the type instance, which holds the value.
    """
    required = False
    name = None
    min = max = None

    def __init__(self, name, type_=None, required=False, min=None, max=None,
                 doc=None, namespace=None, **kw):
        self.name = name
        if type_ is None:
            type_ = StringType
        self.type = type_
        self.required = required
        self.min = min
        self.max = max
        self.namespace = namespace
        if doc is not None:
            self.__doc__ = doc

    def __str__(self):
        return "%s(%s:%s)" % (
            self.__class__.__name__, self.name, self.type.__class__.__name__)

    def __get__(self, obj, cls):
        if obj is None:
            return self
        key = '_%s_' % self.name
        val = getattr(obj, key, notset)
        if val is notset:
            # ComplexTypes should not return None, but fresh
            # empty versions of themselves if not set -- of course
            # for this to work they have to *become set* when
            # accessed for the first time. This enables you to say:
            # Foo.Bar.Baz = 1 even if Foo.Bar has not yet been set.
            val = self.type.empty()
            self._set_xml_context(val)
            setattr(obj, key, val)
        return val

    def __set__(self, obj, value):
        # convert from node or other xml value into simple value
        key = '_%s_' % self.name

        if isinstance(value, (list, tuple)):
            new = []
            for item in value:
                if not isinstance(item, self.type):
                    item = self._new(item)
                item._position = obj._child_count
                obj._child_count += 1
                new.append(item)
            setattr(obj, key, new)
            return

        if isinstance(self.type, AnyType) or not isinstance(value, self.type):
            value = self._new(value)
        else:
            # a type may not share the same namespace as its container
            # so if we were given a full type, ensure it is set up
            # with the proper tag and namespace for this context
            self._set_xml_context(value)

        # remember the order in which we saw assignments
        value._position = obj._child_count
        obj._child_count += 1

        # sort of hacky set/append combo
        # this is needed to handle parsing multiple values out of xml
        curval = getattr(obj, key, None)
        if curval is not None and (self.max == 'unbounded' or self.max > 1):
            if not isinstance(curval, list):
                curval = [curval]
            curval.append(value)
            value = curval
        setattr(obj, key, value)

    def __delete__(self, obj):
        delattr(obj, '_%s_' % self.name)

    def _new(self, value):
        val = self.type(value)
        self._set_xml_context(val)
        return val

    def _set_xml_context(self, value):
        try:
            value._tag = self.name
            value._namespace = self.namespace
        except AttributeError:
            # value was None or another unalterable builtin
            pass

    def isanytype(self):
        return (isinstance(self.type, AnyType)
                or getattr(self.type, '_abstract', False))


class InputMessage(object):
    """
    Base of the marshalling chain for input messages. Call this with
    positional or keyword arguments appropriate to the message, and
    get back a formatter whose toxml() method will yield xml Elements
    for inclusion in a SOAP message.
    """
    def __init__(self, tag, namespace, parts, style, literal, headers):
        self.tag = tag
        self.namespace = namespace
        self.parts = parts
        self.style = style
        self.literal = literal
        self.headers = headers
        self.formatter = self._pick_formatter()

    def __call__(self, *arg, **kw):
        tag = self.tag
        namespace = self.namespace
        header_fmt = []
        for name, cls in self.headers:
            # simple headers
            val = kw.pop(name, None)
            if val is not None:
                header_fmt.append((name, cls(val)))
            # complex headers
            hkids = getattr(cls, '_children', ())
            hkids = itertools.chain(hkids, getattr(cls, '_attributes', ()))
            hkw = {}
            for kcls in hkids:
                val = kw.pop(kcls.name, None)
                if val is not None:
                    hkw[kcls.name] = kcls._new(val)
            if hkw:
                header_fmt.append((name, cls(**hkw)))

        if len(self.parts) == 1:
            return self.formatter(
                tag, namespace, [
                    (part_tag, cls(*arg, **kw))
                    for part_tag, cls in self.parts],
                header_fmt
                )
        else:
            # map each arg in args to one part
            parts_fmt = []
            alist = list(arg)
            for part_tag, cls in self.parts:
                fmt = cls(alist.pop(0), **kw)
                parts_fmt.append((part_tag, fmt))
            return self.formatter(tag, namespace, parts_fmt, header_fmt)

    def _pick_formatter(self):
        if self.style == 'document':
            # decide whether wrapped or not
            wrapper = self._is_wrapper()
            if self.literal:
                if wrapper:
                    return DocumentLiteralWrapperInputFormatter
                else:
                    return DocumentLiteralInputFormatter
            elif wrapper:
                return DocumentEncodedWrapperInputFormatter # FIXME
            else:
                return DocumentEncodedInputFormatter # FIXME
        elif self.style == 'rpc':
            if self.literal:
                return RpcLiteralInputFormatter
            else:
                return RpcEncodedInputFormatter

    def _is_wrapper(self):
        if len(self.parts) != 1:
            return False
        part = self.parts[0][1]
        if part._tag != self.tag:
            return False
        return True


class InputFormatter(object):
    """
    Base class for input message formatters
    """
    def __init__(self, tag, namespace, parts, headers):
        self.tag = tag
        self.namespace = namespace
        self.parts = parts
        self.headers = headers

    def toxml(self):
        raise NotImplemented

    def headerxml(self):
        for name, hdr in self.headers:
            yield hdr.toxml(name)


class DocumentLiteralWrapperInputFormatter(InputFormatter):
    """
    Input message formatter that formats a document literal message
    with wrapper. This means that the body of the message is simply
    the serialized xml of the single message part, which must be
    a complexType element with the same name as the operation.
    """
    def toxml(self):
        _, part = self.parts[0]
        yield part.toxml(empty=True)


class DocumentLiteralInputFormatter(InputFormatter):
    """
    Input message formatter for non-wrapped document literal messages.
    The main difference between this type of message and wrapped types
    is that there may be > 1 input part, and they are not all necessarily
    contained in an element with the same name as the operation.
    """
    def toxml(self):
        for part_tag, part in self.parts:
            yield part.toxml(empty=True)


class RpcLiteralInputFormatter(InputFormatter):
    """
    Input message formatting in the RPC literal style. A top-level element
    named after the operation wraps each input part, which may be a
    complexType or simple type.
    """
    def toxml(self):
        tag = '{%s}%s' % (self.namespace, self.tag)
        e = etree.Element(tag)
        for part_tag, type_ in self.parts:
            if part_tag:
                # print "appending", part_tag, type_
                part_xml = type_.toxml(part_tag)
                if part_xml is not None:
                    e.append(part_xml)
        yield e


class RpcEncodedInputFormatter(InputFormatter):
    """
    Input message formatter for rpc/enc style. A top-level element
    named after the operation wraps each input part, which may be a complex
    or simple type. Each part's xml includes an xsi:type attribute with
    the value being the namespaced type of the element.
    """
    def toxml(self):
        tag = '{%s}%s' % (self.namespace, self.tag)
        e = etree.Element(tag)
        for part_tag, type_ in self.parts:
            if part_tag:
                part_xml = type_.toxml(part_tag, self.namespace)
                nsmap = SOAPNS.copy()
                if type_._schema:
                    nsmap.update(type_._schema.short_nsmap)
                backmap = dict(zip(nsmap.values(), nsmap.keys()))
                if part_xml is not None:
                    if type_.xsi_type:
                        ns, local = type_.xsi_type
                        prefix = backmap[ns]
                        part_xml.attrib['{%s}type' % NS_XSI] = (
                            '%s:%s' % (prefix, local))
                    e.append(part_xml)
        yield e


class OutputMessage(object):
    """
    Unmarshaller for SOAP responses. This class probably needs subclasses
    for all of the different binding styles.
    """
    def __init__(self, tag, namespace, parts, headers):
        self.tag = tag
        self.namespace = namespace
        self.parts = parts
        self.headers = headers

    def __call__(self, body, header=None):
        result = []
        local_tag = local(body.tag)
        for part_tag, part in self.parts:
            if part_tag is None:
                part_tag = part._tag
            if part_tag is None:
                raise ValueError("No part tag for part %s" % part)
            if local_tag in (part_tag, part._tag):
                result.append(part(body))
            else:
                part_el = None
                if part._tag:
                    part_el = body.find(part._tag)
                if part_el is None:
                    part_el = body.find(part_tag)
                if part_el is not None:
                    result.append(part(part_el))
                else:
                    log.debug(
                        "No element found in %s  for part %s/%s",
                        body, part_tag, part._tag)
        if header is not None:
            headers = {}
            for header_tag, part in self.headers:
                header_el = header.find('{%s}%s' % (self.namespace, header_tag))
                if header_el is not None:
                    headers[header_tag] = part(header_el)
            if headers:
                result.append(headers)
        if len(result) == 1:
            return result[0]
        return tuple(result)


#
# The wsdl type factory.
#
class Factory(object):
    """
    WSDL type factory.
    """
    _typemap = Element._typemap.copy()
    _typemap.update({
        'integer': IntType,
        'positiveInteger': IntType,
        'short': IntType,
        'unsignedInt': IntType,
        'unsignedByte': IntType,
        'unsignedLong': LongType,
        'unsignedShort': IntType,
        'char': StringType,
        'long': LongType,
        'byte': StringType,
        'double': FloatType,
        'base64Binary': StringType,
        'anyURI': StringType,
        'language': StringType,
        'token': StringType,
        'hexBinary': StringType,
        # FIXME: probably timedelta, but needs parsing.
        # It looks like P29DT23H54M58S
        'duration': StringType,
        'QName': StringType,
        'ID': StringType,
        'IDREF': StringType,
        })

    _simple_tag = '{%s}simpleType' % NS_XSD
    _enum_tag =  '{%s}enumeration' % NS_XSD
    _attr_tag = '{%s}attribute' % NS_XSD
    _seq_tag = '{%s}sequence' % NS_XSD
    _all_tag = '{%s}all' % NS_XSD
    _cplx_tag = '{%s}complexContent' % NS_XSD
    _ext_tag = '{%s}extension' % NS_XSD
    _spl_tag = '{%s}simpleContent' % NS_XSD
    _element_tag = '{%s}element' % NS_XSD
    _choice_tag = '{%s}choice' % NS_XSD
    _restr_tag = '{%s}restriction' % NS_XSD
    _any_attr_tag = '{%s}anyAttribute' % NS_XSD
    _list_tag = '{%s}list' % NS_XSD
    _types_tag = '{%s}types' % NS_WSDL
    _schema_tag = '{%s}schema' % NS_XSD
    _import_tag = '{%s}import' % NS_XSD
    _cplx_type_tag = '{%s}complexType' % NS_XSD

    def __init__(self, wsdl_file):
        self.wsdl = etree.parse(wsdl_file).getroot()
        self.nsmap = NSStack(self.wsdl)
        self._imports = {}
        self._lock = RLock()
        self._lock.acquire()
        try:
            self._typemap = self._typemap.copy()
        finally:
            self._lock.release()

    def build(self, client):
        """
        Generate classes and methods for types and bindings defined in
        the wsdl file. Classes and methods become attributes of the type
        and service containers of the given client instance, respectively.
        """
        self._lock.acquire()
        try:
            self._process_types(client)
            self._process_methods(client)
            return client
        finally:
            self._lock.release()

    def resolve(self, name, allow_ref=True):
        """
        Resolve a class name to a class.
        """
        try:
            return self._typemap[name]
        except KeyError:
            if allow_ref:
                return TypeRef(name, self)
            raise

    def _process_types(self, client):
        self._refs = []
        types = self.wsdl.find(self._types_tag)
        if types is None:
            return
        for child in types.getchildren():
            if self._is_schema(child):
                self._process_schema(client, child)
            elif self._is_type(child):
                self._process_type(client, child)
            else:
                raise Exception("Unknown type tag %s" % child)
        self._resolve_refs()

    def _process_schema(self, client, schema):
        self.nsmap.push_schema(schema)
        for child in schema.getchildren():
            if self._is_type(child):
                self._process_type(client, child)
            elif self._is_import(child):
                self._process_import(client, child)
        self.nsmap.pop_schema()

    def _process_type(self, client, child):
        if self._is_element(child):
            name = child.get('name')
            typel = child.find(self._cplx_type_tag)
            if typel is None:
                typel = child.find(self._simple_tag)
            if typel is None:
                typel = child.get('type', None)
            if typel is None:
                raise ValueError("Could not find type for element %s" % child)
            self._make_class(client, typel, name=name, force_name=True,
                             name_from=child)
        else:
            name = child.get('name', None)
            if name is None:
                return
            self._make_class(client, child, name=name, force_name=False)

    def _process_import(self, client, child):
        # IMPORTS CAN BE CIRCULAR! BEWARE!
        url = child.get('schemaLocation')
        if not url:
            return
        if url in self._imports:
            log.debug("Already imported %s", url)
            return
        schema = etree.parse(urlopen(url)).getroot()
        self._imports[url] = schema
        self._process_schema(client, schema)

    def _resolve_refs(self):
        for client_type, name in self._refs:
            ref = getattr(client_type, name)
            if isinstance(ref, TypeRef):
                setattr(client_type, name, ref())
        self._refs = []

    def _process_methods(self, client):
        services = self.wsdl.findall('.//{%s}service' % NS_WSDL)
        for service in services:
            for port in service.findall('.//{%s}port' % NS_WSDL):
                if not self._is_soap_port(port):
                    continue
                self._process_port(client, port)

    def _is_soap_port(self, port):
        soap_ns = (NS_SOAP, NS_SOAP12)
        for el in port:
            if el.nsmap[el.prefix] in soap_ns:
                return True
        return False

    def _process_port(self, client, port):
        service = client.service
        location = port[0].get('location')
        binding_name = local_attr(port.get('binding'))
        binding = self.wsdl.find(".//{%s}binding[@name='%s']" %
                                  (NS_WSDL, binding_name))
        style = self._binding_style(binding)
        ptype_name = local_attr(binding.get('type'))
        ptype = self.wsdl.find(".//{%s}portType[@name='%s']" %
                                (NS_WSDL, ptype_name))
        for op in binding.findall('{%s}operation' % NS_WSDL):
            name = local_attr(op.attrib['name'])
            params = op.attrib.get('parameterOrder', '').split(' ')
            try:
                (action, op_style, literal,
                 in_headers, out_headers) = self._op_info(op)
            except SyntaxError:
                # FIXME not a soap op after all??
                continue
            if not op_style:
                if not style:
                    raise SyntaxError("Neither binding nor operation style found")
                op_style = style
            port_op = ptype.find("{%s}operation[@name='%s']" %
                                 (NS_WSDL, name))
            in_msg_name = local_attr(port_op.find(
                '{%s}input' % NS_WSDL).attrib['message'])
            out_msg_name = local_attr(port_op.find(
                '{%s}output' % NS_WSDL).attrib['message'])
            in_types = self.wsdl.findall(
                ".//{%s}message[@name='%s']/{%s}part" %
                (NS_WSDL, in_msg_name, NS_WSDL))
            out_types = self.wsdl.findall(
                './/{%s}message[@name="%s"]/{%s}part' %
                (NS_WSDL, out_msg_name, NS_WSDL))
            in_msg = self._make_input_msg(client, name, in_types, params,
                                          op_style, literal, in_headers)
            out_msg = self._make_output_msg(client, name, out_types,
                                            op_style, literal, out_headers)
            setattr(service, name,
                    Method(location, name, action, in_msg, out_msg))

    def _make_input_msg(self, client, name, types, params, op_style, literal,
                        headers):
        # FIXME use params! There's useful information there...
        parts = []
        header_parts = []
        namespace = self.nsmap.targetNamespace()
        # this has to be determined per-part
        # by looking at the part's schema
        for t in types:
            if not 'name' in t.attrib:
                continue
            part_name = t.attrib['name']
            if 'element' in t.attrib:
                parts.append(
                    (part_name, self._make_class(client, t.attrib['element'])))
            elif 'type' in t.attrib:
                parts.append(
                    (part_name, self._make_class(client, t.attrib['type'])))
        for h_name, h_type in headers:
            header_parts.append((h_name, self._make_class(client, h_type)))
        return InputMessage(name, namespace, parts, op_style, literal,
                            header_parts)

    def _make_output_msg(self, client, name, types, op_style, literal, headers):
        parts = []
        header_parts = []

        schema = self.nsmap.top()
        namespace = schema.targetNamespace
        for t in types:
            if not 'name' in t.attrib:
                continue
            part_name = t.attrib['name']
            if 'element' in t.attrib:
                parts.append(
                    (part_name, self._make_class(client, t.attrib['element'])))
            elif 'type' in t.attrib:
                parts.append(
                    (part_name, self._make_class(client, t.attrib['type'])))
        for h_name, h_type in headers:
            header_parts.append((h_name, self._make_class(client, h_type)))
        return OutputMessage(name, namespace, parts, header_parts)

    def _make_class(self, client, type_, name=None, force_name=False,
                    name_from=None):
        client_type = client.type
        ref = None

        if isinstance(type_, basestring):
            # catch known types
            key = local_attr(type_)
            if key in self._typemap:
                # FIXME (both branches) this fails for instances of types that
                # have their own namespaces
                if force_name and name != key:
                    # handle simple rename-only "subclasses" of existing types
                    cls = self._make_subclass(client, name, name_from,
                                              self._typemap[key])
                    self._typemap[name] = cls
                    setattr(client_type, name, cls)
                    return cls
                return self._typemap[key]
            if key == 'anyType':
                # anyType must be bound to client, since
                # it requires run-time type lookup
                return self._anyType(client)
            # ... or find the definition in wsdl
            ref, etype = None, self._find_type(type_)
            if etype is None:
                ref, etype = self._find_element_ref(type_)
            type_ = etype

        if name is None:
            name = type_.get('name')

        # can't build a class without a name
        if name is None:
            return

        # this case handles weirdness like an element with
        # one namespace having a type attrib that points
        # to an element with another namespace.
        if ref is not None:
            parent = ref.getparent()
        else:
            parent = type_.getparent()
        schema, namespace = self._find_schema(parent)

        # in cache?
        cls = self._typemap.get(name, None)
        if cls is not None:
            if isinstance(cls, TypeRef):
                self._refs.append((client_type, name))
            if not hasattr(client_type, name):
                setattr(client_type, name, cls)
            if ref is not None:
                # FIXME this is similar to _make_subclass: consolidate?
                # need to subclass, set ref's name, namespace and schema
                # because the referring element wraps the type
                rname = ref.get('name')
                cls = type(rname, (cls,), {'_tag': rname,
                                           '_namespace': namespace,
                                           '_schema': schema})
                self._typemap[rname] = cls
                setattr(client_type, rname, cls)
            return cls

        # short circuit for enums
        if self._is_enum(type_):
            cls = self._make_enum(type_, client, namespace, name)
            self._typemap[name] = cls
            setattr(client_type, name, cls)
            return cls
        # short circuit for arrays
        elif self._is_array(type_):
            cls = self._make_array(type_, client, namespace, name)
            self._typemap[name] = cls
            setattr(client_type, name, cls)
            return cls
        # short circuit for unions
        elif self._is_union(type_):
            cls = self._make_union(type_, client, namespace, name)
            self._typemap[name] = cls
            setattr(client_type, name, cls)
            return cls
        # short circuit for simpleTypes
        elif self._is_simple(type_):
            cls = self._make_simple(type_, client, namespace, name)
            self._typemap[name] = cls
            setattr(client_type, name, cls)
            return cls

        # In case a type is self-referential, we need something in
        # the typemap before we start processing children
        self._typemap[name] = TypeRef(name, self)

        # the body dict of the class
        data = {'_attributes': [],
                '_children': [],
                '_substitutions': {},
                '_namespace': namespace,
                '_schema': schema,
                '_client': client,
                '_resolver': client,
                'xsd_type': (namespace, name)}
        # this handles cases where the xml element name is always
        # forced to the name in the wsdl
        if force_name:
            data['_tag'] = name
        bases = (ComplexType,)

        if schema.qualified:
            child_namespace = namespace
        else:
            # child elements are unqualified
            child_namespace = None

        for e in type_:
            # create attribute or element for each one
            # FIXME how to handle 'any attribute' ?
            # FIXME how to handle restrictions?
            if e.tag == self._attr_tag:      # attribute
                self._add_attribute(client, data, e, child_namespace)
            elif e.tag in (self._seq_tag,
                           self._all_tag,
                           self._choice_tag): # sequence of elements
                self._add_children(client, data, e, child_namespace)
            elif e.tag == self._cplx_tag:    # subclass
                e = e[0]
                if e.tag == self._ext_tag:
                    bases = (self._make_class(client, e.attrib['base']),)
                for se in e:
                    if se.tag == self._attr_tag:
                        self._add_attribute(client, data, se, child_namespace)
                    elif se.tag in (self._seq_tag,
                                    self._all_tag,
                                    self._choice_tag):
                        self._add_children(client, data, se, child_namespace)
            elif e.tag == self._spl_tag:      # subclass of builtin
                e = e[0]
                if e.tag == self._ext_tag:
                    # type for class's _content attribute
                    # to allow it to be properly converted
                    data['_content_type'] = self.resolve(
                        local_attr(e.attrib['base']))
                for se in e:
                    if se.tag == self._attr_tag:
                        self._add_attribute(client, data, se, namespace)
                    elif se.tag in (self._seq_tag, self._all_tag):
                        self._add_children(client, data, se, namespace)
            elif e.tag == self._any_attr_tag:
                data['any_attribute'] = True
        # add attributes/children from parent classes to my lists
        for base in bases:
            data['_attributes'] = list(base._attributes) + data['_attributes']
            data['_children'] = list(base._children) + data['_children']

        # track any typerefs in attributes/children
        for attr in data['_attributes']:
            if isinstance(attr.type, TypeRef):
                self._refs.append((attr, 'type'))
        for child in data['_children']:
            if isinstance(child.type, TypeRef):
                self._refs.append((child, 'type'))

        # mark abstract classes as such
        if type_.get('abstract', None) == 'true':
            data['_abstract'] = True
        else:
            # otherwise base class's abstractness pollutes subclasses
            data['_abstract'] = False
            if self._any_abstract(bases):
                data['_type_attr'] = '{%s}type' % NS_XSI
                data['_type_value'] = name

        cls = type(name, bases, data)

        # add to substitutionGroup
        substitutionGroup = (type_.get('substitutionGroup')
                             or type_.getparent().get('substitutionGroup'))
        if substitutionGroup:
            group_cls = self._make_class(
                client,
                local_attr(substitutionGroup)
                )
            group_cls._substitutions[name] = cls

        # track typeref in _content_type
        if isinstance(cls._content_type, TypeRef):
            self._refs.append((cls, '_content_type'))
        self._typemap[name] = cls
        setattr(client_type, name, cls)
        return cls

    def _add_attribute(self, client, data, element, namespace):
        try:
            name = element.attrib['name']
        except KeyError:
            # not a true attribute -- a restriction or something
            # that we don't care about (for now)
            return
        # attribute may reference a type, or may include a complexType
        # or other type definition inline, or may be a list
        type_ref = None
        try:
            type_ref = element.attrib['type']
        except KeyError:
            restr = self._find_restriction(element[0])
            if restr is not None:
                type_ref = local_attr(restr.get('base'))

        if type_ref:
            attr = AttributeDescriptor(
                name=name,
                namespace=namespace,
                type_=self._make_class(client, type_ref),
                required=element.get('use', None) == 'required')
        elif (len(element) and
              len(element[0]) and
              element[0][0].tag == self._list_tag):
            # not really a simple type -- a list
            type_ = self._make_list(
                element[0][0], client, namespace, name)
            attr = AttributeDescriptor(
                name=name,
                namespace=namespace,
                type_=type_)
        else:
            raise NotImplemented("Unable to add attribute for %s" %
                                 etree.tostring(element))
        data[name] = attr
        data['_attributes'].append(attr)

    def _add_children(self, client, data, element, namespace):
        for se in self._children(element):
            name = se.attrib.get('name')
            # ref for substitutionGroup
            type_ = se.attrib.get('ref')
            if type_:
                if not name:
                    # FIXME: or leave as None,
                    # see ComplexType.__init__ real_cls
                    name = local_attr(type_)
                type_ = self._make_class(client, type_)
            else:
                # element may n reference a type, or may include a complexType
                # or other type definition inline
                try:
                    type_ref = se.attrib['type']
                except KeyError:
                    type_ref = se[0]
                type_ = self._make_class(client, type_ref)

            el = AttributeDescriptor(
                name=name,
                type_=type_,
                min=se.get('minOccurs'),
                max=se.get('maxOccurs'),
                namespace=namespace)
            data[name] = el
            data['_children'].append(el)

    def _is_array(self, element):
        try:
            restr = element[0][0]
            if not local(restr.tag) == 'restriction':
                return False
            prefix, kind = restr.attrib['base'].split(':')
            return kind == 'Array'
        except (IndexError, TypeError, KeyError, ValueError):
            return False

    def _is_enum(self, element):
        if not element.tag == self._simple_tag:
            return False
        # Note: find_enumerations returns a list now, but
        # in case it returns an iterator in future (as it did in past)
        # listify
        enums = list(self._find_enumerations(element))
        if not enums:
            return False
        return True

    def _is_union(self, element):
        if not element.tag == self._simple_tag:
            return False
        try:
            if local(element[0].tag) == 'union':
                return True
        except (IndexError, TypeError):
            return False

    def _is_simple(self, element):
        return element.tag == self._simple_tag

    def _is_element(self, element):
        return element.tag == self._element_tag

    def _is_schema(self, element):
        return element.tag == self._schema_tag

    def _is_import(self, element):
        return element.tag == self._import_tag

    def _is_type(self, element):
        return element.tag in (
            self._element_tag, self._cplx_type_tag, self._simple_tag)

    def _any_abstract(self, bases):
        for cls in bases:
            if getattr(cls, '_abstract', None):
                return True
            base_bases = getattr(cls, '__bases__', [])
            if base_bases and self._any_abstract(base_bases):
                return True
        return False

    def _find_schema(self, element):
        if self._is_schema(element):
            schema = Schema(element)
            namespace = schema.targetNamespace
        else:
            schema = self.nsmap.top()
            namespace = schema.targetNamespace
        return schema, namespace

    def _make_enum(self, element, client, namespace, name):
        vals = []
        data = {}
        for e in self._find_enumerations(element):
            # FIXME could be typed (int, etc)
            try:
                val = e.attrib['value']
                vals.append(val)
                data[val] = val
            except KeyError:
                pass # enumeration value without a name? we can't use it
        data['_values'] = vals
        data['_client'] = client
        data['xsd_type'] = (namespace, name)
        return type(element.attrib['name'], (EnumType,), data)

    def _make_array(self, element, client, namespace, name):
        # look for restriction on array type, that is the
        # type for each item. Make a list container
        # with the appropriate item type.
        array_spec = element[0][0][0]
        tag = local(array_spec.tag)
        if tag == 'attribute':
            array_type, junk = element[0][0][0].get(
                '{%s}arrayType' % NS_WSDL).split('[', 1)
            array_type = local_attr(array_type)
        elif tag == 'sequence':
            array_type = local_attr(array_spec[0].get('type'))
        # anyType can't be found by resolve, it's special
        # (putting anyType in the typemap results in anyType
        # objects resolving themselves to AnyType rather than
        # the correct type at runtime), so we have to special
        # case it here
        if array_type == 'anyType':
            array_type = AnyType
        else:
            array_type = self.resolve(array_type)
        bases = (ArrayType,)
        data = {'_arrayType': array_type,
                '_client': client,
                'xsd_type': (namespace, name)}
        cls = type(name, bases, data)
        if isinstance(array_type, TypeRef):
            self._refs.append((cls, '_arrayType'))
        return cls

    def _make_list(self, element, client, namespace, name):
        # implemented as ArrayType subclass since arrays and lists
        # mean the same thing on the python side
        list_type = local_attr(element.get('itemType'))
        if list_type == 'anyType':
            list_type = AnyType
        else:
            list_type = self.resolve(list_type)
        data = {'_arrayType': list_type,
                '_client': client,
                'xsd_type': (namespace, name)}
        cls = type(name, (ArrayType,), data)
        if isinstance(list_type, TypeRef):
            self._refs.append((cls, '_arrayType'))
        return cls

    def _make_union(self, element, client, namespace, name):
        # Totally fake for the moment.
        # FIXME: union the restrictions when we care about restrictions
        #base_types = element[0].attrib['memberTypes'].split(' ')
        #base_clses = [self.resolve(local_attr(base_type), allow_ref=False)
        #              for base_type in base_types]
        # Cases of union so far are int+enum, so string for now
        #base_cls = self.resolve('string', allow_ref=False)
        base_cls = UnionType
        data = {'xsd_type': (namespace, name),
                '_tag': name,
                '_client': client,
                '_namespace': namespace,
                '_nsmap': self.nsmap.top()} # FIXME prefix?
        cls = type(name, (base_cls,), data)
        return cls

    def _make_simple(self, element, client, namespace, name):
        base_type = local_attr(self._find_restriction(element).get('base'))
        base_cls = self.resolve(base_type, allow_ref=False)
        data = {'xsd_type': (namespace, name),
                '_tag': name,
                '_client': client,
                '_namespace': namespace,
                '_schema': self.nsmap.top()} # FIXME prefix?
        cls = type(name, (Pickleable, base_cls,), data)
        return cls

    def _make_subclass(self, client, name, element, base):
        schema, namespace = self._find_schema(element)
        data = {'xsd_type': (namespace, name),
                '_tag': name,
                '_client': client,
                '_namespace': namespace,
                '_schema': schema}
        if Pickleable in base.__mro__:
            bases = (base,)
        else:
            bases = (Pickleable, base)
        cls = type(name, bases, data)
        return cls

    def _children(self, element):
        # FIXME for element.tag == _all_tag,
        # force minOccurs -> 0, maxOccurs -> 1
        for e in element:
            if e.tag == self._element_tag:
                yield e
            elif e.tag == self._choice_tag:
                # items in choice inherit maxOccurs setting from choice
                # this allows multiple DataOffer children, for example
                max = e.get('maxOccurs')
                for se in e:
                    if max:
                        se.attrib['maxOccurs'] = max
                    yield se

    def _find_type(self, name):
        lname = local_attr(name)
        sources = [self.wsdl] + self._imports.values()
        for source in sources:
            type_nodes = itertools.chain(
                    source.findall(
                        ".//%s[@name='%s']" % (self._cplx_type_tag, lname)),
                    source.findall(
                        ".//%s[@name='%s']" % (self._simple_tag, lname)))
            for node in type_nodes:
                return node # return first node found, if any

    def _find_element_ref(self, name):
        sources = [self.wsdl] + self._imports.values()
        for source in sources:
            elem_refs = source.findall(
                ".//%s[@name='%s']" % (self._element_tag, local_attr(name)))
            if elem_refs:
                # elem_refs[0] contains information about
                # the eventual wanted type -- its name and namespace
                # will actually wrap the wanted type.
                type_name = elem_refs[0].get('type')
                if type_name:
                    return elem_refs[0], self._find_type(type_name)
                else:
                    # self-contained type declaration
                    return elem_refs[0], elem_refs[0][0]
        raise UnknownType("Could not find definition of class %s" % name)

    def _find_enumerations(self, element):
        restr = self._find_restriction(element)
        if restr is None:
            return []
        return restr.findall(self._enum_tag)

    def _find_restriction(self, element):
        restr = element.find(self._restr_tag)
        if restr is not None:
            return restr
        try:
            next = element[0]
        except IndexError:
            next = None
        if next is None:
            return
        return self._find_restriction(next)

    def _anyType(self, client):
        return AnyType(client)

    def _binding_style(self, binding):
        soap_binding = binding.find('{%s}binding' % NS_SOAP)
        if soap_binding is None:
            soap_binding = binding.find('{%s}binding' % NS_SOAP12)
        if soap_binding is None:
            soap_binding = binding.find('binding')
        if soap_binding is None:
            raise SyntaxError("No SOAP binding found in %s" %
                              etree.tostring(binding))
        return soap_binding.get('style')

    def _op_info(self, op):
        soap_op = op.find('{%s}operation' % NS_SOAP)
        if soap_op is None:
            soap_op = op.find('{%s}operation' % NS_SOAP12)
        if soap_op is None:
            soap_op = op.find('operation')
        if soap_op is None:
            raise SyntaxError("No SOAP operation found in %s" %
                              etree.tostring(op))
        action = soap_op.attrib['soapAction']
        op_style = soap_op.get('style')
        # FIXME is it reasonable to assume that input and output
        # are the same? Is it ok to ignore the encoding style?
        input = op.find('{%s}input' % NS_WSDL)
        literal = input[0].get('use') == 'literal'

        # the header message points at a wsdl:message somewhere in the doc
        # the part names the part of that message that goes in the header
        # so to get the type we need to find the message and then get the
        # element or type attribute of the named part
        in_headers = [self._find_message_part(h.get('message'), h.get('part'))
                      for h in input.findall('{%s}header' % NS_SOAP)]
        output = op.find('{%s}output' % NS_WSDL)
        out_headers = [self._find_message_part(h.get('message'), h.get('part'))
                       for h in output.findall('{%s}header' % NS_SOAP)]
        return action, op_style, literal, in_headers, out_headers

    def _find_message_part(self, message, part):
        message = local_attr(message)
        part = self.wsdl.find(
            ".//{%s}message[@name='%s']/{%s}part[@name='%s']" %
            (NS_WSDL, message, NS_WSDL, part))
        return (part.get('name'), part.get('element') or part.get('type'))


class TypeRef(object):
    def __init__(self, name, factory):
        self.name = name
        self.factory = factory

    def __call__(self):
        return self.factory.resolve(self.name, allow_ref=False)


def local(tag):
    return tag[tag.find('}')+1:]


def local_attr(attr):
    if ':' in attr:
        _, attr = attr.split(':')
    return attr


def xsi_type(element):
    # Types and their values are generally namespaced, but we don't
    # want the namespaces here.
    for key, val in element.attrib.items():
        if local(key) == 'type':
            return local_attr(val)


class NSStack(object):

    def __init__(self, schema=None):
        self._stack = []
        if schema is not None:
            self.push_schema(schema)

    def targetNamespace(self):
        for schema in self._stack:
            try:
                return schema.targetNamespace
            except KeyError:
                pass

    def get(self, key, default=None):
        try:
            return self[key]
        except KeyError:
            return default

    def top(self):
        return self._stack[0]

    def push_schema(self, schema):
        self._stack.insert(0, Schema(schema))

    def pop_schema(self):
        self._stack.pop(0)


class Schema(object):
    def __init__(self, element):
        self.element = element

    @property
    def nsmap(self):
        return self.element.nsmap

    @property
    def targetNamespace(self):
        return self.element.attrib['targetNamespace']

    @property
    def qualified(self):
        return self.element.get('elementFormDefault', None) == 'qualified'

    @property
    def short_nsmap(self):
        nsmap = {}
        globalns = set(SOAPNS.values())
        for k, v in self.element.nsmap.items():
            if self.qualified and v == self.targetNamespace:
                nsmap[None] = v
            elif v in globalns:
                continue
            else:
                nsmap[k] = v
        return nsmap

    def minimal_nsmap(self, targetNamespace):
        if self.qualified:
            return {None: targetNamespace}
        return self.short_nsmap


def backmap(dct):
    return dict(zip(dct.values(), dct.keys()))


class UnknownType(TypeError):
    pass
