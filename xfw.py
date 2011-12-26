##############################################################################
#
# Copyright (c) 2009-2011 Nexedi SA and Contributors. All Rights Reserved.
#                    Pelletier Vincent <vincent@nexedi.com>
#
# WARNING: This program as such is intended to be used by professional
# programmers who take the whole responsability of assessing all potential
# consequences resulting from its eventual inadequacies and bugs
# End users who are looking for a ready-to-use solution with commercial
# garantees and support are strongly adviced to contract a Free Software
# Service Company
#
# This program is Free Software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA  02111-1307, USA.
#
##############################################################################
import hashlib
from datetime import datetime
strptime = datetime.strptime
dummy_datetime = datetime(1900, 1, 1) # Any date will do

__all__ = [
    'BaseField', 'PaddedField',
    'StringField', 'IntegerField', 'DateTimeField',
    'FieldList',
    'FieldListFile', 'HeadFile', 'ConstItemTypeFile',
    'ChecksumedFile',
]

class BaseField(object):
    """
    Virtual class.

    A field is a subset of a string, qualified by a specific length.
    """
    # Char to ignore when probing data presence.
    # Overload in subclass to customise.
    _blank_char = ' '

    def __init__(self, length, truncate=False, cast=False):
        """
        Defines a field of given length.

        If truncate is True, field will silently truncate received data when
        rendering data too big to fit in its length, other wise it will raise
        an exception.

        If cast is True, the result of parsing using this field will be
        converted (the type of conversion depends on the field type), otherwise
        it will be a raw string of field's length.
        """
        self.length = length
        self.truncate = truncate
        self.cast = cast

    def getLength(self):
        return self.length

    def render(self, data=None):
        raise NotImplementedError

    def parse(self, data):
        if self.cast:
            result = self._cast(data)
        else:
            result = data
        return result

    def _cast(self, data):
        raise NotImplementedError

    def probe(self, data):
        return bool(data.strip(self._blank_char))

class PaddedField(BaseField):
    """
    Virtual class.
    """

    def _pad(self, data, pad_length):
        raise NotImplementedError

    def _strip(self, data):
        raise NotImplementedError

    def _render(self, data):
        data_len = len(data)
        if data_len > self.length:
            if self.truncate:
                data = data[:self.length]
            else:
                raise ValueError, 'Data too long to fit type width: ' \
                    '%r, %r available. Data: %r' % (data_len, self.length,
                        data)
        elif data_len < self.length:
            data = self._pad(data, self.length - data_len)
        return data

    def parse(self, data):
        return super(PaddedField, self).parse(self._strip(data))

class StringField(PaddedField):
    def _pad(self, data, pad_length):
        return data + ' ' * pad_length

    def _strip(self, data):
        return data.rstrip(' ')

    def render(self, data=''):
        if not isinstance(data, basestring):
            raise TypeError, 'Expected data of string type, got %s' % (
                type(data), )
        return self._render(data)

    def _cast(self, data):
        return data

class IntegerField(PaddedField):
    def _pad(self, data, pad_length):
        return '0' * pad_length + data

    def _strip(self, data):
        return data.lstrip('0') or '0'

    def render(self, data=0):
        if isinstance(data, basestring):
            # Duplicates work, but this ensures we receive a valid integer
            # representation.
            data = int(data)
        assert isinstance(data, (int, long)) or \
            (self.truncate and isinstance(data, float)), repr(data)
        data = str(int(data))
        return self._render(data)

    def parse(self, data):
        if not self.probe(data):
            data = '0'
        return super(IntegerField, self).parse(data)

    def _cast(self, data):
        return int(data)

class DateTimeField(BaseField):
    def __init__(self, fmt, truncate=False, cast=False):
        assert not truncate
        # Computing our length has the advantage of validating given format
        super(DateTimeField, self).__init__(len(dummy_datetime.strftime(fmt)),
            cast=cast)
        self.fmt = fmt
        self.null = '0' * self.length

    def render(self, data=None):
        if data is None:
            result = self.null
        elif isinstance(data, basestring):
            if len(data) != self.length:
                raise ValueError('Invalid length %r for format %r' % (
                    len(data), self.fmt))
            result = data
        else:
            result = data.strftime(self.fmt)
        return result

    def parse(self, data):
        if not self.probe(data):
            return None
        return super(DateTimeField, self).parse(data)

    def _cast(self, data):
        if data == self.null:
            return None
        return strptime(data, self.fmt)

class FieldList(object):
    """
    A field list is a linear, ordered sequence of fields.
    Those fields must be identified uniquely with a name, and can be optional.
    """
    def __init__(self, field_list, total_length, separator='', padding_id=None,
            fixed_value_dict=()):
        """
        Defines a sequence of fields.

        field_list must be a list of 3-tuples composed of:
        - the field (instance of a subclass of BaseField)
        - wether it is required or not (boolean)
        - a name unique to its field list
        It is possible for any item in field_list to be an instance of
        FieldList class, in which case its content (padding inclued !) and
        fixed values will be reused in place of that element. Its separator
        value is ignored.
        """
        self.separator = separator
        self.total_length = total_length
        self.field_list = expanded_field_list = []
        append = expanded_field_list.append
        extend = expanded_field_list.extend
        self.fixed_value_dict = fixed_value_dict = dict(fixed_value_dict)
        setdefault = fixed_value_dict.setdefault
        for field in field_list:
            if isinstance(field, FieldList):
                extend(field._getFieldList())
                for key, value in field._getFixedValueDict().iteritems():
                    setdefault(key, value)
            else:
                append(field)
        offset = len(separator) * (len(expanded_field_list) - 1)
        field_id_set = set()
        if padding_id is not None:
            field_id_set.add(padding_id)
        for field, _, field_id in expanded_field_list:
            if field_id is not None:
                if field_id in field_id_set:
                    raise ValueError, 'Field %r already present.' % (
                        field_id, )
                field_id_set.add(field_id)
            offset += field.getLength()
        if offset > total_length:
            raise ValueError, 'Maximum length exceeded: %r, limit is %r' % \
                (offset, total_length)
        else:
            to_pad = total_length - offset
            if padding_id is not None:
                self.field_list.append(
                    (getFieldType(StringField, to_pad), False, padding_id))
                to_pad = 0
            self.padding_length = to_pad

    def _getFixedValueDict(self):
        """
        For internal use only.
        """
        return self.fixed_value_dict

    def _getFieldList(self):
        """
        For internal use only.
        """
        return self.field_list

    def _checkValues(self, data_dict):
        """
        Check data_dict against reference values, raises ValueError if a
        mismatch is found.
        Adds missing keys to data_dict.
        """
        for key, value in self.fixed_value_dict.iteritems():
            actual_value = data_dict.setdefault(key, value)
            if actual_value != value:
                raise ValueError, '%r: expected %r, got %r' % (key, value,
                    actual_value)

    def generate(self, data_dict):
        """
        Generate a string from field list description and given data mapping.

        data_dict must be a dict composed of:
        - key: field name
        - value: field value

        If a field is declared mandatory in field list description but is
        missing in this dict, an exception will be raised.
        """
        self._checkValues(data_dict)
        result = []
        append = result.append
        for field, mandatory, field_id in self.field_list:
            if field_id is None:
                data = field.render()
            elif data_dict.get(field_id) is not None:
                data = field.render(data_dict[field_id])
            else:
                if mandatory:
                    raise ValueError, 'Field %r is mandatory' % (field_id, )
                data = field.render()
            append(data)
        if self.padding_length:
            append(' ' * self.padding_length)
        rendered = self.separator.join(result)
        if len(rendered) != self.total_length:
            raise ValueError, 'Internal consistency error: rendered string ' \
                'length %r, expected %r' % (len(rendered), self.total_length)
        return rendered

    def parse(self, rendered):
        """
        Parse a string into a data mapping.

        rendered must have a length identical to field list description,
        otherwise an exception will be raised.

        Returned value is a dict containing all fields declared in the field
        list description.
        """
        assert isinstance(rendered, basestring), repr(rendered)
        if len(rendered) != self.total_length:
            raise ValueError, 'Data length missmatch: expected %i, got ' \
                '%i (%r)' % (self.total_length, len(rendered), rendered)
        data_dict = {}
        offset = 0
        separator_len = len(self.separator)
        for field, mandatory, field_id in self.field_list:
            field_length = field.getLength()
            if field_id is not None:
                field_data = rendered[offset:offset+field_length]
                parsed_value = field.parse(field_data)
                if parsed_value is None and mandatory:
                    raise ValueError('Mandatory field %r empty: %r' % 
                      (field_id, field_data))
                data_dict[field_id] = parsed_value
            offset += field_length
            next_separator = rendered[offset:offset+separator_len]
            if next_separator:
                if next_separator != self.separator:
                    raise ValueError, 'Separator %r expected, got %r ' \
                        '(in %r)' % (self.separator, rendered[offset:],
                            rendered)
                offset += separator_len
        assert offset + self.padding_length == self.total_length, offset
        self._checkValues(data_dict)
        return data_dict

    def parseStream(self, stream):
        return self.parse(stream.read(self.total_length))

    def generateStream(self, stream, data_dict):
        stream.write(self.generate(data_dict))

class FieldListFile(object):
    def __init__(self, head, item_callback, separator=''):
        r"""
        Files parsed/generated by this class follow the following structure:
            FILE: HEAD SEPARATOR [ITEM SEPARATOR [ITEM SEPARATOR [...]]]
        Where:
          SEPARATOR is a fixed string.
            HEAD is a string which can be parsed by instance given in <head>
            parameter.
            ITEM is a string which can be parsed by instance returned by
            <item_callback>, and there is a known number of such items (also as
            returned by <item_callback>).

        Chunk (head or item) generator & parser:
        Instances responsible for individual chunk parsing & generation must
        implement the following interface:
            parseStream(stream) -> parsed_value
            generateStream(stream, parsed_value)

        Stream:
        streams given to this class methods must implement the following
        methods:
        - read(length) -> data
        - write(data)
        They might implement tell() for more detailed exception messages. If
        it's not implemented, it must not be available at all.

        head
            instance implementing the chunk interface.
        item_callback (callable)
            Callable receiving a parsed head a parameter and expected to
            return 2 values:
            - number of items (ignored when generating)
            - instance implementing  the chunk interface
        separator (string)
            (see above definition)
        """
        self._head = head
        self._item_callback = item_callback
        self._separator = separator
        self._separator_len = len(separator)

    def eatSeparator(self, stream):
        separator = stream.read(self._separator_len)
        if separator != self._separator:
            tell = getattr(stream, 'tell', None)
            if tell is None:
                at = ''
            else:
                at = ' at %i' % (tell() - len(separator), )
            raise ValueError('Unexpected separator value%s: %r' % (at,
                separator))

    def addSeparator(self, stream):
        stream.write(self._separator)

    def _parseStreamItems(self, stream, item, item_count):
        item_list = []
        if item_count:
            append = item_list.append
            eatSeparator = self.eatSeparator
            item_parse = item.parseStream
            for _ in xrange(item_count - 1):
                append(item_parse(stream))
                eatSeparator(stream)
            append(item_parse(stream))
        return item_list

    def _generateStreamItems(self, stream, item, item_list):
        if item_list:
            addSeparator = self.addSeparator
            item_generate = item.generateStream
            for item_data in item_list[:-1]:
                item_generate(stream, item_data)
                addSeparator(stream)
            item_generate(stream, item_list[-1])

    def parseStream(self, stream, eat_last_separator=False):
        parsed_head = self._head.parseStream(stream)
        item_count, item = self._item_callback(parsed_head)
        if item_count:
            self.eatSeparator(stream)
            item_list = self._parseStreamItems(stream, item, item_count)
        else:
            item_list = None
        if eat_last_separator:
            self.eatSeparator(stream)
        return parsed_head, item_list

    def _generateStream(self, stream, parsed_head, item_list, item,
            add_last_separator):
        self._head.generateStream(stream, parsed_head)
        if item_list:
            self.addSeparator(stream)
            self._generateStreamItems(stream, item, item_list)
        if add_last_separator:
            self.addSeparator(stream)

    def _getGenerateStreamParameters(self, args):
        assert isinstance(args, (tuple, list)), args
        if len(args) == 1:
            args = (args[0], None)
        return args

    def generateStream(self, stream, args, add_last_separator=False):
        head_dict, item_list = self._getGenerateStreamParameters(args)
        _, item = self._item_callback(head_dict, item_list)
        self._generateStream(stream, head_dict, item_list, item,
            add_last_separator)

class HeadFile(FieldListFile):
    """
    Special case of a FieldListFile: contains just a head.
    """
    def __init__(self, head, **kw):
        super(HeadFile, self).__init__(head, self._callback, **kw)

    def _callback(self, head_dict, item_list=None):
        assert item_list is None, item_list
        return 0, None

class ConstItemTypeFile(FieldListFile):
    """
    Special case of a FieldListFile: items type does not depend on head
    content.
    """
    def __init__(self, head, item_count_key, item, **kw):
        """
        item_count_key (string)
            Identifier in a parsed head giving the number of contained items.
        item (FieldList, FieldListFile)
            Format of contained items.
            Can be another FieldListFile if these items are composed.
        """
        if (item_count_key is None) ^ (item is None):
            raise ValueError('Inconsistent values for item_count_key and item')
        self._item_count_key = item_count_key
        self._item = item
        super(ConstItemTypeFile, self).__init__(head, self._callback, **kw)

    def _callback(self, head_dict, item_list=None):
        if item_list is not None:
            head_dict[self._item_count_key] = len(item_list)
        return head_dict[self._item_count_key], self._item

class ChecksumedFile(object):
    """
    Virtual class.

    Helper class to manipulate checksumed files which contain their own
    checksum.
    Obviously, the checksum itself cannot be part of the checksumed data.
    Don't instanciate this class directly, use *ChecksumedFile classes (where
    * is desired hash algorithm name).

    Limitations:
    - cannot seek
    """
    def __init__(self, stream):
        """
        stream
            Some stream. Typically, an opened file object.
        """
        self._stream = stream
        self._hash = self._hash_class()
        self._ahead = None

    def updateAhead(self, data):
        if self._ahead is not None:
            self._hash.update(self._ahead)
        self._ahead = data

    def discardAhead(self, replacement=None):
        """
        Discard read-ahead buffer.
        replacement
            A replacement string to use to update hash.
        """
        self._ahead = replacement

    def update(self, data):
        update = self._hash.update
        if self._ahead is not None:
            update(self._ahead)
            self._ahead = None
        update(data)

    def getDigest(self):
        return self._hash.digest()

    def getHexDigest(self):
        return self._hash.hexdigest()

    def _read(self, update, args, kw):
        data = self._stream.read(*args, **kw)
        update(data)
        return data

    def _readline(self, update, args, kw):
        data = self._stream.readline(*args, **kw)
        update(data)
        return data

    def read(self, *args, **kw):
        return self._read(self.update, args, kw)

    def readline(self, *args, **kw):
        return self._readline(self.update, args, kw)

    def write(self, data):
        self._stream.write(data)
        self.update(data)

    def readAhead(self, *args, **kw):
        """
        Same as read, but checksum is not updated with returned data.
        It will be updated on the next read call (ahead or not) with data
        returned by this call.
        """
        return self._read(self.updateAhead, args, kw)

    def readlineAhead(self, *args, **kw):
        """
        See readAhead: same, for readline.
        """
        return self._readline(self.updateAhead, args, kw)

    def peek(self, length):
        """
        Read <length> bytes from current position.
        Doesn't alter current position, doesn't update checksum.
        """
        pos = self._stream.tell()
        data = self._stream.read(length)
        self._stream.seek(pos)
        return data

    def peekLine(self):
        """
        Read one line from current position.
        Doesn't alter current position, doesn't update checksum.
        """
        pos = self._stream.tell()
        data = self._stream.readline()
        self._stream.seek(pos)
        return data

    def tell(self):
        return self._stream.tell()

    def tellAhead(self):
        return self.tell() + len(self._ahead)

_globals = globals()
append = __all__.append
try:
    algorithm_list = hashlib.algorithms
except AttributeError:
    algorithm_list = [x for x in (
      'md5', 'sha1', 'sha224', 'sha256', 'sha384', 'sha512') if getattr(
      hashlib, x, None) is not None]
for algorithm in algorithm_list:
    class_name = algorithm.upper() + 'ChecksumedFile'
    _globals[class_name] = type(
        class_name,
        (ChecksumedFile, ),
        {
            '_hash_class': getattr(hashlib, algorithm),
        }
    )
    append(class_name)
del append
del _globals

