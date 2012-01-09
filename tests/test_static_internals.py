from StringIO import StringIO
import pickle
import types
from urllib2 import HTTPError

from lxml import etree
from nose.tools import raises, eq_

import scio
import scio.client
import scio.gen
import helpers


M = {}

def setup():
    lyr = types.ModuleType('lyr')
    lwc = scio.gen.gen(scio.Client(helpers.support('lyrics.wsdl', 'r')))
    exec lwc in lyr.__dict__
    M['lyr'] = lyr

    zf = types.ModuleType('zf')
    zfc = scio.gen.gen(scio.Client(helpers.support('zfapi.wsdl', 'r')))
    print zfc
    exec zfc in zf.__dict__
    M['zf'] = zf


def test_enum_restriction_not_first_element():
    zf = M['zf'].Client()
    print zf.type.ApiAccessMask._values
    assert zf.type.ApiAccessMask._values


def test_list_unmarshalling():
    lw = M['lyr'].Client()
    rsp = etree.fromstring(helpers.support('lyric_rsp.xml', 'r').read())[0][0]
    print rsp
    artist, albums = lw.service.getArtist.method.output(rsp)
    print artist, albums
    assert albums
    eq_(len(albums), 22)
    boy = albums[0]
    eq_(boy.album, u'Boy');
    eq_(boy.year, 1980)
    eq_(len(boy.songs), 11)
    eq_(boy.songs[0], u'I Will Follow')
    eq_(boy.songs[10], u'Shadows And Tall Trees')


@raises(scio.Fault)
def test_handle_error_raises_fault():
    lw = M['lyr'].Client()
    fr = """<env:Envelope xmlns:env='http://schemas.xmlsoap.org/soap/envelope/'><env:Header></env:Header><env:Body><env:Fault xmlns:env='http://schemas.xmlsoap.org/soap/envelope/'><faultcode>env:Server</faultcode><faultstring>java.lang.NullPointerException</faultstring></env:Fault></env:Body></env:Envelope>"""
    e = HTTPError("http://foo", 500, "Server Error", {}, StringIO(fr))
    lw.handle_error(lw.service.getArtist.method, e)


@raises(scio.NotSOAP)
def test_no_soap_body_in_xml_response_raises_notsoap():
    lw = M['lyr'].Client()
    er = "<a/>"
    lw.handle_response(None, er)


@raises(HTTPError)
def test_handle_error_with_blank_body():
    lw = M['lyr'].Client()
    fr = "<a/>"
    e = HTTPError("http://foo", 500, "Server Error", {}, StringIO(fr))
    lw.handle_error(lw.service.getArtist.method, e)


def test_fault_includes_detail_if_set():
    try:
        lw = M['lyr'].Client()
        fr = """<env:Envelope xmlns:env='http://schemas.xmlsoap.org/soap/envelope/'><env:Header></env:Header><env:Body><env:Fault xmlns:env='http://schemas.xmlsoap.org/soap/envelope/'><faultcode>env:Server</faultcode><faultstring>java.lang.NullPointerException</faultstring><detail>Got bitten by monkey</detail></env:Fault></env:Body></env:Envelope>"""
        e = HTTPError("http://foo", 500, "Server Error", {}, StringIO(fr))
        lw.handle_error(lw.service.getArtist.method, e)
    except scio.Fault, f:
        print str(f)
        assert f.detail

    try:
        lw = M['lyr'].Client()
        fr = """<env:Envelope xmlns:env='http://schemas.xmlsoap.org/soap/envelope/'><env:Header></env:Header><env:Body><env:Fault xmlns:env='http://schemas.xmlsoap.org/soap/envelope/'><faultcode>env:Server</faultcode><faultstring>java.lang.NullPointerException</faultstring></env:Fault></env:Body></env:Envelope>"""
        e = HTTPError("http://foo", 500, "Server Error", {}, StringIO(fr))
        lw.handle_error(lw.service.getArtist.method, e)
    except scio.Fault, f:
        print str(f)
        assert not f.detail


def test_instantiate_complex_type_with_string():
    snx = scio.Client(helpers.support('synxis.wsdl'))
    price = snx.type.MarketSegment('Irate organists', MarketSegmentCode='IRO')
    assert price._content == 'Irate organists'
    assert price.MarketSegmentCode == 'IRO'


def test_instantiate_complex_type_with_dict():
    lw = M['lyr'].Client()
    album = lw.type.AlbumResult({'artist': 'Wilco', 'album': 'Summerteeth', 'year': 1999})
    assert album.artist == 'Wilco'
    assert album.album == 'Summerteeth'
    assert album.year == 1999


def test_empty_complextype_not_true():
    lw = M['lyr'].Client()
    song = lw.type.SongResult()
    assert not song


def test_iter_over_self():
    lw = M['lyr'].Client()
    song = lw.type.SongResult(artist='Prince', song='Nothing Compares 2 U')

    c = 0
    for s in song:
        assert s.song == 'Nothing Compares 2 U'
        c += 1
    assert c == 1, "Self iter yield <> 1 item"


def test_iter_empty():
    lw = M['lyr'].Client()
    song = lw.type.SongResult()
    c = 0
    for p in song:
        c += 1
    assert c == 0, "Empty type iter yielded items"


def test_fault_is_unpickleable():
    try:
        lw = M['lyr'].Client()
        fr = """<env:Envelope xmlns:env='http://schemas.xmlsoap.org/soap/envelope/'><env:Header></env:Header><env:Body><env:Fault xmlns:env='http://schemas.xmlsoap.org/soap/envelope/'><faultcode>env:Server</faultcode><faultstring>java.lang.NullPointerException</faultstring><detail>Got bitten by monkey</detail></env:Fault></env:Body></env:Envelope>"""
        e = HTTPError("http://foo", 500, "Server Error", {}, StringIO(fr))
        lw.handle_error(lw.service.getArtist.method, e)
    except scio.Fault, f:
        pf = pickle.dumps(f)
        upf = pickle.loads(pf)
        assert unicode(upf) == unicode(f)
