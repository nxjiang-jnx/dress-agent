#!/usr/bin/env python3
"""Winding number of query points against a mesh (igl), for hidden_masks.py.

    python winding.py in.npz out.npy      # in.npz holds V, F, Q
"""
import sys

import igl
import numpy as np

d = np.load(sys.argv[1])
w = igl.fast_winding_number(d["V"].astype(np.float64), d["F"].astype(np.int64), d["Q"].astype(np.float64))
np.save(sys.argv[2], w.astype(np.float32))
