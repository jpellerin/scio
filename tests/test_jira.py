import scio
import helpers


def test_parse_jira():
    client = scio.Client(helpers.support('jira.wsdl', 'r'))
