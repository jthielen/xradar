# Copyright (c) 2022, openradar developers.
# Distributed under the MIT License. See LICENSE for more info.

"""

NEXRAD Level II data
====================

Reads data from NEXRAD Level II files and contained messages.

...TODO...

This implementation uses code from MetPy (Copyright (c) 2008-2022, MetPy Developers) and PyART (Copyright (c) 2013, UChicago Argonne, LLC) ...TODO licenses...

Example::

    import xradar as xd
    dtree = xd.io.open_nexrad_level2_datatree(filename)

.. autosummary::
   :nosignatures:
   :toctree: generated/

   {}

"""

__all__ = [
    "NEXRADLevel2BackendEntrypoint",
    "open_nexrad_level2_datatree",
]