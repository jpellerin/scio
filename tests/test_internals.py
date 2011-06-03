from decimal import Decimal
from StringIO import StringIO
import pickle
from urllib2 import HTTPError

from lxml import etree
from nose.tools import raises, eq_

import scio
import scio.client
import helpers


def test_type_mappings():
    print scio.client.Element._typemap
    assert 'int' in scio.client.Element._typemap


def test_enum_restriction_not_first_element():
    zf = scio.Client(helpers.support('zfapi.wsdl', 'r'))
    print zf.type.ApiAccessMask._values
    assert zf.type.ApiAccessMask._values


def test_array_detection():
    lw = scio.client.Factory(helpers.support('lyrics.wsdl', 'r'))
    aos = lw.wsdl.xpath("//*[@name='ArrayOfstring']")[0]
    print aos
    assert lw._is_array(aos)


def test_list_unmarshalling():
    lw = scio.Client(helpers.support('lyrics.wsdl', 'r'))
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
    lw = scio.Client(helpers.support('lyrics.wsdl', 'r'))
    fr = """<env:Envelope xmlns:env='http://schemas.xmlsoap.org/soap/envelope/'><env:Header></env:Header><env:Body><env:Fault xmlns:env='http://schemas.xmlsoap.org/soap/envelope/'><faultcode>env:Server</faultcode><faultstring>java.lang.NullPointerException</faultstring></env:Fault></env:Body></env:Envelope>"""
    e = HTTPError("http://foo", 500, "Server Error", {}, StringIO(fr))
    lw.handle_error(lw.service.getArtist.method, e)


@raises(scio.NotSOAP)
def test_no_soap_body_in_xml_response_raises_notsoap():
    lw = scio.Client(helpers.support('lyrics.wsdl', 'r'))
    er = "<a/>"
    lw.handle_response(None, er)


@raises(HTTPError)
def test_handle_error_with_blank_body():
    lw = scio.Client(helpers.support('lyrics.wsdl', 'r'))
    fr = "<a/>"
    e = HTTPError("http://foo", 500, "Server Error", {}, StringIO(fr))
    lw.handle_error(lw.service.getArtist.method, e)


def test_fault_includes_detail_if_set():
    try:
        lw = scio.Client(helpers.support('lyrics.wsdl', 'r'))
        fr = """<env:Envelope xmlns:env='http://schemas.xmlsoap.org/soap/envelope/'><env:Header></env:Header><env:Body><env:Fault xmlns:env='http://schemas.xmlsoap.org/soap/envelope/'><faultcode>env:Server</faultcode><faultstring>java.lang.NullPointerException</faultstring><detail>Got bitten by monkey</detail></env:Fault></env:Body></env:Envelope>"""
        e = HTTPError("http://foo", 500, "Server Error", {}, StringIO(fr))
        lw.handle_error(lw.service.getArtist.method, e)
    except scio.Fault, f:
        print str(f)
        assert f.detail

    try:
        lw = scio.Client(helpers.support('lyrics.wsdl', 'r'))
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


def test_empty_complextype_not_true():
    lw = scio.Client(helpers.support('lyrics.wsdl'))
    song = lw.type.SongResult()
    assert not song


def test_iter_over_self():
    lw = scio.Client(helpers.support('lyrics.wsdl'))
    song = lw.type.SongResult(artist='Prince', song='Nothing Compares 2 U')

    c = 0
    for s in song:
        assert s.song == 'Nothing Compares 2 U'
        c += 1
    assert c == 1, "Self iter yield <> 1 item"


def test_iter_empty():
    lw = scio.Client(helpers.support('lyrics.wsdl'))
    song = lw.type.SongResult()
    c = 0
    for p in song:
        c += 1
    assert c == 0, "Empty type iter yielded items"


def test_fault_is_unpickleable():
    try:
        lw = scio.Client(helpers.support('lyrics.wsdl', 'r'))
        fr = """<env:Envelope xmlns:env='http://schemas.xmlsoap.org/soap/envelope/'><env:Header></env:Header><env:Body><env:Fault xmlns:env='http://schemas.xmlsoap.org/soap/envelope/'><faultcode>env:Server</faultcode><faultstring>java.lang.NullPointerException</faultstring><detail>Got bitten by monkey</detail></env:Fault></env:Body></env:Envelope>"""
        e = HTTPError("http://foo", 500, "Server Error", {}, StringIO(fr))
        lw.handle_error(lw.service.getArtist.method, e)
    except scio.Fault, f:
        pf = pickle.dumps(f)
        upf = pickle.loads(pf)
        assert unicode(upf) == unicode(f)
