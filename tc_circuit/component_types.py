from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, ClassVar, cast

from save_monger import ComponentKind, ParseComponent, Point
from tc_circuit.component_info import ComponentInfo, COMPONENT_INFOS


@dataclass
class TCComponent:
    pos: Point
    rotation: int

    info: ClassVar[ComponentInfo]
    registry: ClassVar[dict[ComponentKind, Callable[[ParseComponent], TCComponent]]] = {}

    def __init_subclass__(cls, **kwargs):
        if 'kind' in kwargs:
            cls.info = COMPONENT_INFOS[kind := kwargs.pop('kind')]
            if kind in cls.registry:
                raise TypeError(f"ComponentKind {kind} already registered to type {cls.registry[kind]}"
                                f" (can't register {cls})")
            cls.registry[kind] = cls.build
        super().__init_subclass__(**kwargs)

    @classmethod
    def build(cls, parse_component: ParseComponent, **kwargs):
        return cls(
            pos=parse_component.position,
            rotation=parse_component.rotation,
            **kwargs  # type: ignore
        )


@dataclass
class LevelInputComponent(TCComponent):
    pass


@dataclass
class LevelOutputComponent(TCComponent):
    pass


class LevelInput2Pin(LevelInputComponent, kind=ComponentKind.LevelInput2Pin):
    pass


class LevelOutput1(LevelOutputComponent, kind=ComponentKind.LevelOutput1):
    pass


class LevelOutputArch(TCComponent, kind=ComponentKind.LevelOutputArch):
    pass


class LevelInputArch(TCComponent, kind=ComponentKind.LevelInputArch):
    pass


@dataclass
class LevelInput8(LevelInputComponent, kind=ComponentKind.LevelInput8):
    pass


@dataclass
class LevelOutput8(LevelOutputComponent, kind=ComponentKind.LevelOutput8):
    pass


@dataclass
class BitLogic(TCComponent):
    pos: Point

    op: ClassVar[str | None] = None


class Nand(BitLogic, kind=ComponentKind.Nand):
    op = "~({a} & {b})"


class Or(BitLogic, kind=ComponentKind.Or):
    op = "{a} | {b}"


class Not(BitLogic, kind=ComponentKind.Not):
    op = "~{a}"


class LevelScreen(TCComponent, kind=ComponentKind.LevelScreen):
    pass


class Program(TCComponent, kind=ComponentKind.Program):
    pass


class Splitter(TCComponent):
    pass


class Splitter8(Splitter, kind=ComponentKind.Splitter8):
    pass


class Maker(TCComponent):
    pass


class Maker8(Maker, kind=ComponentKind.Maker8):
    pass


class DelayLine(TCComponent):
    pass


class VirtualDelayLine(TCComponent):
    pass


class DelayLine1(DelayLine, kind=ComponentKind.DelayLine1):
    pass


class VirtualDelayLine1(VirtualDelayLine, kind=ComponentKind.VirtualDelayLine1):
    pass


class Constant(TCComponent):
    value: int
    width: int


class Off(Constant, kind=ComponentKind.Off):
    value = 0
    width = 1


class On(Constant, kind=ComponentKind.On):
    value = 1
    width = 1
