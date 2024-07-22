from __future__ import annotations

from dataclasses import dataclass
from math import trunc
from pathlib import Path

from save_monger import ParseResult, Point, ComponentKind
from save_monger.tc_save import TCSave

from tc_circuit.component_info import ComponentInfo, ComponentCategory, PinInfo
from tc_circuit.tc_circuit import TCCircuit


@dataclass
class CustomInfo:
    path: Path
    parse_result: ParseResult
    schematic: TCCircuit | None = None
    cinfo: ComponentInfo | None = None


FACTORY_OFFSET = 127


class ComponentFactory:
    def __init__(self, tcsave: TCSave):
        self.save = tcsave
        self.index = {}
        self.reload()

    def reload(self):
        self.index.clear()
        for file in (self.save.schematics / "component_factory").rglob("circuit.data"):
            pr = ParseResult.from_bytes(file.read_bytes(), headers_only=True)
            self.index[pr.save_id] = CustomInfo(file, pr)

    def __repr__(self):
        return f"{type(self).__name__}({self.path!r})"

    def load_component_info(self, cid: int) -> ComponentInfo:
        ci = self.index[cid]
        if ci.cinfo is None:
            self._fully_load(ci)
        return ci.cinfo

    def _fully_load(self, ci: CustomInfo):
        ci.parse_result = ParseResult.from_bytes(ci.path.read_bytes(), headers_only=False)
        ci.schematic = TCCircuit.from_parse_state(ci.parse_result)
        area = set()
        needs_virtual = False
        minx, miny, maxx, maxy = float("inf"), float("inf"), -float("inf"), -float("inf")
        for c in ci.schematic.components.values():
            if c.info.category != ComponentCategory.is_io:
                for p in c.area():
                    x = (p.x + FACTORY_OFFSET) // 8
                    y = (p.y + FACTORY_OFFSET) // 8
                    area.add(Point(x=x, y=y))
                    if x < minx: minx = x
                    if y < miny: miny = y
                    if x > maxx: maxx = x
                    if y > maxy: maxy = y
            if c.info.kind == ComponentCategory.has_virtual:
                needs_virtual = True
        # Carefully replicate nim behavior
        displacement = Point(x=trunc(-(maxx + minx) / 2), y=trunc(-(maxy + miny) / 2))

        pin_locations = set()
        pins = []
        for c in ci.schematic.components.values():
            if c.info.category == ComponentCategory.is_io:
                # if isinstance(c.info, Input):
                x = (c.pos.x + FACTORY_OFFSET) // 8
                y = (c.pos.y + FACTORY_OFFSET) // 8
                pins.append(PinInfo(kind={
                    "input": "output",
                    "output": "input"
                }[c.info.pins[0].kind],
                                    width=c.info.pins[0].width,
                                    pos=Point(x=x, y=y) + displacement,
                                    label=getattr(c, "label", f"No label: {type(c).__name__}")))
                pin_locations.add(pins[-1].pos)

        area = [r for p in area if (r := p + displacement) not in pin_locations]
        ci.cinfo = ComponentInfo(
            kind=ComponentKind.Custom,
            category=ComponentCategory.has_virtual if needs_virtual else ComponentCategory.default,
            pins=pins,
            backend_only=False,
            area=area,
            counterpart=ComponentKind.VirtualCustom if needs_virtual else None,
            other={
                'cid': ci.parse_result.save_id,
                'name': ci.path.parent.name,
                'custom_displacement': displacement
            }
        )
