from scio import client, gen

import helpers


def test_static_generation_does_not_raise_error():
    def check(wsdl):
        code = gen.gen(client.Client(helpers.support(wsdl)))
        ns = {}
        print code
        exec code in ns
    for wsdl in ('CampaignService.wsdl', 'InfoService.wsdl', 'jira.wsdl',
                 'boyzoid.wsdl', 'lyrics.wsdl', 'ServicedAccountService.wsdl',
                 'shoppingservice.wsdl', 'synxis.wsdl', 'zfapi.wsdl'):
        print wsdl
        yield check, wsdl
