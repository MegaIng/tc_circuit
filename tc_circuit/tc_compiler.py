from __future__ import annotations

from graphlib import TopologicalSorter
from inspect import get_annotations, signature
from typing import Callable, Any, Iterable, ClassVar

from tc_circuit.component_info import PinInfo
from tc_circuit.component_types import TCComponent
from tc_circuit import component_types
from tc_circuit.tc_circuit import TCCircuit, WireCluster


class TCCompiler:
    circuit: TCCircuit | None = None
    _registry: ClassVar[list[tuple[type[TCComponent], Callable[[TCCompiler, TCComponent], Any]]]]

    def _compile_all(self, circuit: TCCircuit):
        assert self.circuit is None
        self.circuit = circuit
        for cid in TopologicalSorter(circuit.dependency_graph).static_order():
            component = circuit.components[cid]
            self._compile(component)
        self.circuit = None

    def _compile(self, component: TCComponent) -> None:
        for typ, func in self._registry:
            if isinstance(component, typ):
                func(self, component)
                return
        raise TypeError(f"Component {component} unhandled by {type(self)}")

    def __init_subclass__(cls, **kwargs):
        cls._registry = []
        for func in cls.__dict__.values():
            if hasattr(func, 'targets'):
                for target in func.targets:
                    assert issubclass(target, TCComponent), (func, target)
                    cls._registry.append((target, func))
            elif callable(func):
                sig = signature(func)
                if len(sig.parameters) != 2:
                    continue
                param = list(sig.parameters.values())[1]
                if isinstance(param.annotation, str):
                    typ = getattr(component_types, param.annotation, None)
                else:
                    typ = param.annotation
                if isinstance(typ, type) and issubclass(typ, TCComponent):
                    cls._registry.append((typ, func))

        super().__init_subclass__(**kwargs)

    def _get_wire(self, component: TCComponent, pin: PinInfo) -> WireCluster | None:
        pos = component.pos + pin.pos.rotate(component.rotation)
        return self.circuit.clusters[1].get(pos, None)

    def _get_inputs(self, component: TCComponent) -> Iterable[tuple[int, PinInfo, WireCluster | None]]:
        for i, pin in enumerate(component.info.pins):
            if pin.kind == "input":
                yield i, pin, self._get_wire(component, pin)

    def _get_outputs(self, component: TCComponent) -> Iterable[tuple[int, PinInfo, WireCluster | None]]:
        for i, pin in enumerate(component.info.pins):
            if pin.kind in ("output", "output_tristate"):
                yield i, pin, self._get_wire(component, pin)
