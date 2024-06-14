from __future__ import annotations

import json
import sys
from argparse import ArgumentParser, FileType
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from tc_circuit.component_types import TCComponent, LevelInputComponent, LevelOutputComponent, Constant
from tc_circuit.tc_circuit import TCCircuit, WireCluster
from tc_circuit.tc_compiler import TCCompiler


@dataclass
class TC2JSON(TCCompiler):
    condense_io: bool = False
    port_as_dict: bool = False
    numeric_names: bool = False

    wires: list[dict] = None
    nodes: dict[str, Any] = None
    cluster_sources: dict[WireCluster, tuple[dict, int]] = None

    def compile(self, circuit: TCCircuit):
        self.wires = []
        self.nodes = {}
        self.cluster_sources = {}
        if self.condense_io:
            self.nodes['in' if not self.numeric_names else '0'] = {
                'type': 'Input',
                'components': []
            }
            self.nodes['out' if not self.numeric_names else '1'] = {
                'type': 'Output',
                'components': []
            }
        self._compile_all(circuit)
        return {
            'wires': self.wires,
            'nodes': self.nodes,
        }

    def _register_source(self, cluster: WireCluster, name: str, index: int, width: int):
        assert cluster not in self.cluster_sources, "Bus style wires not supported"
        port = {'component': name, 'index': index} if self.port_as_dict else [name, index]
        self.cluster_sources[cluster] = port, width

    def _connect(self, cluster: WireCluster, name: str, index: int):
        assert cluster in self.cluster_sources, "Missing source for wire cluster"
        src, w = self.cluster_sources[cluster]
        target = {'component': name, 'index': index} if self.port_as_dict else [name, index]
        self.wires.append({'from': src, 'to': target, 'width': w})

    def _new_node(self, prefix: str, data: dict[str, Any]) -> str:
        name = str(len(self.nodes)) if self.numeric_names else f'{prefix}_{len(self.nodes)}'
        self.nodes[name] = data
        return name

    def _compile_input(self, comp: LevelInputComponent):
        if self.condense_io:
            name = 'in' if not self.numeric_names else '0'
        else:
            name = self._new_node('in', {'type': 'Input', 'components': []})
        () = self._get_inputs(comp)
        for _, pin, cluster in self._get_outputs(comp):
            index = len(self.nodes[name]['components'])
            self.nodes[name]['components'].append(pin.width)
            self._register_source(cluster, name, index, pin.width)

    def _compile_output(self, comp: LevelOutputComponent):
        if self.condense_io:
            name = 'out' if not self.numeric_names else '1'
        else:
            name = self._new_node('out', {'type': 'Output', 'components': []})
        for _, pin, cluster in self._get_inputs(comp):
            index = len(self.nodes[name]['components'])
            self.nodes[name]['components'].append(pin.width)
            self._connect(cluster, name, index)
        () = self._get_outputs(comp)

    def _compile_constant(self, comp: Constant):
        name = self._new_node('Constant', {'type': 'Constant', 'width': comp.width, 'value': comp.value})
        for i, pin, cluster in self._get_outputs(comp):
            self._register_source(cluster, name, i, pin.width)
        () = self._get_inputs(comp)

    def _compile_generic(self, comp: TCComponent):
        name = self._new_node(comp.__class__.__name__, {'type': comp.__class__.__name__})
        for i, pin, cluster in self._get_outputs(comp):
            self._register_source(cluster, name, i, pin.width)
        for i, pin, cluster in self._get_inputs(comp):
            self._connect(cluster, name, i)


def main(args: list[str] = None):
    if args is None:
        args = sys.argv[1:]
    argparse = ArgumentParser()
    argparse.add_argument('--condense-io', action='store_true')
    argparse.add_argument('--port-as-dict', action='store_true')
    argparse.add_argument('--numeric-names', action='store_true')
    argparse.add_argument('-o', '--out', type=FileType('w'), default=sys.stdout)
    argparse.add_argument('circuit', type=Path)
    args = argparse.parse_args(args)
    comp = TC2JSON(condense_io=args.condense_io, port_as_dict=args.port_as_dict, numeric_names=args.numeric_names)
    data = args.circuit.read_bytes()
    circuit = TCCircuit.from_bytes(data)
    json_data = comp.compile(circuit)
    json.dump(json_data, args.out)


if __name__ == '__main__':
    main()
