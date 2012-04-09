from __future__ import with_statement
import os

from scio import client, gen

HERE = os.path.dirname(__file__)
_support = os.path.join(HERE, 'support')


def support(filename, *arg, **kw):
    return open(os.path.join(_support, filename), *arg, **kw)


def generate_static_clients():
    lwcode = gen.gen(client.Client(support('lyrics.wsdl', 'r')))
    with open(os.path.join(HERE, 'lwclient.py'), 'w') as fh:
        fh.write(lwcode)
    zfcode = gen.gen(client.Client(support('zfapi.wsdl', 'r')))
    with open(os.path.join(HERE, 'zfclient.py'), 'w') as fh:
        fh.write(zfcode)
    bzcode = gen.gen(client.Client(support('boyzoid.wsdl', 'r')))
    with open(os.path.join(HERE, 'bzclient.py'), 'w') as fh:
        fh.write(bzcode)

    import lwclient
    import zfclient
    import bzclient
    return lwclient, zfclient, bzclient
