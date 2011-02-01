from urllib2 import urlopen
import scio.client


def reviver(classname, proto=object, args=()):
      return proto.__new__(getattr(pickling_client.type, classname), *args)


pickling_client = scio.Client(urlopen('http://lyricwiki.org/server.php?wsdl'),
                              reduce_callback=reviver)


def globs(globs):
    globs['pickling_client'] = pickling_client
    return globs
