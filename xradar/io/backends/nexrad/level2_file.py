# Copyright (c) 2022, openradar developers.
# Distributed under the MIT License. See LICENSE for more info.
"""
NEXRAD Level II data
====================

Reads data from NEXRAD Level II files and contained messages.

...TODO...

This implementation uses code from MetPy (Copyright (c) 2008-2022, MetPy Developers) and PyART (Copyright (c) 2013, UChicago Argonne, LLC) ...TODO licenses...

"""
from ._message_structures.extended import msg15_code_map, msg2_additional_fmt, msg2_fmt
from ._message_structures.standard import (
    data_block_fmt,
    message_header_fmt,
    msg1_fmt,
    msg1_data_header,
    msg31_data_header_fmt,
    msg31_volume_constant_fmt,
    msg31_elevation_constant_fmt,
    msg5_fmt,
    msg5_elevation_fmt,
    Radial,
    radial_constant_fmt_v1,
    radial_constant_fmt_v2,
    volume_header_fmt,
)
from .utils import _open_as_needed, IOBuffer


log = logging.getLogger(__name__)


AR2_BLOCKSIZE = 2432  # 12 (CTM) + 2416 (Msg hdr + data) + 4 (FCS)
CTM_HEADER_SIZE = 12


class NEXRADLevel2File:
    """
    Class for accessing data in a NEXRAD (WSR-88D) Level II file.

    NEXRAD Level II files [1]_, also know as NEXRAD Archive Level II or
    WSR-88D Archive level 2, are available from the NOAA National Climate Data
    Center [2]_ as well as on the UCAR THREDDS Data Server [3]_. Files with
    uncompressed messages and compressed (BZ2) messages are supported, as are
    externally compressed files

    Parameters
    ----------
    filename : str
        Filename of Archive II file to read.

    Attributes
    ----------
    clutter_filter_bypass_map : dict, optional
        Unpacked clutter filter bypass map, if present
    dt : `datetime.datetime`
        The date and time of the data
    maintenance_data : `collections.namedtuple`, optional
        Unpacked maintenance data information, if found
    maintenance_data_desc : dict, optional
        Descriptions of maintenance data fields, if maintenance data present
    nscans : int
        Number of scans in the file.
    radial_records : list
        Radial (1 or 31) messages in the file.
    rda : dict, optional
        Unpacked RDA adaptation data, if present
    rda_adaptation_desc : dict, optional
        Descriptions of RDA adaptation data, if adaptation data present
    rda_status : `collections.namedtuple`, optional
        Unpacked RDA status information, if found
    scan_msgs : list of arrays
        Each element specifies the indices of the message in the
        radial_records attribute which belong to a given scan.
    stid : str
        The ID of the radar station
    sweeps : list[tuple]
        TODO from metpy, need relative to pyart implementation
    volume_header : `collections.namedtuple`
        Volume header
    vcp : dict
        VCP information dictionary.
    _records : list
        A list of all records (message) in the file.
    _fobj : file-like
        File like object from which data is read.
    _msg_type : '31' or '1':
        Type of radial messages in file.

    References
    ----------
    .. [1] http://www.roc.noaa.gov/WSR88D/Level_II/Level2Info.aspx
    .. [2] http://www.ncdc.noaa.gov/
    .. [3] http://thredds.ucar.edu/thredds/catalog.html

    Notes
    -----

    TODO: document: self._buffer

    """

    def __init__(self, filename, *, has_volume_header=True):
        """Create instance of `NEXRADLevel2File`.

        Parameters
        ----------
        filename : str or file-like object
            If str, the name of the file to be opened. Gzip-ed files are
            recognized with the extension '.gz', as are bzip2-ed files with
            the extension `.bz2` If `filename` is a file-like object,
            this will be read from directly.

        """
        # Open file, with buffer helper class
        fobj = _open_as_needed(filename)
        with contextlib.closing(fobj):
            self._buffer = IOBuffer.fromfile(fobj)

        # Save original file object (for later file handling operations)
        self._fobj = fobj

        # Try to read the volume header. If this fails, or we're told we don't have one
        # then we fall back and try to just read messages, assuming we have e.g. one of
        # the real-time chunks.
        try:
            if has_volume_header:
                self._read_volume_header()
        except (OSError, ValueError):
            log.warning('Unable to read volume header. Attempting to read messages.')
            self._buffer.reset()

        # See if we need to apply bz2 decompression
        start = self._buffer.set_mark()
        try:
            self._buffer = IOBuffer(self._buffer.read_func(bzip_blocks_decompress_all))
        except ValueError:
            self._buffer.jump_to(start)

        # Now we're all initialized, we can proceed with reading in data
        self._read_data()

    def _read_volume_header(self):
        self.volume_header = self._buffer.read_struct(volume_header_fmt)
        self.dt = nexrad_to_datetime(self.volume_header.date, self.volume_header.time)
        self.stid = self.volume_header.icao  # TODO needed? icao vs. stid?

    def _read_data(self):
        self._msg_buf = {}
        self.sweeps = []
        self.rda_status = []
        while not self._buffer.at_end():
            # Clear old file book marks and set the start of message for
            # easy jumping to the end
            self._buffer.clear_marks()
            msg_start = self._buffer.set_mark()

            # Skip CTM
            self._buffer.skip(CTM_HEADER_SIZE)

            # Read the message header
            msg_hdr = self._buffer.read_struct(message_header_fmt)
            log.debug('Got message: %s (at offset %d)', str(msg_hdr), self._buffer._offset)

            # The AR2_BLOCKSIZE accounts for the CTM header before the
            # data, as well as the Frame Check Sequence (4 bytes) after
            # the end of the data.
            msg_bytes = AR2_BLOCKSIZE

            # If the size is 0, this is just padding, which is for certain
            # done in the metadata messages. Let the default block size handle rather
            # than any specific heuristic to skip.
            if msg_hdr.size:
                # For new packets, the message size isn't on the fixed size boundaries,
                # so we use header to figure out. For these, we need to include the
                # CTM header but not FCS, in addition to the size.

                # As of 2620002P, this is a special value used to indicate that the segment
                # number/count bytes are used to indicate total size in bytes.
                if msg_hdr.size == 65535:
                    msg_bytes = (msg_hdr.segments << 16 | msg_hdr.segment_num
                                 + CTM_HEADER_SIZE)
                elif msg_hdr.type in (29, 31):
                    msg_bytes = CTM_HEADER_SIZE + 2 * msg_hdr.size

                log.debug('Total message size: %d', msg_bytes)

                # Try to handle the message. If we don't handle it, skipping
                # past it is handled at the end anyway.
                decoder = f'_decode_msg{msg_hdr.type:d}'
                if hasattr(self, decoder):
                    getattr(self, decoder)(msg_hdr)
                else:
                    log.warning('Unknown message: %d', msg_hdr.type)

            # Jump to the start of the next message. This depends on whether
            # the message was legacy with fixed block size or not.
            self._buffer.jump_to(msg_start, msg_bytes)

        # Check if we have any message segments still in the buffer
        if self._msg_buf:
            log.warning('Remaining buffered message segments for message type(s): %s',
                        ' '.join(f'{typ} ({len(rem)})' for typ, rem in self._msg_buf.items()))

        del self._msg_buf

    # TODO skipping all _decode_msg* from metpy L270-L647 (ana. to pyart L146-173)

    # TODO maybe? metpy _buffer_segment L649
    # TODO maybe? metpy _add_sweep L667
    # TODO maybe? metpy _check_size L680

    def close(self):
        """Close the file."""
        self._fobj.close()

    # TODO consider from pyart: location, scan_info, get_vcp_pattern, get_nrays, get_range
    # get_times, get_azimuth_angles, get_elevation_angles, get_target_angles,
    # get_nyquist_vel, get_unambigous_range, get_data

    __del__ = close

    def __enter__(self):
        return self

    def __exit__(self, type, value, traceback):
        self.close()

    # TODO consider from rainbow/furuno: filename, version, type, datetime, first_dimension,
    # header
