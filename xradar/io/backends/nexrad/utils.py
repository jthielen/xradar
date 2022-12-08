# Copyright (c) 2022, openradar developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Utilities for parsing NEXRAD files.

TODO acknowledge metpy
"""
import bz2
import datetime
import contextlib
import gzip
import io
import logging
import struct

import numpy as np
from scipy.constants import day, milli


log = logging.getLogger(__name__)


def bzip_blocks_decompress_all(data):
    """Decompress all of the bzip2-ed blocks.
    Returns the decompressed data as a `bytearray`.

    TODO: compare to bzip approach in pyart
    """
    frames = bytearray()
    offset = 0
    while offset < len(data):
        block_cmp_bytes = abs(int.from_bytes(data[offset:offset + 4], 'big', signed=True))
        offset += 4
        try:
            frames += bz2.decompress(data[offset:offset + block_cmp_bytes])
            offset += block_cmp_bytes
        except OSError:
            # If we've decompressed any frames, this is an error mid-stream, so warn, stop
            # trying to decompress and let processing proceed
            if frames:
                logging.warning('Error decompressing bz2 block stream at offset: %d',
                                offset - 4)
                break
            else:  # Otherwise, this isn't a bzip2 stream, so bail
                raise ValueError('Not a bz2 stream.')
    return frames


def nexrad_to_datetime(julian_date, ms_midnight):
    """Convert NEXRAD date time format to python `datetime.datetime`."""
    # Subtracting one from julian_date is because epoch date is 1
    return datetime.datetime.utcfromtimestamp((julian_date - 1) * day + ms_midnight * milli)


def scaler(scale):
    """Create a function that scales by a specific value."""
    def inner(val):
        return val * scale
    return inner


def angle(val):
    """Convert an integer value to a floating point angle."""
    return val * 360. / 2**16


def remap_status(val):
    """Convert status integer value to appropriate bitmask."""
    status = 0
    bad = BAD_DATA if val & 0xF0 else 0
    val &= 0x0F
    if val == 0:
        status = START_ELEVATION
    elif val == 1:
        status = 0
    elif val == 2:
        status = END_ELEVATION
    elif val == 3:
        status = START_ELEVATION | START_VOLUME
    elif val == 4:
        status = END_ELEVATION | END_VOLUME
    elif val == 5:
        status = START_ELEVATION | LAST_ELEVATION

    return status | bad


START_ELEVATION = 0x1
END_ELEVATION = 0x2
START_VOLUME = 0x4
END_VOLUME = 0x8
LAST_ELEVATION = 0x10
BAD_DATA = 0x20


def _open_as_needed(filename, mode='rb'):
    r"""Return a file-object given either a filename or an object.

    Handles opening with the right class based on the file extension. Useful for NEXRAD
    files using external compression.

    Code ported from MetPy (Copyright (c) 2008-2022, MetPy Developers) ...TODO license...
    """
    # Handle file-like objects
    if hasattr(filename, 'read'):
        # See if the file object is really gzipped or bzipped.
        lead = filename.read(4)

        # If we can seek, seek back to start, otherwise read all the data into an
        # in-memory file-like object.
        try:
            filename.seek(0)
        except (AttributeError, io.UnsupportedOperation):
            filename = io.BytesIO(lead + filename.read())

        # If the leading bytes match one of the signatures, pass into the appropriate class.
        with contextlib.suppress(AttributeError):
            lead = lead.encode('ascii')
        if lead.startswith(b'\x1f\x8b'):
            filename = gzip.GzipFile(fileobj=filename)
        elif lead.startswith(b'BZh'):
            filename = bz2.BZ2File(filename)

        return filename

    # This will convert pathlib.Path instances to strings
    filename = str(filename)

    if filename.endswith('.bz2'):
        return bz2.BZ2File(filename, mode)
    elif filename.endswith('.gz'):
        return gzip.GzipFile(filename, mode)
    else:
        kwargs = {'errors': 'surrogateescape'} if mode != 'rb' else {}
        return open(filename, mode, **kwargs)  # noqa: SIM115


class IOBuffer:
    """Holds bytes from a buffer to simplify parsing and random access.
    
    TODO metpy acknowledge
    """

    def __init__(self, source):
        """Initialize the IOBuffer with the source data."""
        self._data = bytearray(source)
        self.reset()

    @classmethod
    def fromfile(cls, fobj):
        """Initialize the IOBuffer with the contents of the file object."""
        return cls(fobj.read())

    def reset(self):
        """Reset buffer back to initial state."""
        self._offset = 0
        self.clear_marks()

    def set_mark(self):
        """Mark the current location and return its id so that the buffer can return later."""
        self._bookmarks.append(self._offset)
        return len(self._bookmarks) - 1

    def jump_to(self, mark, offset=0):
        """Jump to a previously set mark."""
        self._offset = self._bookmarks[mark] + offset

    def offset_from(self, mark):
        """Calculate the current offset relative to a marked location."""
        return self._offset - self._bookmarks[mark]

    def clear_marks(self):
        """Clear all marked locations."""
        self._bookmarks = []

    def splice(self, mark, newdata):
        """Replace the data after the marked location with the specified data."""
        self.jump_to(mark)
        self._data = self._data[:self._offset] + bytearray(newdata)

    def read_struct(self, struct_class):
        """Parse and return a structure from the current buffer offset."""
        this_struct = struct_class.unpack_from(memoryview(self._data), self._offset)
        self.skip(struct_class.size)
        return this_struct

    def read_func(self, func, num_bytes=None):
        """Parse data from the current buffer offset using a function."""
        # only advance if func succeeds
        res = func(self.get_next(num_bytes))
        self.skip(num_bytes)
        return res

    def read_ascii(self, num_bytes=None):
        """Return the specified bytes as ascii-formatted text."""
        return self.read(num_bytes).decode('ascii')

    def read_binary(self, num, item_type='B'):
        """Parse the current buffer offset as the specified code."""
        if 'B' in item_type:
            return self.read(num)

        if item_type[0] in ('@', '=', '<', '>', '!'):
            order = item_type[0]
            item_type = item_type[1:]
        else:
            order = '@'

        return list(self.read_struct(struct.Struct(order + f'{int(num):d}' + item_type)))

    def read_int(self, size, endian, signed):
        """Parse the current buffer offset as the specified integer code."""
        return int.from_bytes(self.read(size), endian, signed=signed)

    def read_array(self, count, dtype):
        """Read an array of values from the buffer."""
        ret = np.frombuffer(self._data, offset=self._offset, dtype=dtype, count=count)
        self.skip(ret.nbytes)
        return ret

    def read(self, num_bytes=None):
        """Read and return the specified bytes from the buffer."""
        res = self.get_next(num_bytes)
        self.skip(len(res))
        return res

    def get_next(self, num_bytes=None):
        """Get the next bytes in the buffer without modifying the offset."""
        if num_bytes is None:
            return self._data[self._offset:]
        else:ytes):
        """Jump the ahead the specified bytes in the buffer."""
        if num_bytes is None:
            self._offset = len(self._data)
        else:
            self._offset += num_bytes

    def check_remains(self, num_bytes):
        """Check that the number of bytes specified remains in the buffer."""
        return len(self._data[self._offset:]) == num_bytes

    def truncate(self, num_bytes):
        """Remove the specified number of bytes from the end of the buffer."""
        self._data = self._data[:-num_bytes]

    def at_end(self):
        """Return whether the buffer has reached the end of data."""
        return self._offset >= len(self._data)

    def __getitem__(self, item):
        """Return the data at the specified location."""
        return self._data[item]

    def __str__(self):
        """Return a string representation of the IOBuffer."""
        return f'Size: {len(self._data)} Offset: {self._offset}'

    def __len__(self):
        """Return the amount of data in the buffer."""
        return len(self._data)


class NamedStruct(struct.Struct):
    """Parse bytes using :class:`Struct` but provide named fields.
    
    TODO metpy acknowledge
    """

    def __init__(self, info, prefmt='', tuple_name=None):
        """Initialize the NamedStruct."""
        if tuple_name is None:
            tuple_name = 'NamedStruct'
        names, fmts = zip(*info)
        self.converters = {}
        conv_off = 0
        for ind, i in enumerate(info):
            if len(i) > 2:
                self.converters[ind - conv_off] = i[-1]
            elif not i[0]:  # Skip items with no name
                conv_off += 1
        self._tuple = namedtuple(tuple_name, ' '.join(n for n in names if n))
        super().__init__(prefmt + ''.join(f for f in fmts if f))

    def _create(self, items):
        if self.converters:
            items = list(items)
            for ind, conv in self.converters.items():
                items[ind] = conv(items[ind])
            if len(items) < len(self._tuple._fields):
                items.extend([None] * (len(self._tuple._fields) - len(items)))
        return self.make_tuple(*items)

    def make_tuple(self, *args, **kwargs):
        """Construct the underlying tuple from values."""
        return self._tuple(*args, **kwargs)

    def unpack(self, s):
        """Parse bytes and return a namedtuple."""
        return self._create(super().unpack(s))

    def unpack_from(self, buff, offset=0):
        """Read bytes from a buffer and return as a namedtuple."""
        return self._create(super().unpack_from(buff, offset))

    def unpack_file(self, fobj):
        """Unpack the next bytes from a file object."""
        return self.unpack(fobj.read(self.size))

    def pack(self, **kwargs):
        """Pack the arguments into bytes using the structure."""
        t = self.make_tuple(**kwargs)
        return super().pack(*t)


class BitField:
    """Convert an integer to a string for each bit.
    
    TODO metpy acknowledge
    """

    def __init__(self, *names):
        """Initialize the list of named bits."""
        self._names = names

    def __call__(self, val):
        """Return a list with a string for each True bit in the integer."""
        if not val:
            return None

        bits = []
        for n in self._names:
            if val & 0x1:
                bits.append(n)
            val >>= 1
            if not val:
                break

        # Return whole list if empty or multiple items, otherwise just single item
        return bits[0] if len(bits) == 1 else bits


            return self._data[self._offset:self._offset + num_bytes]

    def skip(self, num_bytes):
        """Jump the ahead the specified bytes in the buffer."""
        if num_bytes is None:
            self._offset = len(self._data)
        else:
            self._offset += num_bytes

    def check_remains(self, num_bytes):
        """Check that the number of bytes specified remains in the buffer."""
        return len(self._data[self._offset:]) == num_bytes

    def truncate(self, num_bytes):
        """Remove the specified number of bytes from the end of the buffer."""
        self._data = self._data[:-num_bytes]

    def at_end(self):
        """Return whether the buffer has reached the end of data."""
        return self._offset >= len(self._data)

    def __getitem__(self, item):
        """Return the data at the specified location."""
        return self._data[item]

    def __str__(self):
        """Return a string representation of the IOBuffer."""
        return f'Size: {len(self._data)} Offset: {self._offset}'

    def __len__(self):
        """Return the amount of data in the buffer."""
        return len(self._data)


class NamedStruct(struct.Struct):
    """Parse bytes using :class:`Struct` but provide named fields.
    
    TODO metpy acknowledge
    """

    def __init__(self, info, prefmt='', tuple_name=None):
        """Initialize the NamedStruct."""
        if tuple_name is None:
            tuple_name = 'NamedStruct'
        names, fmts = zip(*info)
        self.converters = {}
        conv_off = 0
        for ind, i in enumerate(info):
            if len(i) > 2:
                self.converters[ind - conv_off] = i[-1]
            elif not i[0]:  # Skip items with no name
                conv_off += 1
        self._tuple = namedtuple(tuple_name, ' '.join(n for n in names if n))
        super().__init__(prefmt + ''.join(f for f in fmts if f))

    def _create(self, items):
        if self.converters:
            items = list(items)
            for ind, conv in self.converters.items():
                items[ind] = conv(items[ind])
            if len(items) < len(self._tuple._fields):
                items.extend([None] * (len(self._tuple._fields) - len(items)))
        return self.make_tuple(*items)

    def make_tuple(self, *args, **kwargs):
        """Construct the underlying tuple from values."""
        return self._tuple(*args, **kwargs)

    def unpack(self, s):
        """Parse bytes and return a namedtuple."""
        return self._create(super().unpack(s))

    def unpack_from(self, buff, offset=0):
        """Read bytes from a buffer and return as a namedtuple."""
        return self._create(super().unpack_from(buff, offset))

    def unpack_file(self, fobj):
        """Unpack the next bytes from a file object."""
        return self.unpack(fobj.read(self.size))

    def pack(self, **kwargs):
        """Pack the arguments into bytes using the structure."""
        t = self.make_tuple(**kwargs)
        return super().pack(*t)


# This works around times when we have more than 255 items and can't use
# NamedStruct. This is a CPython limit for arguments.
class DictStruct(Struct):
    """Parse bytes using :class:`Struct` but provide named fields using dictionary access."""

    def __init__(self, info, prefmt=''):
        """Initialize the DictStruct."""
        names, formats = zip(*info)

        # Remove empty names
        self._names = [n for n in names if n]

        super().__init__(prefmt + ''.join(f for f in formats if f))

    def _create(self, items):
        return dict(zip(self._names, items))

    def unpack(self, s):
        """Parse bytes and return a dict."""
        return self._create(super().unpack(s))

    def unpack_from(self, buff, offset=0):
        """Unpack the next bytes from a file object."""
        return self._create(super().unpack_from(buff, offset))


class Enum:
    """Map values to specific strings."""

    def __init__(self, *args, **kwargs):
        """Initialize the mapping."""
        # Assign values for args in order starting at 0
        self.val_map = dict(enumerate(args))

        # Invert the kwargs dict so that we can map from value to name
        self.val_map.update(zip(kwargs.values(), kwargs.keys()))

    def __call__(self, val):
        """Map an integer to the string representation."""
        return self.val_map.get(val, f'Unknown ({val})')


class Bits:
    """Breaks an integer into a specified number of True/False bits."""

    def __init__(self, num_bits):
        """Initialize the number of bits."""
        self._bits = range(num_bits)

    def __call__(self, val):
        """Convert the integer to the list of True/False values."""
        return [bool((val >> i) & 0x1) for i in self._bits]


class BitField:
    """Convert an integer to a string for each bit."""

    def __init__(self, *names):
        """Initialize the list of named bits."""
        self._names = names

    def __call__(self, val):
        """Return a list with a string for each True bit in the integer."""
        if not val:
            return None

        bits = []
        for n in self._names:
            if val & 0x1:
                bits.append(n)
            val >>= 1
            if not val:
                break

        # Return whole list if empty or multiple items, otherwise just single item
        return bits[0] if len(bits) == 1 else bits


class Array:
    """Use a Struct as a callable to unpack a bunch of bytes as a list."""

    def __init__(self, fmt):
        """Initialize the Struct unpacker."""
        self._struct = Struct(fmt)

    def __call__(self, buf):
        """Perform the actual unpacking."""
        return list(self._struct.unpack(buf))
