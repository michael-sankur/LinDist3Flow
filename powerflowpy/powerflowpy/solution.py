# Elaine Laguerta (github: @elaguerta)
# LBNL GIG
# File created: 28 August 2020
# Implement FBS to solve Power Flow for a radial distribution network.

from typing import Iterable, List, Dict
from . utils import mask_phases
from . network import *

class Solution:

    def __init__(self, network: Network, tol: float = -1, max_iter: int = -1) -> None:
        self.iterations = -1  # stores number of iterations of FBS until convergence
        self.Vtest = np.zeros(3, dtype='complex')
        self.Vref = network.Vbase * np.ones(3, dtype='complex')
        self.solved_nodes = dict()
        self.solved_lines = dict()
        self.tolerance = -1  # stores the tolerance
        self.diff = -1  # stores the final value of Vtest - Vref at convergence

        """ Set up voltages and currents for all nodes """
        for node in network.get_nodes():
            node_dict = dict()
            self.solved_nodes[node.name] = node_dict
            # initialize a zeroed out array for each solution var
            node_dict['V'] = network.Vbase * np.ones(3, dtype='complex')
            node_dict['Inode'] = np.zeros(3, dtype='complex')
            node_dict['S'] =
        for line in network.get_lines():
            line_dict = dict()
            self.solved_lines[line.name] = line_dict
            line_dict['I'] = np.zeros(3, dtype='complex')

    def update_voltage(network: Network, source_node: Node, target_node: Node, direction: str) -> None:
        """
        updates voltage at target_node based on source_node according to:
        target_node_dict['V'] = source_node_dict['V'] - (source,target).FZpu * (source,target).I
        """
        source_node_dict = self.solved_nodes[source_node.name]
        target_node_dict = self.solved_nodes[target_node.name]
        line_key = (source_node.name, target_node.name)
        source_V = source_node_dict['V']
        target_V = target_node_dict['V']
        FZpu = network.lines[line_key].FZpu
        I = self.solved_lines[line_key]['I']
        # if forward, subtract Z*I, otherwise add Z*I
        sign = direction == 'forward' ? - 1: 1

        # target node voltage = source node voltage +/- current(target_node, source_node)
        new_target_V = source_V + sign * np.matmul(FZpu, I)
        # zero out voltages for not existent phases at target node
        # ELAINE: move this out or toggle for forward/backward
        target_node_dict['V'] = mask_phases(new_target_V, target_node.phases)
        return None

    def update_current(network: Network, line_in: Line) -> None:
        downstr_node_name = line_in.key[1]
        solved_line_dict = self.solved_lines[line_in.key]
        downstr_node_dict = self.solved_nodes[ downstr_node_name ]
        downstr_node_phases = network.nodes[ downstr_node_name ].phases
        line_I = solved_line_dict['I']
        line_s = solved_line_dict['s']
        downstr_node_V = downstr_node_dict['V']

        new_line_I = np.conj(np.divide(line_s, downstr_node_V))
        # TODO: confirm that np.divide is the same as matlab right divide './'
        new_line_I = mask_phases(new_line_I, downstr_node_phases)

    def update_voltage_dependent_load(network: Network) -> None:
        """
        update s at network loads
        """
        #TODO: write this!
        # s = spu.*(aPQ + aI.*(abs(V)) + aZ.*(abs(V)).^2) - 1j * cappu + wpu
        pass

    def __str__(self):
        return '\n'.join(
            [
                f'itertations to convergence: {self.iterations}',
                f'tolerance at convergence: {self.tolerance}',
                f'solution: \n {self.solved_nodes}'
            ]
        )