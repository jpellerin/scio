import scio.client as sc
import helpers

class WrappedMethodCall(sc.MethodCall):
    def format_request(self, *arg, **kw):
        foo = kw.pop('foo', None)
        request = super(WrappedMethodCall, self).format_request(*arg, **kw)
        request.foo = foo
        return request


class WrappingServiceContainer(sc.ServiceContainer):
    method_class = WrappedMethodCall



class FooingClient(sc.Client):
    def __init__(self, wsdl_fp, transport=None, service_class=None,
                 type_class=None, **kw):
        if service_class is None:
            service_class = WrappingServiceContainer
        super(FooingClient, self).__init__(wsdl_fp, transport=transport,
                                           service_class=service_class,
                                           type_class=type_class)

    def send(self, method, request):
        assert request.foo, "request.foo was not set"


def test_calls_get_foo():
    c = FooingClient(helpers.support('lyrics.wsdl'))
    c.service.getArtist('U2', foo='electric!')

        
