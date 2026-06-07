"""
damask/phase_config.py
Convert one sampled parameter row into a DAMASK phase dictionary.

This module centralizes:
- mapping sample column names to DAMASK YAML keys,
- unit conversion from user-facing CSV units (GPa/MPa) to SI (Pa),
- assembly of vector-valued plasticity parameters,
- construction of h_sl-sl through interaction_matrix.build_h_sl_sl().

A complete material configuration file contains 'phase', 'material', and
'homogenization' sections in DAMASK.
"""

from dataclasses import dataclass
from copy import deepcopy

from damask_utils.interaction_matrix import build_h_sl_sl


def phase_yaml_base() -> dict:
    return {
        'lattice': 'cI',
        'mechanical': {
            'output': ['F', 'P', 'F_e', 'F_p', 'L_p', 'O'],
            'elastic': {
                'type': 'Hooke',
                'C_11': 233.3e9,
                'C_12': 135.5e9,
                'C_44': 128.0e9,
            },
            'plastic': {
                'type': 'phenopowerlaw',
                'N_sl': [12, 12],
                'n_sl': 20.0,
                'a_sl': 2.25,
                'h_0_sl-sl': 1.0e9,
                'xi_0_sl': [95e6, 96e6],
                'xi_inf_sl': [222e6, 412e6],
                'dot_gamma_0_sl': 0.001,
                'h_sl-sl': [1.0] * 24,
            },
        },
    }


@dataclass(frozen=True)
class PhaseConfig:
    phase_name: str
    prefix: str
    sample: object

    def _value(self, key: str) -> float:
        return float(self.sample[f'{self.prefix}_{key}'])

    def _gpa_to_pa(self, key: str) -> float:
        return self._value(key) * 1e9

    def _mpa_to_pa(self, key: str) -> float:
        return self._value(key) * 1e6

    def to_yaml_dict(self) -> dict:
        data = deepcopy(phase_yaml_base())

        data['mechanical']['elastic']['C_11'] = self._mpa_to_pa('C11')
        data['mechanical']['elastic']['C_12'] = self._mpa_to_pa('C12')
        data['mechanical']['elastic']['C_44'] = self._mpa_to_pa('C44')

        data['mechanical']['plastic']['n_sl'] = self._value('n_sl')
        data['mechanical']['plastic']['a_sl'] = self._value('a_sl')
        
        dot_gamma = self._value('dot_gamma_0_sl')
        data['mechanical']['plastic']['dot_gamma_0_sl'] = [dot_gamma, dot_gamma]
        
        data['mechanical']['plastic']['h_0_sl-sl'] = self._mpa_to_pa('h0_sl')
        
        data['mechanical']['plastic']['xi_0_sl'] = [
            self._mpa_to_pa('xi_0_sl_1'),
            self._mpa_to_pa('xi_0_sl_2'),
        ]
        data['mechanical']['plastic']['xi_inf_sl'] = [
            self._mpa_to_pa('xi_inf_sl_1'),
            self._mpa_to_pa('xi_inf_sl_2'),
        ]
        data['mechanical']['plastic']['h_sl-sl'] = build_h_sl_sl(1.0, 1.4)  # TODO: hardcoded for now, should be added as fixed parameters within material parameters
            # self._value('h_sl_sl_aa'),
            # self._value('h_sl_sl_ab'),
        return data
