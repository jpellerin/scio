from setuptools import setup, find_packages

CLASSIFIERS = """\
Development Status :: 5 - Production/Stable
Intended Audience :: Developers
License :: OSI Approved :: BSD License
Natural Language :: English
Programming Language :: Python
Programming Language :: Python :: 2.4
Programming Language :: Python :: 2.5
Programming Language :: Python :: 2.6
Programming Language :: Python :: 2.7
Topic :: Software Development :: Object Brokering""".split("\n")

setup(
    name='Scio',
    version='0.9',
    author_email='oss@leapfrogdevelopment.com',
    url='http://bitbucket.org/leapfrogdevelopment/scio/overview',
    install_requires=['lxml>=2.2', 'python-dateutil'],
    tests_require=['nose>=1.0', 'Sphinx>=1.0'],
    packages=find_packages(),
    classifiers=CLASSIFIERS,
    )
