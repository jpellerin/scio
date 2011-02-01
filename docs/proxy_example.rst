====================================
Scio: custom client subclass example
====================================

To do weird things when calling SOAP methods, subclass
:class:`scio.Client` and override the :meth:`scio.Client.send`
method. In the example below, the client is overridden to proxy SOAP
requests through a separate daemon, to avoid blocking on them.

.. literalinclude :: ../examples/proxy.py
   :language: python
