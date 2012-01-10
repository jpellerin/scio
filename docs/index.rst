=======================================
Scio: SOAP Classes for Input and Output
=======================================

.. warning ::

   Scio is under active development. These documents may change frequently as new
   versions are released. Please make sure that you are looking at the
   most current version.

Scio is a python library for interacting with `SOAP`_ services. It parses
`WSDL`_ files to produce type classes and service calls that may be used
to call SOAP services and handle the results of those calls in a
humane way.

Scio also includes a `Sphinx`_ extension for generating documentation
from WSDL files.

While Scio itself is pure python, it requires `lxml`_.

Contents:

.. toctree::
   :maxdepth: 2

   quickstart.rst
   client.rst
   api.rst
   pickling.rst
   proxy_example.rst
   auto.rst
   codegen.rst

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`

Changelog
=========

.. include :: ../CHANGELOG


.. _Sphinx : http://sphinx.pocoo.org/
.. _SOAP : http://en.wikipedia.org/wiki/SOAP
.. _WSDL : http://www.w3.org/TR/wsdl
.. _lxml : http://codespeak.net/lxml/
