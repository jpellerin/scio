===============================
Scio: documenting SOAP services
===============================

Scio includes a Sphinx extension, `scio.autowsdl`, that you can use to
automatically document SOAP services defined in wsdl files.

To use autowsdl, include it in your conf.py:

.. code-block :: python

   extensions = ['sphinx.ext.autodoc', 'sphinx.ext.doctest',
                 'sphinx.ext.intersphinx', 'scio.autowsdl']

Then in a source reST document processed by Sphinx, include a declaration like:

.. code-block :: rest

   .. autowsdl: path/to/wsdl_file.wsdl
      :namespace: stuffz

The generated documentation looks like the example below. The classes
documented will be given a pseudo-module namespace to avoid collisions
when generating documentation for multiple wsdl files. By default, the
namespace is the basename of the wsdl file, with the file extension
removed. If you want to customize the namespace, set the
``:namespace:`` option in the ``.. autowsdl`` block.

Example: LyricWiki
==================

.. autowsdl :: ../tests/support/lyrics.wsdl
   :namespace: lyricwiki
