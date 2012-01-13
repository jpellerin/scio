import unittest

import scio.client
import scio.gen

import helpers

def mock_urlopen(url):
    fn = url.split('/')[-1]
    return helpers.support(fn, 'r')


class TestSchemaImport(unittest.TestCase):

    def setUp(self):
        self.urlopen = scio.client.urlopen
        scio.client.urlopen = mock_urlopen
        self.client = scio.client.Client(
            helpers.support('CampaignManagementService.wsdl', 'r'))

    def tearDown(self):
        scio.client.urlopen = self.urlopen

    def test_imported_types_exist(self):
        # tests that this type exists and can be used w/strings
        tok = self.client.type.ApplicationToken('fred')
        self.assertEqual(tok, 'fred')

    def test_generated_client_with_imports(self):
        code = scio.gen.gen(self.client)
        print code
        ns = {}
        exec code in ns
        tok = ns['Client']().type.ApplicationToken('fred')
        self.assertEqual(tok, 'fred')
        assert not 'StringType' in ns['Client']._types._types
