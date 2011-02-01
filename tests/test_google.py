import scio
import helpers


class StubClient(scio.Client):
    sent = []

    def send(self, method, request):
        self.sent.append((method, request))


def test_parse_adwords():
    client = scio.Client(helpers.support('adwords_campaignservice.wsdl', 'r'))


def test_method_call_with_headers():
    StubClient.sent = []
    client = StubClient(helpers.support('adwords_campaignservice.wsdl', 'r'))
    client.service.getCampaign(id=1,
                               useragent="foo (mozilla)",
                               email="bar@foo.com",
                               clientEmail="buz@baz.com",
                               clientCustomerId="5",
                               developerToken="99dt",
                               applicationToken="12at"
                               )
    print StubClient.sent
    request = StubClient.sent[0][1].data
    print request
    assert 'email>' in request
    assert 'bar@foo.com' in request
    assert '99dt' in request
    assert '12at' in request
    assert 'foo (mozilla)'


def test_get_all_campaigns():
    StubClient.sent = []
    client = StubClient(helpers.support('adwords_campaignservice.wsdl', 'r'))
    client.service.getAllAdWordsCampaigns(dummy=0,
                                          useragent="foo (mozilla)",
                                          email="bar@foo.com",
                                          clientEmail="buz@baz.com",
                                          clientCustomerId="5",
                                          developerToken="99dt",
                                          applicationToken="12at")
    request = StubClient.sent[0][1].data
    print request
    assert 'getAllAdWordsCampaigns' in request
    assert '</dummy>' in request


def test_header_unmarshalling():
    client = scio.Client(
        helpers.support('adwords_trafficestimatorservice.wsdl', 'r'))
    response = helpers.support('adwords_response_example.xml', 'r').read()
    result, headers = client.handle_response(
        client.service.estimateKeywordList.method,
        response)
    print result
    print headers
    assert headers['operations'] == 1
    assert headers['responseTime'] == 10636
    assert headers['units'] == 1
    assert 'eb21e6667abb131c117b58086f75abbd' in headers['requestId']
