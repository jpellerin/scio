================
Scio: Quickstart
================

1. Install
==========

Scio may be installed via easy_install, pip or manually. If you are
handling dependencies yourself, note that Scio requires a recent
version of `lxml`_ (2.2 or later).

2. Create a client
==================

To create a `SOAP`_ client, pass an open filehandle referencing a
`WSDL`_ document to :class:`scio.Client`. Scio will parse the WSDL
file and generate :ref:`types` and :ref:`services` that you can use to
call SOAP services and handle the results of those calls.

>>> import scio
>>> import urllib2
>>> lyrics = scio.Client(
... urllib2.urlopen('http://lyricwiki.org/server.php?wsdl'))

3. Call a SOAP Method
=====================

To call a SOAP method, use the *service* attribute of the
client. Refer to the method by name, and pass the parameters to the
method as positional arguments. Some SOAP methods take builtin types
as input, some take SOAP types. Methods return one or more SOAP types.

>>> artist, albums = lyrics.service.getArtist('Wilco')

Many simple SOAP types subclass builtin Python types and can be used almost
interchangeably with them.

>>> artist
u'Wilco'
>>> type(artist)
<class 'scio.client.StringType'>

There are list-like types as well as string, object, and number-like types.

>>> type(albums)
<class 'scio.client.AlbumDataArray'>

Object-like types (Complex types in SOAP parlance) behave *mostly*
like normal objects. See :ref:`types` for some ways in which they differ.

>>> am = albums[0]
>>> type(am)
<class 'scio.client.AlbumData'>
>>> am.album
u'A.M.'
>>> am.songs
[u'I Must Be High', u'Casino Queen', u'Box Full Of Letters', u"Shouldn't Be Ashamed", u'Pick Up The Change', u'I Thought I Held You', u"That's Not The Issue", u"It's Just That Simple", u"Should've Been In Love", u'Passenger Side', u'Dash 7', u'Blue Eyed Soul', u'Too Far Apart']

4. Generate documentation
=========================

Scio includes a `Sphinx`_ extension that you can use to generate
documentation for a WSDL file. This is a good way to get started when
working with an unfamiliar SOAP service. See :doc:`auto`.


.. _lxml : http://codespeak.net/lxml/
.. _SOAP : http://en.wikipedia.org/wiki/SOAP
.. _WSDL : http://www.w3.org/TR/wsdl
.. _Sphinx : http://sphinx.pocoo.org/
