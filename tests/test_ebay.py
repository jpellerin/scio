import scio
import helpers
import time

def test_parse_shoppingservice():
    client = scio.Client(helpers.support('shoppingservice.wsdl', 'r'))

def test_parse_ebaysvc():
    st = time.time()
    client = scio.Client(helpers.support('eBaySvc.wsdl', 'r'))
    taken = time.time() - st
    print "parsed 4.2mb wsdl in", taken
test_parse_ebaysvc.slow = True
