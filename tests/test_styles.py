import scio
import helpers
from lxml import etree
from nose.tools import eq_


def test_zfapi_is_document_literal_wrapper():
    zf = scio.Client(helpers.support('zfapi.wsdl', 'r'))
    eq_(zf.service.Authenticate.method.input.formatter,
        scio.client.DocumentLiteralWrapperInputFormatter)


def test_rpc_enc_includes_type_attrib():
    lw = scio.Client(helpers.support('lyrics.wsdl', 'r'))
    req = lw.service.checkSongExists.method.input('prince', '1999').toxml()
    c = etree.Element('c')
    for e in req:
        c.append(e)
    req_xml = etree.tostring(c)
    print req_xml
    artist = c[0][0]
    print artist.attrib
    assert artist.attrib
