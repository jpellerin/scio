#!/bin/sh
#
# This glue script allows tests to be run via tox from nosemacs.
# See: http://bitbucket.org/jpellerin/nosemacs
#

root=`dirname $0`
cd $root
tox -e py26 -- $@
