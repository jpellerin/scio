import os

from lxml import etree
from cPickle import dumps, loads
from nose.tools import eq_

import helpers

HERE = os.path.dirname(__file__)

lw = zf = None

def setup():
    global lw, zf
    lwclient, zfclient, bzclient = helpers.generate_static_clients()
    lw = lwclient.Client()
    zf = zfclient.Client()


def test_pickle_and_unpickle_single_type():
    album = lw.type.AlbumResult(
        artist='The Mountain Goats',
        album='The Life of the World to Come',
        year=2009)
    eq_(album.year, 2009)
    eq_(album.artist, 'The Mountain Goats')
    eq_(album.album, 'The Life of the World to Come')

    pickled_album = dumps(album)
    unpickled_album = loads(pickled_album)

    eq_(unpickled_album.year, 2009)
    eq_(unpickled_album.artist, 'The Mountain Goats')
    eq_(unpickled_album.album, 'The Life of the World to Come')

    repickled = dumps(unpickled_album)
    reunpickled_album = loads(repickled)
    eq_(reunpickled_album.year, 2009)
    eq_(reunpickled_album.artist, 'The Mountain Goats')
    eq_(reunpickled_album.album, 'The Life of the World to Come')

    repickled_same = dumps(album)
    reunpickled_same = loads(repickled_same)


def test_pickle_unpickle_deep_type():
    v = etree.fromstring(
        '<Address><FirstName>Fred</FirstName></Address>')
    ifn = zf.type.Address(v).FirstName
    eq_(str(ifn), 'Fred')
    pickled_ifn = dumps(ifn)
    unpickled_ifn = loads(pickled_ifn)
    eq_(str(unpickled_ifn), str(ifn))


def test_pickle_simple_enum():
    g = zf.type.PhotoSetType('Gallery')
    r = dumps(g)
    un_g = loads(r)
    eq_(str(g), str(un_g))


def test_pickle_unpickle_array():
    rsp = etree.fromstring(helpers.support('lyric_rsp.xml', 'r').read())[0][0]
    print rsp
    artist, albums = lw.service.getArtist.method.output(rsp)
    boy = albums[0]
    pickled_boy = dumps(boy)
    unpickled_boy = loads(pickled_boy)

    eq_(unpickled_boy.album, u'Boy');
    eq_(unpickled_boy.year, 1980)
    eq_(len(unpickled_boy.songs), 11)
    eq_(unpickled_boy.songs[0], u'I Will Follow')
    eq_(unpickled_boy.songs[10], u'Shadows And Tall Trees')
