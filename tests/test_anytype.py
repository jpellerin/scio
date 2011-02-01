import scio
import helpers
from lxml import etree

def test_deserialize_boyzoid_response():
    client = scio.Client(helpers.support('boyzoid.wsdl', 'r'))
    response = etree.parse(helpers.support('bz_response.xml', 'r')).getroot()
    quote = client.service.getQuote.method.output(response)
    print quote, quote.item
    print quote.item[1].value
