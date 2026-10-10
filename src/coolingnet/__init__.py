"""coolingnet: optimization of cooling water system hydraulic debottlenecking.

Python reimplementation of Souza, Levy & Costa, Applied Thermal Engineering 128
(2018) 1531-1542, originally developed in GAMS (SBB/CONOPT) with R post-processing.
"""

from coolingnet.config import CaseStudy, dump_case, load_case, paper_case
from coolingnet.network import Network, build_network

__version__ = "0.1.0"

__all__ = ["CaseStudy", "Network", "__version__", "build_network", "dump_case", "load_case", "paper_case"]
