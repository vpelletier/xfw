xfw is an eXtensible Fixed-Width file handling module.

Features
========

- field types (integers, strings, dates) are declared independently of
  file structure, and can be extended through subclassing. (BaseField
  subclasses)

- multi-field structure declaration (FieldList class)

- non-homogeneous file file structure declaration (FieldListFile)

- checksum/hash computation helpers (ChecksumedFile subclasses)

- does not depend on line notion (file may not contain CR/LF chars at all
  between successive field sets)

Missing features / bugs
=======================

- string trucating is multi-byte (UTF-8, ...) agnostic, and will mindlessly cut
  in the middle of any entity
  If your fields are defined in number of characters of some encoding, just use
  provide xfw with unicode objects, and do the transcoding outside it. See
  `codecs` standard module.

- proper interface declaration

- fields (IntegerField, DateTimeField) should cast by default when parsing

- FieldList total length should be made optional, and only used to
  auto-generate annonymous padding at record end when longer that the sum of
  individual fields lengths.

Example
=======

Dislaimer: give file format is purely hypothetical, does not some from any spec
I know of, should not be taken as a guideline but just as a showcase of xfw
capabilities.

Let's assume a file composed of a general header, containing some
constant-value 5-char identifier, a 3-char integer giving the number of records
contained, and an optional 20-char comment. It is followed by records, composed
of a header itself composed of a date (YYYYMMDD), a row type (2-char integer)
and number of rows (2-char integer), and followed by rows. Row types all start
with a time (HHMMSS), followed by fields which depend on row type:

- type 1: a 10-char string

- type 2: a 2-char integer, 8 chars of padding, a 1-char integer

To run the following code as a doctest, run::

   python -m doctest README.rst

Declare all file structures::

    >>> import xfw
    >>> ROOT_HEADER = xfw.FieldList([
    ...     (xfw.StringField(5), True, 'header_id'),
    ...     (xfw.IntegerField(3, cast=True), True, 'block_count'),
    ...     (xfw.StringField(15), False, 'comment'),
    ... ], 23, fixed_value_dict={
    ...     'header_id': 'HEAD1',
    ... })
    >>> BLOCK_HEADER = xfw.FieldList([
    ...     (xfw.DateTimeField('%Y%m%d', cast=True), True, 'date'),
    ...     (xfw.IntegerField(2, cast=True), True, 'row_type'),
    ...     (xfw.IntegerField(2, cast=True), True, 'row_count'),
    ... ], 12)
    >>> ROW_BASE = xfw.FieldList([
    ...     (xfw.DateTimeField('%H%M%S', cast=True), True, 'time'),
    ... ], 6)
    >>> ROW_TYPE_DICT = {
    ...     1: xfw.FieldList([
    ...         ROW_BASE,
    ...         (xfw.StringField(10), True, 'description'),
    ...     ], 16),
    ...     2: xfw.FieldList([
    ...         ROW_BASE,
    ...         (xfw.IntegerField(2, cast=True), True, 'some_value'),
    ...         (xfw.StringField(8), False, None), # annonymous padding
    ...         (xfw.IntegerField(1, cast=True), True, 'another_value'),
    ...     ], 17),
    ... }
    >>> def blockCallback(head, item_list=None):
    ...     if item_list is None:
    ...         row_count = head['row_count']
    ...     else:
    ...         row_count = len(item_list)
    ...     return row_count, ROW_TYPE_DICT[head['row_type']]
    >>> FILE_STRUCTURE = xfw.ConstItemTypeFile(
    ...     ROOT_HEADER,
    ...     'block_count',
    ...     xfw.FieldListFile(
    ...         BLOCK_HEADER,
    ...         blockCallback,
    ...         separator='\n',
    ...     ),
    ...     separator='\n',
    ... )

Parse sample file through a hash helper wrapper (SHA1)::

    >>> from cStringIO import StringIO
    >>> sample_file = StringIO(
    ...     'HEAD1002blah           \n'
    ...     '201112260101\n'
    ...     '115500other str \n'
    ...     '201112260201\n'
    ...     '11550099        8'
    ... )
    >>> from datetime import datetime
    >>> checksumed_wrapper = xfw.SHA1ChecksumedFile(sample_file)
    >>> parsed_file = FILE_STRUCTURE.parseStream(checksumed_wrapper)
    >>> parsed_file == \
    ... (
    ...     {
    ...         'header_id': 'HEAD1',
    ...         'block_count': 2,
    ...         'comment': 'blah',
    ...     },
    ...     [
    ...         (
    ...             {
    ...                 'date': datetime(2011, 12, 26, 0, 0),
    ...                 'row_type': 1,
    ...                 'row_count': 1,
    ...             },
    ...             [
    ...                 {
    ...                     'time': datetime(1900, 1, 1, 11, 55),
    ...                     'description': 'other str',
    ...                 },
    ...             ]
    ...         ),
    ...         (
    ...             {
    ...                 'date': datetime(2011, 12, 26, 0, 0),
    ...                 'row_type': 2,
    ...                 'row_count': 1,
    ...             },
    ...             [
    ...                 {
    ...                     'time': datetime(1900, 1, 1, 11, 55),
    ...                     'some_value': 99,
    ...                     'another_value': 8,
    ...                 },
    ...             ]
    ...         ),
    ...     ],
    ... )
    True

Verify SHA1 was properly accumulated::

    >>> import hashlib
    >>> hashlib.sha1(sample_file.getvalue()).hexdigest() == checksumed_wrapper.getHexDigest()
    True

Generate a file from parsed data (as it was verified correct above)::

    >>> generated_stream = StringIO()
    >>> FILE_STRUCTURE.generateStream(generated_stream, parsed_file)
    >>> generated_stream.getvalue() == sample_file.getvalue()
    True

Likewise, using unicode objects and producing streams of different binary
length, although containing the same number of entities. Note that
fixed-values defined in format declaration are optional (ex: `header_id`),
and dependent values are automaticaly computed (ex: `block_count`).

Generate with unicode chars fitting in single UTF-8-encoded bytes::

    >>> import codecs
    >>> encoded_writer = codecs.getwriter('UTF-8')
    >>> input_data = (
    ...    {
    ...        'comment': u'Just ASCII',
    ...    },
    ...    [],
    ... )
    >>> sample_file = StringIO()
    >>> FILE_STRUCTURE.generateStream(encoded_writer(sample_file), input_data)
    >>> sample_file.getvalue()
    'HEAD1000Just ASCII     '
    >>> len(sample_file.getvalue())
    23

Generate again, with chars needing more bytes when encoded, and demonstrating
checksum generation::

    >>> input_data = (
    ...    {
    ...        'comment': u'\u3042\u3044\u3046\u3048\u304a\u304b\u304d\u304f\u3051\u3053\u3055\u3057\u3059\u305b\u305d',
    ...    },
    ...    [],
    ... )
    >>> sample_file = StringIO()
    >>> checksumed_wrapper = xfw.SHA1ChecksumedFile(sample_file)
    >>> FILE_STRUCTURE.generateStream(encoded_writer(checksumed_wrapper), input_data)
    >>> sample_file.getvalue()
    'HEAD1000\xe3\x81\x82\xe3\x81\x84\xe3\x81\x86\xe3\x81\x88\xe3\x81\x8a\xe3\x81\x8b\xe3\x81\x8d\xe3\x81\x8f\xe3\x81\x91\xe3\x81\x93\xe3\x81\x95\xe3\x81\x97\xe3\x81\x99\xe3\x81\x9b\xe3\x81\x9d'
    >>> len(sample_file.getvalue())
    53
    >>> hashlib.sha1(sample_file.getvalue()).hexdigest() == checksumed_wrapper.getHexDigest()
    True
