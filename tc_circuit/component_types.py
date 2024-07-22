from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass, fields
from typing import Callable, ClassVar, cast, Iterable

from save_monger import ComponentKind, ParseComponent, Point
from tc_circuit.component_info import ComponentInfo, COMPONENT_INFOS

cc_loader: ContextVar[Callable[[int], ComponentInfo]] = ContextVar('cc_loader', default=lambda cid: None)


@dataclass
class TCComponent:
    pos: Point
    rotation: int

    info: ClassVar[ComponentInfo]
    registry: ClassVar[dict[ComponentKind, Callable[[ParseComponent], TCComponent]]] = {}

    def __init_subclass__(cls, **kwargs):
        if 'kind' in kwargs:
            kind = kwargs.pop('kind')
            if kwargs.pop('retrieve_info', True):
                cls.info = COMPONENT_INFOS[kind]
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

    def area(self) -> Iterable[Point]:
        xx, xy, yx, yy = ((1, 0, 0, 1), (0, -1, 1, 0), (-1, 0, 0, -1), (0, 1, -1, 0))[self.rotation]
        for p in self.info.area:
            yield self.pos + Point(x=p.x * xx + p.y * xy, y=p.x * yx + p.y * yy)

    def describe(self) -> str:
        lines = [f"{type(self).__name__}"]
        for f in fields(self):
            if f.name not in {'pos', 'rotation'}:
                lines.append(f"{f.name}={getattr(self, f.name)}")
        return "\n".join(lines)

    def local_to_global_pos(self, pos: Point) -> Point:
        return self.pos + pos.rotate(self.rotation)


def _generate_larger(cls_or_pattern: type | str):
    def inner(cls):
        for n in (8, 16, 32, 64):
            name = pattern.format(n=n)

            class Larger(cls, kind=getattr(ComponentKind, name)):
                pass

            Larger.__name__ = name
            Larger.__module__ = cls.__module__
            Larger.__qualname__ = cls.__qualname__ + str(n)
            globals()[name] = Larger
        return cls

    if isinstance(cls_or_pattern, type):
        pattern = cls_or_pattern.__name__ + "{n}"
        return inner(cls_or_pattern)
    else:
        pattern = cls_or_pattern
        return inner


@_generate_larger
@dataclass
class Input(TCComponent):
    label: str

    @classmethod
    def build(cls, parse_component: ParseComponent, **kwargs):
        return super().build(parse_component, label=parse_component.custom_string or cls.__name__, **kwargs)


class Input1(Input, kind=ComponentKind.Input1):
    pass


@_generate_larger
@dataclass
class Output(TCComponent):
    label: str

    @classmethod
    def build(cls, parse_component: ParseComponent, **kwargs):
        return super().build(parse_component, label=parse_component.custom_string or cls.__name__, **kwargs)


class Output1(Output, kind=ComponentKind.Output1):
    pass


@_generate_larger("Output{n}z")
@dataclass
class OutputZ(TCComponent):
    label: str

    @classmethod
    def build(cls, parse_component: ParseComponent, **kwargs):
        return super().build(parse_component, label=parse_component.custom_string or cls.__name__, **kwargs)


class Output1z(TCComponent, kind=ComponentKind.Output1z):
    pass


@_generate_larger
@dataclass
class Bidirectional(TCComponent):
    label: str

    @classmethod
    def build(cls, parse_component: ParseComponent, **kwargs):
        return super().build(parse_component, label=parse_component.custom_string or cls.__name__, **kwargs)


class Bidirectional1(Bidirectional, kind=ComponentKind.Bidirectional1):
    pass


@dataclass
class LevelInputComponent(Input):
    pass


@dataclass
class LevelOutputComponent(Output):
    pass


class LevelInput1(LevelInputComponent, kind=ComponentKind.LevelInput1):
    pass


class LevelInput2Pin(LevelInputComponent, kind=ComponentKind.LevelInput2Pin):
    pass


class LevelInput3Pin(LevelInputComponent, kind=ComponentKind.LevelInput3Pin):
    pass


class LevelInput4Pin(LevelInputComponent, kind=ComponentKind.LevelInput4Pin):
    pass


class LevelInputCode(LevelInputComponent, kind=ComponentKind.LevelInputCode):
    pass


class LevelInputConditions(LevelInputComponent, kind=ComponentKind.LevelInputConditions):
    pass


class LevelOutput1(LevelOutputComponent, kind=ComponentKind.LevelOutput1):
    pass


class LevelOutput2Pin(LevelOutputComponent, kind=ComponentKind.LevelOutput2Pin):
    pass


class LevelOutput3Pin(LevelOutputComponent, kind=ComponentKind.LevelOutput3Pin):
    pass


class LevelOutput4Pin(LevelOutputComponent, kind=ComponentKind.LevelOutput4Pin):
    pass


class LevelOutput1Sum(LevelOutputComponent, kind=ComponentKind.LevelOutput1Sum):
    pass


class LevelOutput1Carry(LevelOutputComponent, kind=ComponentKind.LevelOutput1Car):
    pass


class LevelOutputCounter(LevelOutputComponent, kind=ComponentKind.LevelOutputCounter):
    pass


class LevelOutputArch(TCComponent, kind=ComponentKind.LevelOutputArch):
    pass


class LevelOutput8z(TCComponent, kind=ComponentKind.LevelOutput8z):
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
class MemoryComponent(TCComponent):
    link_id: int

    @classmethod
    def build(cls, parse_component: ParseComponent, **kwargs):
        return super().build(parse_component, **kwargs, link_id=parse_component.permanent_id)


@dataclass
class BitwiseLogic(TCComponent):
    op: ClassVar[str | None] = None


@_generate_larger
class Nand(BitwiseLogic, kind=ComponentKind.Nand):
    op = "~({a} & {b})"


@_generate_larger
class Nor(BitwiseLogic, kind=ComponentKind.Nor):
    op = "~({a} | {b})"


@_generate_larger
class Or(BitwiseLogic, kind=ComponentKind.Or):
    op = "{a} | {b}"


class Or3(BitwiseLogic, kind=ComponentKind.Or3):
    op = "{a} | {b} | {c}"


class And3(BitwiseLogic, kind=ComponentKind.And3):
    op = "{a} & {b} & {c}"


@_generate_larger
class Xor(BitwiseLogic, kind=ComponentKind.Xor):
    op = "{a} ^ {b}"


@_generate_larger
class Xnor(BitwiseLogic, kind=ComponentKind.Xnor):
    op = "~({a} ^ {b})"


@_generate_larger
class And(BitwiseLogic, kind=ComponentKind.And):
    op = "{a} & {b}"


@_generate_larger
class Not(BitwiseLogic, kind=ComponentKind.Not):
    op = "~{a}"


@_generate_larger("Buffer{n}")
class Buffer(BitwiseLogic):
    op = "{a}"


class Buffer1(Buffer, kind=ComponentKind.Buffer1):
    pass


class FullAdder(TCComponent, kind=ComponentKind.FullAdder):
    pass


class Decoder1(TCComponent, kind=ComponentKind.Decoder1):
    pass


class Decoder2(TCComponent, kind=ComponentKind.Decoder2):
    pass


class Decoder3(TCComponent, kind=ComponentKind.Decoder3):
    pass


class BitMemory(MemoryComponent, kind=ComponentKind.BitMemory):
    pass


class VirtualBitMemory(MemoryComponent, kind=ComponentKind.VirtualBitMemory):
    pass


@_generate_larger
class Neg(TCComponent):
    pass


@_generate_larger
class Add(TCComponent):
    pass


@_generate_larger
class Mul(TCComponent):
    pass


@_generate_larger
class DivMod(TCComponent):
    pass


@_generate_larger
class Shr(TCComponent):
    pass


@_generate_larger
class Shl(TCComponent):
    pass


@_generate_larger
class Ror(TCComponent):
    pass


@_generate_larger
class Rol(TCComponent):
    pass


@_generate_larger
class LessU(TCComponent):
    pass


@_generate_larger
class LessI(TCComponent):
    pass


@_generate_larger
class Register(MemoryComponent):
    pass


@_generate_larger
class VirtualRegister(MemoryComponent):
    pass


@_generate_larger
class Equal(TCComponent):
    pass


class LevelScreen(TCComponent, kind=ComponentKind.LevelScreen):
    pass


class Keyboard(TCComponent, kind=ComponentKind.Keyboard):
    pass


@dataclass
class Console(TCComponent, kind=ComponentKind.Console):
    linked_to: tuple[int, int]

    @classmethod
    def build(cls, parse_component: ParseComponent, **kwargs):
        return super().build(parse_component,
                             linked_to=tuple(map(int, filter(None, parse_component.custom_string.split(':')))),
                             **kwargs)


@dataclass
class SegmentDisplay(TCComponent, kind=ComponentKind.SegmentDisplay):
    pass  # TODO: color info


@dataclass
class DotMatrixDisplay(TCComponent, kind=ComponentKind.DotMatrixDisplay):
    pass  # TODO: extract info (orientation?)


@dataclass
class SpriteDisplay(TCComponent, kind=ComponentKind.SpriteDisplay):
    pass  # TODO: extract info (image?)


@dataclass
class Halt(TCComponent, kind=ComponentKind.Halt):
    msg: str

    @classmethod
    def build(cls, parse_component: ParseComponent, **kwargs):
        return super().build(parse_component, msg=parse_component.custom_string or "Halt", **kwargs)


@dataclass
class IndexerByte(TCComponent, kind=ComponentKind.IndexerByte):
    offset: int

    @classmethod
    def build(cls, parse_component: ParseComponent, **kwargs):
        return super().build(parse_component, offset=parse_component.setting_1, **kwargs)


@dataclass
class IndexerBit(TCComponent, kind=ComponentKind.IndexerBit):
    offset: int

    @classmethod
    def build(cls, parse_component: ParseComponent, **kwargs):
        return super().build(parse_component, offset=parse_component.setting_1, **kwargs)


class ProbeMemoryBit(TCComponent, kind=ComponentKind.ProbeMemoryBit):
    pass


class ProbeMemoryWord(TCComponent, kind=ComponentKind.ProbeMemoryWord):
    pass


class ProbeWireBit(TCComponent, kind=ComponentKind.ProbeWireBit):
    pass


class ProbeWireWord(TCComponent, kind=ComponentKind.ProbeWireWord):
    pass


class SomeProgram(TCComponent):
    selected_programs: dict[int, str]
    watched_links: list[tuple[int, ...]]
    data_width: int

    @classmethod
    def build(cls, parse_component: ParseComponent, **kwargs):
        return super().build(parse_component,
                             selected_programs=parse_component.selected_programs,
                             watched_links=[tuple(map(int, f.split(':')))
                                            for f in filter(None, parse_component.custom_string.split(','))],
                             **kwargs)


@dataclass
class Program(SomeProgram, kind=ComponentKind.Program):
    selected_programs: dict[int, str]
    watched_links: list[tuple[int, ...]]
    data_width: int

    @classmethod
    def build(cls, parse_component: ParseComponent, **kwargs):
        return super().build(parse_component, data_width=8 * 2 ** parse_component.setting_2, **kwargs)


@dataclass
class Program8_1(SomeProgram, kind=ComponentKind.Program8_1):
    selected_programs: dict[int, str]
    watched_links: list[tuple[int, ...]]
    data_width = 8


@_generate_larger
class Splitter(TCComponent):
    pass


@_generate_larger
class Maker(TCComponent):
    pass


@_generate_larger
class DelayLine(MemoryComponent):
    pass


@_generate_larger
class VirtualDelayLine(MemoryComponent):
    pass


class DelayLine1(DelayLine, kind=ComponentKind.DelayLine1):
    pass


class VirtualDelayLine1(VirtualDelayLine, kind=ComponentKind.VirtualDelayLine1):
    pass


@_generate_larger
class Switch(TCComponent):
    pass


class Switch1(Switch, kind=ComponentKind.Switch1):
    pass


@_generate_larger
class Mux(TCComponent):
    pass


@_generate_larger
@dataclass
class Counter(MemoryComponent):
    step: int

    @classmethod
    def build(cls, parse_component: ParseComponent, **kwargs):
        return super().build(parse_component, step=parse_component.setting_1, **kwargs)


@_generate_larger
@dataclass
class VirtualCounter(MemoryComponent):
    pass


class SomeConstant(TCComponent):
    value: int


@_generate_larger
@dataclass
class Constant(SomeConstant):
    value: int

    @classmethod
    def build(cls, parse_component: ParseComponent, **kwargs):
        return super().build(parse_component, **kwargs, value=parse_component.setting_1)


class Off(SomeConstant, kind=ComponentKind.Off):
    value = 0


class On(SomeConstant, kind=ComponentKind.On):
    value = 1


@dataclass
class FileLoader(TCComponent, kind=ComponentKind.FileLoader):
    default_file_path: str

    @classmethod
    def build(cls, parse_component: ParseComponent, **kwargs):
        return super().build(parse_component, default_file_path=parse_component.custom_string, **kwargs)


@dataclass
class RamLike(MemoryComponent):
    word_width: int
    word_count: int


@dataclass
class Ram(RamLike, kind=ComponentKind.Ram):
    @classmethod
    def build(cls, parse_component: ParseComponent, **kwargs):
        word_width = 8 * (2 ** parse_component.setting_2)
        return super().build(parse_component, **kwargs, word_width=word_width,
                             word_count=parse_component.setting_1 // word_width)


@dataclass
class VirtualRam(MemoryComponent, kind=ComponentKind.VirtualRam):
    pass


@dataclass
class RamFast(RamLike, kind=ComponentKind.RamFast):
    @classmethod
    def build(cls, parse_component: ParseComponent, **kwargs):
        word_width = 8 * (2 ** parse_component.setting_2)
        return super().build(parse_component, **kwargs, word_width=word_width,
                             word_count=parse_component.setting_1 // word_width)


@dataclass
class VirtualRamFast(MemoryComponent, kind=ComponentKind.VirtualRamFast):
    pass


@dataclass
class RamLatency(RamLike, kind=ComponentKind.RamLatency):
    @classmethod
    def build(cls, parse_component: ParseComponent, **kwargs):
        word_width = 8 * (2 ** parse_component.setting_2)  # TODO: check that this is correct
        return super().build(parse_component, **kwargs, word_width=word_width,
                             word_count=parse_component.setting_1 // word_width)


@dataclass
class VirtualRamLatency(MemoryComponent, kind=ComponentKind.VirtualRamLatency):
    pass


@dataclass
class Rom(RamLike, kind=ComponentKind.Rom):
    @classmethod
    def build(cls, parse_component: ParseComponent, **kwargs):
        word_width = 8 * (2 ** parse_component.setting_2)
        return super().build(parse_component, **kwargs, word_width=word_width,
                             word_count=parse_component.setting_1 // word_width)


@dataclass
class VirtualRom(MemoryComponent, kind=ComponentKind.VirtualRom):
    pass


@dataclass
class Hdd(TCComponent, kind=ComponentKind.Hdd):
    pass  # TODO: extract infos (size?)


@dataclass
class VirtualHdd(TCComponent, kind=ComponentKind.VirtualHdd):
    pass


@dataclass
class RamDualLoad(RamLike, kind=ComponentKind.RamDualLoad):
    @classmethod
    def build(cls, parse_component: ParseComponent, **kwargs):
        word_width = 8 * (2 ** parse_component.setting_2)
        return super().build(parse_component, **kwargs, word_width=word_width,
                             word_count=parse_component.setting_1 // word_width)


@dataclass
class VirtualRamDualLoad(MemoryComponent, kind=ComponentKind.VirtualRamDualLoad):
    pass


@dataclass
class CustomComponent(TCComponent, kind=ComponentKind.Custom, retrieve_info=False):
    custom_displacement: Point
    info: ComponentInfo

    @classmethod
    def build(cls, parse_component: ParseComponent, **kwargs):
        info = cc_loader.get()(parse_component.custom_id)
        return super().build(parse_component, info=info, custom_displacement=parse_component.custom_displacement,
                             **kwargs)

    def area(self) -> Iterable[Point]:
        d = self.custom_displacement - self.info.other['custom_displacement']
        for p in self.info.area:
            yield self.pos + (p + d).rotate(self.rotation)

    def local_to_global_pos(self, pos: Point) -> Point:
        d = self.custom_displacement - self.info.other['custom_displacement']
        return self.pos + (pos + d).rotate(self.rotation)

    def describe(self) -> str:
        return f"Custom: {self.info.other['name']}"


@dataclass
class LevelGate(TCComponent, kind=ComponentKind.LevelGate):
    pass  # TODO: extract infos
