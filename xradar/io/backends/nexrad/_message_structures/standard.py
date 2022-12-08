# Copyright (c) 2022, openradar developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Contains parsed specs for standard NEXRAD messages.

TODO acknowledge pyart and metpy

The deails on these structures are documented in:
"Interface Control Document for the Achive II/User" RPG Build 12.0
Document Number 2620010E
and
"Interface Control Document for the RDA/RPG" Open Build 13.0
Document Number 2620002M
Tables and page number refer to those in the second document unless
otherwise noted.
"""
from collections import namedtuple

from ..utils import NamedStruct, scaler, angle, BitField, az_rate


# Figure 1 in Interface Control Document for the Archive II/User
# page 7-2
volume_header_fmt = NamedStruct(
    (
        ('tape', '9s'),
        ('extension', '3s'),
        ('date', 'I'),
        ('time', 'I'),
        ('icao', '4s')
    ),
    '>',
    'VOLUME_HEADER'
)


# Table II Message Header Data
# page 3-7
message_header_fmt = NamedStruct(
    (
        ('size', 'H'),  # size of data, no including header
        ('channels', 'B'),
        ('type', 'B'),
        ('seq_id', 'H'),
        ('date', 'H'),
        ('ms', 'I'),
        ('segments', 'H'),
        ('segment_num', 'H'),
    ),
    '>',
    'MSG_HEADER'
)


# Table III Digital Radar Data (Message Type 1)
# pages 3-7 to
msg1_fmt = NamedStruct(
    (
        ('collect_ms', 'I'),  # 0-3
        ('collect_date', 'H'),  # 4-5
        ('unambig_range', 'h', scaler(100)),  # 6-7  TODO metpy has 'H'?
        ('azimuth_angle', 'H', angle),  # 8-9
        ('azimuth_number', 'H'),  # 10-11
        ('radial_status', 'H', remap_status),  # 12-13
        ('elevation_angle', 'H', angle),  # 14-15
        ('elevation_number', 'H'),  # 16-17
        ('sur_range_first', 'H'),  # 18-19  TODO metpy has 'h'?
        ('doppler_range_first', 'H'),  # 20-21  TODO metpy has 'h'?
        ('sur_range_step', 'H'),  # 22-23
        ('doppler_range_step', 'H'),  # 24-25
        ('sur_nbins', 'H'),  # 26-27
        ('doppler_nbins', 'H'),  # 28-29
        ('cut_sector_num', 'H'),  # 30-31
        ('calib_const', 'f'),  # 32-35
        ('sur_pointer', 'H'),  # 36-37
        ('vel_pointer', 'H'),  # 38-39
        ('width_pointer', 'H'),  # 40-41
        ('doppler_resolution', 'H', BitField(None, 0.5, 1.0)),  # 42-43
        ('vcp', 'H'),   # 44-45
        (None, '14x'),  # 46-59
        ('nyquist_vel', 'h', scaler(0.01)),  # 60-61  TODO metpy has 'H'?
        ('atmos_attenuation', 'h'),  # 62-63  TODO metpy has 'H'?
        ('threshold', 'h', scaler(100)),  # 64-65  TODO metpy has 'H'?; check scale factor in general (is same as unambig_range)?
        ('spot_blank_status', 'H', BitField('Radial', 'Elevation', 'Volume')),  # 66-67  TODO metpy has 'B'?
        (None, '32x'),  # 68-99
        # 100+  reflectivity, velocity and/or spectral width data, 'B'
    ),
    '>',
    'MSG_1'
)
msg1_data_header = namedtuple(
    'MSG_1_DATA_HEADER',
    'name first_gate gate_width num_gates scale offset'
)

# Table XI Volume Coverage Pattern Data (Message Type 5 & 7)
# pages 3-51 to 3-54
msg5_fmt = NamedStruct(
    (
        ('msg_size', 'H'),
        ('pattern_type', 'H'),
        ('pattern_number', 'H'),
        ('num_cuts', 'H'),
        ('vcp_version', 'B'),
        ('clutter_map_group', 'B'),
        ('doppler_vel_res', 'B', BitField(None, 0.5, 1.0)),
        ('pulse_width', 'B', BitField('None', 'Short', 'Long')),
        (None, '4x'),
        ('vcp_sequencing', 'H'),
        ('vcp_supplemental_info', 'H'),
        (None, '2x'),
        ('els', None)
    ),
    '>',
    'MSG_5'
)
msg5_elevation_fmt = NamedStruct(
    (
        ('elevation_angle', 'H', angle),
        ('channel_config', 'B', Enum('Constant Phase', 'Random Phase', 'SZ2 Phase')),
        (
            'waveform',
            'B',
            Enum(
                'None',
                'Contiguous Surveillance',
                'Contig. Doppler with Ambiguity Res.',
                'Contig. Doppler without Ambiguity Res.',
                'Batch',
                'Staggered Pulse Pair'
            )
        ),
        (
            'super_resolution',
            'B',
            BitField(
                '0.5 azimuth and 0.25km range res.',
                'Doppler to 300km',
                'Dual Polarization Control',
                'Dual Polarization to 300km'
            )
        ),
        ('prf_number', 'B'),
        ('prf_pulse_count', 'H'),
        ('azimuth_rate', 'H', az_rate),  # TODO metpy has 'h'?
        ('ref_thresh', 'h', scaler(0.125)),
        ('vel_thresh', 'h', scaler(0.125)),
        ('sw_thresh', 'h', scaler(0.125)),
        ('zdr_thres', 'h', scaler(0.125)),
        ('phi_thres', 'h', scaler(0.125)),
        ('rho_thres', 'h', scaler(0.125)),
        ('edge_angle_1', 'H', angle),
        ('dop_prf_num_1', 'H'),
        ('dop_prf_pulse_count_1', 'H'),
        ('spare_1', 'H'),
        ('edge_angle_2', 'H', angle),
        ('dop_prf_num_2', 'H'),
        ('dop_prf_pulse_count_2', 'H'),
        ('spare_2', 'H'),
        ('edge_angle_3', 'H', angle),
        ('dop_prf_num_3', 'H'),
        ('dop_prf_pulse_count_3', 'H'),
        ('spare_3', 'H')
    ),
    '>',
    'MSG_5_ELEV'
)


# Table XVII Digital Radar Generic Format Blocks (Message Type 31)
# pages 3-87 to 3-89
msg31_data_header_fmt = NamedStruct(
    (
        ('id', '4s'),  # 0-3
        ('collect_ms', 'L'),  # 4-7
        ('collect_date', 'H'),  # 8-9
        ('azimuth_number', 'H'),  # 10-11
        ('azimuth_angle', 'f'),  # 12-15
        ('compress_flag', 'B'),  # 16
        (None, 'x'),  # 17
        ('radial_length', 'H'),  # 18-19
        ('azimuth_spacing', 'B', Enum(0, 0.5, 1.0)),  # 20
        ('radial_spacing', 'B', remap_status),  # 21
        ('elevation_number', 'B'),  # 22
        ('cut_sector', 'B'),  # 23
        ('elevation_angle', 'f'),  # 24-27
        ('radial_blanking', 'B', BitField('Radial', 'Elevation', 'Volume')),  # 28
        ('azimuth_mode', 'b', scaler(0.01)),  # TODO metpy has 'B'?  # 29
        ('block_count', 'H')  # 30-31
        # skipping block_pointer_* from PyART (32-67); handled in _decode_msg31
    ),
    '>',
    'MSG_31'
)
# Table XVII-E Data Block (Volume Data Constant Type)
# page 3-92
msg31_volume_constant_fmt = NamedStruct(
    (
        ('block_type', 's'),
        ('data_name', '3s'),
        ('lrtup', 'H'),
        ('version_major', 'B'),
        ('version_minor', 'B'),
        ('lat', 'f'),
        ('lon', 'f'),
        ('height', 'h'),
        ('feedhorn_height', 'H'),
        ('refl_calib', 'f'),
        ('power_h', 'f'),
        ('power_v', 'f'),
        ('diff_refl_calib', 'f'),
        ('init_phase', 'f'),
        ('vcp', 'H'),
        ('processing_status', 'H', BitField('RxR Noise', 'CBT'))
    ),
    '>',
    'VOLUME_DATA_BLOCK'
)
# Table XVII-F Data Block (Elevation Data Constant Type)
# page 3-93
msg31_elevation_constant_fmt = NamedStruct(
    (
        ('block_type', 's'),
        ('data_name', '3s'),
        ('lrtup', 'H'),
        ('atmos', 'h', scaler(0.001)),
        ('refl_calib', 'f')
    ),
    '>',
    'ELEVATION_DATA_BLOCK'
)
# Table XVII-H Data Block (Radial Data Constant Type)
# pages 3-93
radial_constant_fmt_v1 = NamedStruct(
    (
        ('block_type', 's'),
        ('data_name', '3s'),
        ('lrtup', 'H'),
        ('unambig_range', 'h', scaler(100)),  # TODO metpy has 'H'?
        ('noise_h', 'f'),
        ('noise_v', 'f'),
        ('nyquist_vel', 'h', scaler(0.01)),  # TODO metpy has 'H'?
        (None, '2x')
    ),
    '>',
    'RADIAL_DATA_BLOCK'
)
radial_constant_fmt_v2 = NamedStruct(
    (
        ('block_type', 's'),
        ('data_name', '3s'),
        ('lrtup', 'H'),
        ('unambig_range', 'H', scaler(100)),
        ('noise_h', 'f'),
        ('noise_v', 'f'),
        ('nyquist_vel', 'H', scaler(0.01)),
        (None, '2x'),
        ('refl_calib_h', 'f'),
        ('refl_calib_v', 'f')
    ),
    '>',
    'RADIAL_DATA_BLOCK_V2'
)
# Table XVII-B Data Block (Descriptor of Generic Data Moment Type)
# pages 3-90 and 3-91
data_block_fmt = NamedStruct(
    (
        ('block_type', 's'),
        ('data_name', '3s'),  # VEL, REF, SW, RHO, PHI, ZDR
        ('reserved', 'L'),
        ('ngates', 'H'),
        ('first_gate', 'h'),  # TODO metpy has 'H'?
        ('gate_spacing', 'h'),  # TODO metpy has 'H'?
        ('thresh', 'h', scaler(0.1)),  # TODO metpy has 'H'?
        ('snr_thres', 'h', scaler(0.1)),
        ('flags', 'B', BitField('Azimuths', 'Gates')),
        ('word_size', 'B'),
        ('scale', 'f'),
        ('offset', 'f')
    ),
    '>',
    'GENERIC_DATA_BLOCK'
)

Radial = namedtuple(
    'Radial',
    'header volume_consts elevation_consts radial_consts moments'
)
