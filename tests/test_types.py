import scio.client as sc
from datetime import datetime
from lxml import etree
from nose.tools import assert_almost_equal


def test_datetime_from_string():
    dt = sc.DateTimeType('2009-01-01T00:00:00')
    assert dt.year == 2009
    assert dt.month == 1
    assert dt.day == 1
    assert dt.hour == 0
    assert dt.minute == 0
    assert dt.second == 0
    assert not dt.microsecond
    assert str(dt) == '2009-01-01T00:00:00'


def test_datetime_from_element():
    e = etree.Element('WhatEver')
    e.text = '2009-01-01T00:00:00'
    dt = sc.DateTimeType(e)
    assert dt.year == 2009
    assert dt.month == 1
    assert dt.day == 1
    assert dt.hour == 0
    assert dt.minute == 0
    assert dt.second == 0
    assert not dt.microsecond
    assert not dt.utcoffset()
    assert str(dt) == '2009-01-01T00:00:00'


def test_datetime_with_timezone():
    dt = sc.DateTimeType('2009-01-01T00:00:00+02:00')
    print dt
    assert dt.year == 2009
    assert dt.month == 1
    assert dt.day == 1
    assert dt.hour == 0
    assert dt.utcoffset()
    assert str(dt) == '2009-01-01T00:00:00+02:00'


def test_boolean_from_string():
    assert sc.BooleanType('true')
    assert sc.BooleanType('True')
    assert sc.BooleanType('1')
    assert sc.BooleanType(1)
    assert not sc.BooleanType('false')
    assert not sc.BooleanType('False')
    assert not sc.BooleanType('0')
    assert not sc.BooleanType(0)


def test_date_from_string():
    dt = sc.DateType('2009-01-01')
    assert dt.year == 2009
    assert dt.month == 1
    assert dt.day == 1
    assert str(dt) == '2009-01-01'


def test_date_from_element():
    e = etree.Element('WhatEver')
    e.text = '2009-01-01'
    dt = sc.DateType(e)
    assert dt.year == 2009
    assert dt.month == 1
    assert dt.day == 1
    assert str(dt) == '2009-01-01'


def test_time_from_string():
    dt = sc.TimeType('06:15:21')
    assert dt.hour == 6
    assert dt.minute == 15
    assert dt.second == 21
    assert not dt.microsecond
    assert str(dt) == '06:15:21'


def test_time_from_element():
    e = etree.Element('WhatEver')
    e.text = '06:15:21'
    dt = sc.TimeType(e)
    assert dt.hour == 6
    assert dt.minute == 15
    assert dt.second == 21
    assert not dt.microsecond
    assert not dt.utcoffset()
    assert str(dt) == '06:15:21'


def test_time_with_timezone():
    dt = sc.TimeType('06:15:21+02:00')
    print dt
    assert dt.hour == 6
    assert dt.minute == 15
    assert dt.second == 21
    assert dt.utcoffset()
    assert str(dt) == '06:15:21+02:00'


def test_long_from_string():
    dt = sc.LongType("9223372036854775807")
    assert dt == 9223372036854775807L
    assert str(dt) == "9223372036854775807"


def test_float_from_string():
    fv = sc.FloatType('2.01')
    assert_almost_equal(fv, 2.01)

