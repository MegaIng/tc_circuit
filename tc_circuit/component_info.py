import json
from functools import cached_property

from pydantic import BaseModel, BeforeValidator
from save_monger import ComponentKind, Point
from enum import Enum
from importlib.resources import files
from typing import Annotated, Any, Iterable


class PinKinds(Enum):
    input = 0
    output = 1
    output_tristate = 2
    bidirectional = 3


class ComponentCategory(Enum):
    default = 0
    is_io = 1
    has_virtual = 2
    is_virtual = 3


def list_to_point(obj):
    if isinstance(obj, list) and len(obj) == 2:
        return {'x': obj[0], 'y': obj[1]}
    else:
        return obj


def enum_by_name(e: type):
    assert issubclass(e, Enum), e

    def validator(obj):
        if isinstance(obj, str):
            return getattr(e, obj)
        else:
            return obj

    return BeforeValidator(validator)


class PinInfo(BaseModel, frozen=True):
    kind: str
    width: int
    pos: Annotated[Point, BeforeValidator(list_to_point)]
    label: str


class ComponentInfo(BaseModel, frozen=True):
    kind: ComponentKind
    category: Annotated[ComponentCategory, enum_by_name(ComponentCategory)]
    pins: tuple[PinInfo, ...]
    backend_only: bool
    area: tuple[Annotated[Point, BeforeValidator(list_to_point)], ...]
    counterpart: Annotated[ComponentKind | None, enum_by_name(ComponentKind)] = None
    other: dict[str, Any] | None = None

    @cached_property
    def pins_by_label(self):
        res = {p.label: p for p in self.pins}
        assert len(res) == len(self.pins), self.pins
        return res

    def __hash__(self):
        return hash((
            self.kind, self.category, self.pins, self.backend_only, self.area,
            self.counterpart, frozenset(self.other.items()) if self.other is not None else None
        ))

    def combined_pins(self) -> Iterable[PinInfo]:
        if self.counterpart is None:
            return self.pins
        counterpart = COMPONENT_INFOS[self.counterpart]
        if counterpart.category == ComponentCategory.has_virtual:
            assert self.category == ComponentCategory.is_virtual, counterpart
            return counterpart.combined_pins()
        early_pins = self.pins
        late_pins = []
        for pin in counterpart.pins:
            if pin not in early_pins:
                assert pin.kind == 'input', pin
                late_pins.append(PinInfo(kind='input_late', width=pin.width, pos=pin.pos, label=pin.label))
        return (*early_pins, *late_pins)

COMPONENT_INFOS: dict[ComponentKind, ComponentInfo] = {
    (kind := getattr(ComponentKind, name)): ComponentInfo(kind=kind, **value)
    for name, value in json.load((files(__package__) / "component_info.json").open("r", encoding="utf-8")).items()
}
