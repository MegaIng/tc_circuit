from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from itertools import count
from typing import Literal

from typing_extensions import Self

from save_monger import ParseResult, ParseWire, Point
from tc_circuit.component_info import ComponentCategory
from tc_circuit.component_types import TCComponent


@dataclass(eq=False)
class WireCluster:
    segments: list[int]
    points: set[Point]
    sources: list[tuple[int, int]]
    targets: list[tuple[int, int]]
    bidis: list[tuple[int, int]]


@dataclass
class TCCircuit:
    components: dict[int, TCComponent]
    wires: dict[int, ParseWire]
    _index: defaultdict[Point, list[tuple[Literal['wire', 'comp'], int]]] = None
    _clusters: tuple[dict[WireCluster, int], dict[Point, WireCluster]] | None = None
    _dependency_graph: dict[int, set[int]] | None = None

    def clear_cache(self):
        self._clusters = None

    @property
    def clusters(self) -> tuple[dict[WireCluster, int], dict[Point, WireCluster]]:
        if self._clusters is None:
            point_to_cluster: dict[Point, WireCluster]
            self._clusters = (all_clusters := dict(), point_to_cluster := {})
            for wire_id, wire in self.wires.items():
                s_cluster = point_to_cluster.get(wire.start, None)
                e_cluster = point_to_cluster.get(wire.end, None)
                match (e_cluster, s_cluster):
                    case (None, None):
                        new_cluster = WireCluster([wire_id], {wire.start, wire.end}, [], [], [])
                        all_clusters[new_cluster] = len(all_clusters)
                        point_to_cluster[wire.start] = new_cluster
                        point_to_cluster[wire.end] = new_cluster
                    case (cluster, None) | (None, cluster):
                        point_to_cluster[wire.start] = cluster
                        point_to_cluster[wire.end] = cluster
                        cluster.segments.append(wire_id)
                        cluster.points.add(wire.start)
                        cluster.points.add(wire.end)
                    case (a, b) if a is b:
                        a.segments.append(wire_id)
                    case (a, b):
                        a.segments.extend(b.segments)
                        a.segments.append(wire_id)
                        a.points.update(b.points)
                        for p in b.points:
                            point_to_cluster[p] = a
                        del all_clusters[b]
                    case _:
                        assert False, "Unreachable"
            for component_id, component in self.components.items():
                for pin_id, pin in enumerate(component.info.pins):
                    global_pos = component.pos + pin.pos.rotate(component.rotation)
                    if global_pos in point_to_cluster:
                        match pin.kind:
                            case 'bidi':
                                point_to_cluster[global_pos].bidis.append((component_id, pin_id))
                            case 'output' | 'output_tristate':
                                point_to_cluster[global_pos].sources.append((component_id, pin_id))
                            case 'input':
                                point_to_cluster[global_pos].targets.append((component_id, pin_id))
                            case _:
                                raise ValueError(f"Unknown pin kind {pin.kind!r}")
        return self._clusters

    @property
    def dependency_graph(self) -> dict[int, set[int]]:
        if self._dependency_graph is None:
            self._dependency_graph = {i: set() for i in self.components}
            for cluster in self.clusters[0]:
                assert not cluster.bidis, ("Can't construct dependency graph when Custom Components with bidi pins are "
                                           "present.")
                srcs = {comp for comp, _ in cluster.sources}
                for tgt, _ in cluster.targets:
                    self._dependency_graph[tgt].update(srcs)
        return self._dependency_graph

    @property
    def index(self) -> defaultdict[Point, list[tuple[Literal['wire', 'comp'], int]]]:
        if self._index is None:
            self._index = defaultdict(list)
            for wid, wire in self.wires.items():
                for p in wire.path:
                    self._index[p].append(('wire', wid))
            for cid, comp in self.components.items():
                for p in comp.area():
                    self._index[p].append(('comp', cid))
        return self._index

    @classmethod
    def from_parse_state(cls, parse_state: ParseResult) -> Self:
        res = {}
        for c in parse_state.components:
            base = TCComponent.registry[c.kind](c)
            res[len(res) + 1] = base
            if base.info.category == ComponentCategory.has_virtual:
                assert base.info.counterpart is not None
                counterpart = TCComponent.registry[base.info.counterpart](c)
                res[len(res) + 1] = counterpart
            else:
                assert base.info.counterpart is None
        return cls(
            res,
            dict(zip(count(), parse_state.wires)),
        )

    @classmethod
    def from_bytes(cls, data: bytes) -> Self:
        return cls.from_parse_state(ParseResult.from_bytes(data))
