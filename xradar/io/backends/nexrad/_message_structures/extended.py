# Copyright (c) 2022, openradar developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Contains parsed specs for additional NEXRAD messages.

TODO acknowledge metpy
"""
from ..utils import NamedStruct, BitField, scaler, version, Array


msg2_fmt = NamedStruct(
    (
        (
            'rda_status',
            'H',
            BitField(
                'None', 'Start-Up', 'Standby', 'Restart', 'Operate', 'Spare', 'Off-line Operate'
            )
        ),
        (
            'op_status',
            'H',
            BitField(
                'Disabled',
                'On-Line',
                'Maintenance Action Required',
                'Maintenance Action Mandatory',
                'Commanded Shut Down',
                'Inoperable',
                'Automatic Calibration'
            )
        ),
        ('control_status', 'H', BitField('None', 'Local Only', 'RPG (Remote) Only', 'Either')),
        (
            'aux_power_gen_state',
            'H',
            BitField(
                'Switch to Aux Power',
                'Utility PWR Available',
                'Generator On',
                'Transfer Switch Manual',
                'Commanded Switchover'
            )
        ),
        ('avg_tx_pwr', 'H'),
        ('ref_calib_cor', 'h', scaler(0.01)),
        ('data_transmission_enabled', 'H', BitField('None', 'None', 'Reflectivity', 'Velocity', 'Width')),
        ('vcp_num', 'h'),
        ('rda_control_auth', 'H', BitField('No Action', 'Local Control Requested', 'Remote Control Enabled')),
        ('rda_build', 'H', version),
        ('op_mode', 'H', BitField('None', 'Test', 'Operational', 'Maintenance')),
        ('super_res_status', 'H', BitField('None', 'Enabled', 'Disabled')),
        ('cmd_status', 'H', Bits(6)),
        ('avset_status', 'H', BitField('None', 'Enabled', 'Disabled')),
        ('rda_alarm_status', 'H', BitField('No Alarms', 'Tower/Utilities', 'Pedestal', 'Transmitter', 'Receiver', 'RDA Control', 'Communication', 'Signal Processor')),
        ('command_acknowledge', 'H', BitField('Remote VCP Received', 'Clutter Bypass map received', 'Redundant Chan Ctrl Cmd received')),
        ('channel_control_status', 'H'),
        ('spot_blanking', 'H', BitField('Enabled', 'Disabled')),
        ('bypass_map_gen_date', 'H'),
        ('bypass_map_gen_time', 'H'),
        ('clutter_filter_map_gen_date', 'H'),
        ('clutter_filter_map_gen_time', 'H'),
        ('refv_calib_cor', 'h', scaler(0.01)),
        ('transition_pwr_src_state', 'H', BitField('Off', 'OK')),
        ('RMS_control_status', 'H', BitField('RMS in control', 'RDA in control')),
        # See Table IV-A for definition of alarms
        (None, '2x'),
        ('alarms', '28s', Array('>14H'))
    ),
    '>',
    'MSG_2'
)
msg2_additional_fmt = NamedStruct(
    (
        ('sig_proc_options', 'H', BitField('CMD RhoHV Test')),
        (None, '36x'),
        ('status_version', 'H')
    ),
    '>',
    'MSG_2_ADDITIONAL'
)

msg15_code_map = {0: 'Bypass Filter', 1: 'Bypass map in Control', 2: 'Force Filter'}
