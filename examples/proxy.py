import BaseHTTPServer as http
import cgi
from threading import Thread
from traceback import format_exc
from urllib2 import HTTPError, Request, urlopen
from cPickle import dumps, loads
from urllib import urlencode
from cStringIO import StringIO
import time

REQUESTS = {}
CERT_PATH = '/etc/ssl_client'
PROXY_HOST = 'localhost'
PROXY_PORT = 7777
PROXY = 'http://%s:%s' % (PROXY_HOST, PROXY_PORT)


#
# The client side
#
class ProxyClient(scio.Client):
    """
    Subclass of scio.Client whose send method returns a ProxyPromise
    bound to the called method.
    """
    def send(self, method, request):
        req = {'url': request.get_full_url(),
               'headers': urlencode(request.headers),
               'req': request.get_data(),
               'ssl_cert': 'example'}
        return ProxyPromise(
            self, method, urlopen(PROXY, data=urlencode(req)).read())


class ProxyPromise(object):
    """
    A promise of an eventual result. Each time it is called, it contacts the
    proxy server to attempt to obtain the SOAP response. If it gets a
    response, it passes it through the client's handle_response to return
    the approprate SOAP type instance. Otherwise, it returns None.
    """
    def __init__(self, client, method, key):
        self.client = client
        self.method = method
        self.key = key
    def __call__(self):
        res = urlopen(PROXY + self.key).read()
        if res == 'waiting':
            return
        code, response = loads(res)
        if code == 200:
            return self.client.handle_response(self.method, response)
        else:
            print response
            raise HTTPError(
                self.method.location, code, 'SOAP Error', [],
                StringIO(response))

#
# The server side -- proxy daemon
#
class Handler(http.BaseHTTPRequestHandler):

    def do_GET(self):
        key = self.path[1:]
        status = REQUESTS.get(int(key), 'waiting')
        self.send_response(200, 'OK')
        self.send_header('Content-length', str(len(status)))
        self.end_headers()
        self.wfile.write(status)

    def do_POST(self):
        data = self.rfile.read(int(self.headers['Content-length']))
        q = cgi.parse_qs(data)
        real_url = q['url'][0]
        real_headers = dict(cgi.parse_qsl(q['headers'][0]))
        real_req = q['req'][0]
        ssl_cert = None
        if 'ssl_cert' in q:
            ssl_cert = q['ssl_cert'][0]
        key = len(REQUESTS.keys()) + 1
        Thread(target=worker,
               args=(key, real_url, real_headers, real_req, ssl_cert)).start()
        self.send_response(200, 'OK')
        self.send_header('Content-length', len(str(key)))
        self.end_headers()
        self.wfile.write(str(key))


def worker(key, real_url, real_headers, real_req, ssl_cert):
    print "(%s) Working on %s %s %s" % (key, real_url, real_headers, real_req)
    try:
        req = Request(real_url, real_req, real_headers)
        if ssl_cert:
            key_file = "%s/%s.key" % (CERT_PATH, ssl_cert)
            cert_file = "%s/%s.pem" % (CERT_PATH, ssl_cert)
            req.key_file = key_file
            req.cert_file = cert_file
        result = urlopen(req).read()
        REQUESTS[key] = dumps((200, result))
    except HTTPError, e:
        print e.code, e.msg, e.hdrs
        REQUESTS[key] = dumps((e.code, e.fp.read()))
    except:
        REQUESTS[key] = dumps((500, format_exc()))


def run(addr=(PROXY_HOST, PROXY_PORT)):
    print addr
    http.HTTPServer(addr, Handler).serve_forever()


if __name__ == '__main__':
    run()
