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

from ..utils import NamedStruct, scaler, angle, BitField


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

### TODO from metpy below, align with pyart ###
msg5_fmt = NamedStruct([('size_hw', 'H'), ('pattern_type', 'H'),
                        ('num', 'H'), ('num_el_cuts', 'H'),
                        ('vcp_version', 'B'), ('clutter_map_group', 'B'),
                        ('dop_res', 'B', BitField(None, 0.5, 1.0)),
                        ('pulse_width', 'B', BitField('None', 'Short', 'Long')),
                        (None, '4x'), ('vcp_sequencing', 'H'),
                        ('vcp_supplemental_info', 'H'), (None, '2x'),
                        ('els', None)], '>', 'VCPFmt')

msg5_elevation_fmt = NamedStruct([('el_angle', 'H', angle),
                            ('channel_config', 'B', Enum('Constant Phase', 'Random Phase',
                                                        'SZ2 Phase')),
                            ('waveform', 'B', Enum('None', 'Contiguous Surveillance',
                                                    'Contig. Doppler with Ambiguity Res.',
                                                    'Contig. Doppler without Ambiguity Res.',
                                                    'Batch', 'Staggered Pulse Pair')),
                            ('super_res', 'B', BitField('0.5 azimuth and 0.25km range res.',
                                                        'Doppler to 300km',
                                                        'Dual Polarization Control',
                                                        'Dual Polarization to 300km')),
                            ('surv_prf_num', 'B'), ('surv_pulse_count', 'H'),
                            ('az_rate', 'h', az_rate),
                            ('ref_thresh', 'h', scaler(0.125)),
                            ('vel_thresh', 'h', scaler(0.125)),
                            ('sw_thresh', 'h', scaler(0.125)),
                            ('zdr_thresh', 'h', scaler(0.125)),
                            ('phidp_thresh', 'h', scaler(0.125)),
                            ('rhohv_thresh', 'h', scaler(0.125)),
                            ('sector1_edge', 'H', angle),
                            ('sector1_doppler_prf_num', 'H'),
                            ('sector1_pulse_count', 'H'), ('supplemental_data', 'H'),
                            ('sector2_edge', 'H', angle),
                            ('sector2_doppler_prf_num', 'H'),
                            ('sector2_pulse_count', 'H'), ('ebc_angle', 'H', angle),
                            ('sector3_edge', 'H', angle),
                            ('sector3_doppler_prf_num', 'H'),
                            ('sector3_pulse_count', 'H'), (None, '2x')], '>', 'VCPEl')



msg31_data_header_fmt = NamedStruct([('stid', '4s'), ('time_ms', 'L'),
                                    ('date', 'H'), ('az_num', 'H'),
                                    ('az_angle', 'f'), ('compression', 'B'),
                                    (None, 'x'), ('rad_length', 'H'),
                                    ('az_spacing', 'B', Enum(0, 0.5, 1.0)),
                                    ('rad_status', 'B', remap_status),
                                    ('el_num', 'B'), ('sector_num', 'B'),
                                    ('el_angle', 'f'),
                                    ('spot_blanking', 'B', BitField('Radial', 'Elevation',
                                                                    'Volume')),
                                    ('az_index_mode', 'B', scaler(0.01)),
                                    ('num_data_blks', 'H')], '>', 'Msg31DataHdr')

msg31_volume_constant_fmt = NamedStruct([('type', 's'), ('name', '3s'),
                                    ('size', 'H'), ('major', 'B'),
                                    ('minor', 'B'), ('lat', 'f'), ('lon', 'f'),
                                    ('site_amsl', 'h'), ('feedhorn_agl', 'H'),
                                    ('calib_dbz', 'f'), ('txpower_h', 'f'),
                                    ('txpower_v', 'f'), ('sys_zdr', 'f'),
                                    ('phidp0', 'f'), ('vcp', 'H'),
                                    ('processing_status', 'H', BitField('RxR Noise',
                                                                        'CBT'))],
                                    '>', 'VolConsts')

msg31_elevation_constant_fmt = NamedStruct([('type', 's'), ('name', '3s'),
                                    ('size', 'H'), ('atmos_atten', 'h', scaler(0.001)),
                                    ('calib_dbz0', 'f')], '>', 'ElConsts')

radial_constant_fmt_v1 = NamedStruct([('type', 's'), ('name', '3s'), ('size', 'H'),
                                ('unamb_range', 'H', scaler(0.1)),
                                ('noise_h', 'f'), ('noise_v', 'f'),
                                ('nyq_vel', 'H', scaler(0.01)),
                                (None, '2x')], '>', 'RadConstsV1')
radial_constant_fmt_v2 = NamedStruct([('type', 's'), ('name', '3s'), ('size', 'H'),
                                ('unamb_range', 'H', scaler(0.1)),
                                ('noise_h', 'f'), ('noise_v', 'f'),
                                ('nyq_vel', 'H', scaler(0.01)),
                                (None, '2x'), ('calib_dbz0_h', 'f'),
                                ('calib_dbz0_v', 'f')], '>', 'RadConstsV2')

data_block_fmt = NamedStruct([('type', 's'), ('name', '3s'),
                                ('reserved', 'L'), ('num_gates', 'H'),
                                ('first_gate', 'H', scaler(0.001)),
                                ('gate_width', 'H', scaler(0.001)),
                                ('tover', 'H', scaler(0.1)),
                                ('snr_thresh', 'h', scaler(0.1)),
                                ('recombined', 'B', BitField('Azimuths', 'Gates')),
                                ('data_size', 'B'),
                                ('scale', 'f'), ('offset', 'f')], '>', 'DataBlockHdr')

Radial = namedtuple('Radial', 'header vol_consts elev_consts radial_consts moments')
