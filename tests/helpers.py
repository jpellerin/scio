import os

_support = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    'support')

def support(filename, *arg, **kw):
    return open(os.path.join(_support, filename), *arg, **kw)
