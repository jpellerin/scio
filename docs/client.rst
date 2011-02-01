============
Scio: Client
============

Client API
==========

.. autoclass :: scio.Client
   :members:

.. _types :

SOAP Types
==========

Constructing SOAP types
-----------------------

>>> import scio
>>> from lxml import etree
>>> from urllib2 import urlopen
>>> wsdl = open('tests/support/adwords_trafficestimatorservice.wsdl', 'r')
>>> adwords = scio.Client(wsdl)

When calling SOAP methods or constructing SOAP type instances,
parameters may be passed as keyword arguments.

>>> cpg = adwords.type.CampaignRequest(
...     networkTargeting=adwords.type.NetworkTarget(
...     networkTypes=["GoogleSearch"]))

Attributes of SOAP type instances may be set directly, even
deeply. Intermediary types will be auto-vivified. List types may be
specified as lists, or built up into lists by multiple assignments.

>>> cpg.geoTargeting.cityTargets.cities = 'Houston'
>>> cpg.geoTargeting.cityTargets.cities = 'Ontario'
>>> cpg.geoTargeting.countryTargets.countries = ['USA', 'Canada']

The repr() of a SOAP type instance is useful.

>>> cpg
CampaignRequest(geoTargeting=GeoTarget(cityTargets=CityTargets(cities=[u'Houston', u'Ontario']), countryTargets=CountryTargets(countries=[u'USA', u'Canada'])), networkTargeting=NetworkTarget(networkTypes=[NetworkType.GoogleSearch]))

Serializing a SOAP type instance into xml is easy. Outside of the
normal call context, you may have to provide an xml tag name.

>>> etree.tostring(cpg.toxml(tag='CampaignRequest'))
'<CampaignRequest xmlns="https://adwords.google.com/api/adwords/v13"><geoTargeting><cityTargets><cities>Houston</cities><cities>Ontario</cities></cityTargets><countryTargets><countries>USA</countries><countries>Canada</countries></countryTargets></geoTargeting><networkTargeting><networkTypes>GoogleSearch</networkTypes></networkTargeting></CampaignRequest>'

You can introspect the available types.

>>> dir(adwords.type)
['AdGroupEstimate', 'AdGroupRequest', 'ApiError', 'ApiException', 'CampaignEstimate', 'CampaignRequest', 'Circle', 'CityTargets', 'CountryTargets', 'GeoTarget', 'KeywordEstimate', 'KeywordRequest', 'KeywordTraffic', 'KeywordTrafficRequest', 'KeywordType', 'LanguageTarget', 'MetroTargets', 'NetworkTarget', 'NetworkType', 'ProximityTargets', 'RegionTargets', '__class__', '__delattr__', '__dict__', '__doc__', '__format__', '__getattribute__', '__hash__', '__init__', '__module__', '__new__', '__reduce__', '__reduce_ex__', '__repr__', '__setattr__', '__sizeof__', '__str__', '__subclasshook__', '__weakref__', '_client', 'applicationToken', 'checkKeywordTraffic', 'checkKeywordTrafficResponse', 'clientCustomerId', 'clientEmail', 'developerToken', 'email', 'estimateAdGroupList', 'estimateAdGroupListResponse', 'estimateCampaignList', 'estimateCampaignListResponse', 'estimateKeywordList', 'estimateKeywordListResponse', 'operations', 'password', 'requestId', 'responseTime', 'units', 'useragent']


.. _services :

Method Calls
============

The `service` attribute of the client instance contains all of the
method calls defined in the wsdl file. To call a SOAP method, call the
appropriate method under `service` with the proper arguments.

>>> url = 'http://lyricwiki.org/server.php?wsdl'
>>> lyrics = scio.Client(urlopen(url))

Methods return one or more SOAP type instances.

>>> artist, albums = lyrics.service.getArtist('Wilco')
>>> artist
u'Wilco'

That looks like a plain unicode string, but it's really a SOAP type.

>>> type(artist)
<class 'scio.client.StringType'>

SOAP types may be complex, and include lists, other types, etc.

>>> am = albums[0]
>>> am.album
u'A.M.'
>>> am.songs
[u'I Must Be High', u'Casino Queen', u'Box Full Of Letters', u"Shouldn't Be Ashamed", u'Pick Up The Change', u'I Thought I Held You', u"That's Not The Issue", u"It's Just That Simple", u"Should've Been In Love", u'Passenger Side', u'Dash 7', u'Blue Eyed Soul', u'Too Far Apart']

You can introspect the available services.

>>> dir(lyrics.service)
['__class__', '__delattr__', '__dict__', '__doc__', '__format__', '__getattribute__', '__hash__', '__init__', '__module__', '__new__', '__reduce__', '__reduce_ex__', '__repr__', '__setattr__', '__sizeof__', '__str__', '__subclasshook__', '__weakref__', '_client', '_methods', 'checkSongExists', 'getAlbum', 'getArtist', 'getHometown', 'getSOTD', 'getSong', 'getSongResult', 'method_class', 'postAlbum', 'postArtist', 'postSong', 'postSong_flags', 'searchAlbums', 'searchArtists', 'searchSongs']

