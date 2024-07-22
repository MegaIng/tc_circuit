from __future__ import annotations

import base64
import importlib.resources
import re
import sys
from argparse import ArgumentParser, FileType
from dataclasses import dataclass
from importlib.abc import Traversable
from pathlib import Path

from svgwrite import Drawing
from svgwrite.shapes import Circle, Rect
from svgwrite.path import Path as SvgPath
from svgwrite.image import Image
from svgwrite.container import Group, Use, Defs

from save_monger import WireKind, Point
from save_monger.tc_save import TCSave

from tc_circuit.component_factory_loader import ComponentFactory
from tc_circuit.component_info import ComponentInfo, PinInfo, ComponentCategory
from tc_circuit.component_types import cc_loader, TCComponent, CustomComponent
from tc_circuit.tc_circuit import TCCircuit, WIRE_COLORS

IMAGE_OVERWRITES = {
    'Program': 'Program1',
    'IndexerBit': 'StateBit',
    'ProbeWireBit': 'StateBit',
    'ProbeMemoryBit': 'StateBit',
    'IndexerByte': 'StateByte',
    'ProbeWireWord': 'StateByte',
    'ProbeMemoryWord': 'StateByte',

    'Counter8': 'Counter',
    'Decoder1': '1_decoder',
    'Decoder2': '2_decoder',
    'Decoder3': '3_decoder',

    'LevelOutputArch': 'Output1_1B',
    'LevelInputArch': 'Input1_1B',
    'LevelInputCode': 'Input1B',
    'LevelInputConditions': 'Input1B',
    'LevelOutput1Sum': 'Output1',
    'LevelOutput1Car': 'Output1',

    'Output16': 'Input16',
    'Output32': 'Input16',
    'Output16z': 'Input16',
    'Output32z': 'Input16',

    'Buffer1': 'StateBit',

    'Mux8': 'Mux',
    'Mux16': 'Mux',
    'Mux32': 'Mux',
    'Mux64': 'Mux',

    'DelayLine1': 'DelayBuffer',
    'DelayLine8': 'DelayBuffer',
    'DelayLine16': 'Register16',
    'DelayLine32': 'Register16',
    'DelayLine64': 'QwordRegister',
    'Counter16': 'Register16',
    'Counter32': 'Register16',
    'Register8': 'Register',

    'FileLoader': 'FileRom',
    'RamFast': 'Ram',
    'RamDualLoad': 'Ram',
    'RamLatency': 'Ram',
    'Hdd': 'Ram',
    'Rom': 'Ram',
    'Program8_1': 'Program1',

}


def get_image(base_name: str) -> Traversable:
    TRANSFORMS = [
        (r"(\w+)64", r"Qword\1"),
        (r"(\w+)64", r"\g<1>Qword"),
        (r"Level(\w+)", r"\1"),
        (r"(\w+)Pin", r"\1"),
        (r"(\w+)64", r"\g<1>8"),
        (r"(\w+)8", r"\g<1>1B"),
    ]
    if base_name in IMAGE_OVERWRITES:
        return importlib.resources.files('tc_circuit') / 'atlas' / f'{IMAGE_OVERWRITES[base_name]}.png'
    to_try = {base_name}
    for pat, sub in TRANSFORMS:
        new_to_try = set(to_try)
        for name in to_try:
            new_to_try.add(re.sub(r"\A(?:" + pat + r")\Z", sub, name))
        to_try = new_to_try
    if base_name.endswith('64'):
        to_try.add(f'Byte{base_name[:-2]}')
        to_try.add(f'{base_name[:-2]}8')
    if base_name.endswith('32'):
        to_try.add(f'{base_name[:-2]}16')
        to_try.add(f'Byte{base_name[:-2]}')
        to_try.add(f'{base_name[:-2]}8')
    if base_name.endswith('16'):
        to_try.add(f'Byte{base_name[:-2]}')
        to_try.add(f'{base_name[:-2]}8')
    if base_name.endswith('8'):
        to_try.add(f'Byte{base_name[:-1]}')
        to_try.add(f'{base_name[:-1]}B')
    for name in to_try:
        f = importlib.resources.files('tc_circuit') / 'atlas' / f'{name}.png'
        if f.is_file():
            return f
    else:
        raise ValueError(f"Can't find image for {base_name} (tried {to_try})")


def get_png_size(content: bytes) -> tuple[int, int]:
    assert content[:8] == b'\x89PNG\r\n\x1a\n', content[:8]
    assert content[12:16] == b'IHDR', content[12:16]
    return int.from_bytes(content[16:20], byteorder='big'), int.from_bytes(content[20:24], byteorder='big')


def get_transform(comp: TCComponent) -> dict:
    out = {}
    out['x'] = comp.pos.x
    out['y'] = comp.pos.y
    if isinstance(comp, CustomComponent):
        delta = comp.custom_displacement - comp.info.other['custom_displacement']
        out['x'] += delta.x
        out['y'] += delta.y
        if comp.rotation != 0:
            out['transform'] = f"rotate({90 * comp.rotation} {comp.pos.x} {comp.pos.y})"
    else:
        if comp.rotation != 0:
            out['transform'] = f"rotate({90 * comp.rotation} {comp.pos.x} {comp.pos.y})"
    return out


@dataclass
class ToSvg:
    circuit: TCCircuit
    svg: Drawing = None
    defs: Defs = None
    pin_types: dict[(str, int), str] = None

    def generate(self):
        self.svg = Drawing("circuit.svg", id="root")

        img = importlib.resources.files('tc_circuit') / 'atlas' / f'background.png'
        content = img.read_bytes()
        size = get_png_size(content)
        content = base64.b64encode(content).decode()

        self.svg.embed_stylesheet(f"""

#root {{
    background-image: url("data:image/png;base64,{content}");
    background-size: {size[0] / 20}px {size[1] / 20}px;
}}
.wire-cluster {{
    fill: rgba(0,0,0,0);
}}
.wire-cluster:hover {{
    fill: rgba(255,0,255,255);
}}
.wire-bit {{
    fill: none;
    stroke: var(--base-color);
    stroke-width: 0.4;
}}

.wire-word {{
    fill: none;
    stroke: var(--base-color);
    stroke-width: 0.5;
}}

.wire-head {{
    fill: none;
    stroke: var(--base-color);
    stroke-width: 0.2
}}

.wire0-0 {{ --base-color: rgb{WIRE_COLORS[0][0]}; }}
.wire0-1 {{ --base-color: rgb{WIRE_COLORS[0][1]}; }}
.wire0-2 {{ --base-color: rgb{WIRE_COLORS[0][2]}; }}
.wire0-3 {{ --base-color: rgb{WIRE_COLORS[0][3]}; }}
.wire0-4 {{ --base-color: rgb{WIRE_COLORS[0][4]}; }}
.wire1 {{ --base-color: rgb{WIRE_COLORS[1][0]}; }}
.wire2 {{ --base-color: rgb{WIRE_COLORS[2][0]}; }}
.wire3 {{ --base-color: rgb{WIRE_COLORS[3][0]}; }}
.wire4 {{ --base-color: rgb{WIRE_COLORS[4][0]}; }}
.wire5 {{ --base-color: rgb{WIRE_COLORS[5][0]}; }}
.wire6 {{ --base-color: rgb{WIRE_COLORS[6][0]}; }}
.wire7 {{ --base-color: rgb{WIRE_COLORS[7][0]}; }}
.wire8 {{ --base-color: rgb{WIRE_COLORS[8][0]}; }}
.wire9 {{ --base-color: rgb{WIRE_COLORS[9][0]}; }}
.wire10 {{ --base-color: rgb{WIRE_COLORS[10][0]}; }}
""")
        self.defs = Defs()
        self.pin_types = {}
        self.svg.add(self.defs)
        minx, maxx, miny, maxy = float('inf'), -float('inf'), float('inf'), -float('inf')

        def touched_point(p: Point):
            nonlocal minx, maxx, miny, maxy
            if p.x < minx: minx = p.x
            if p.x > maxx: maxx = p.x
            if p.y < miny: miny = p.y
            if p.y > maxy: maxy = p.y

        for wire in self.circuit.wires.values():
            classes = [
                'wire-bit' if wire.kind == WireKind.wk_1 else 'wire-word',
                f'wire{wire.color}' if wire.color != 0 else f'wire{wire.color}-{wire.kind}'
            ]
            if len(wire.path) == 2:
                d = wire.path[1] - wire.path[0]
                if abs(d.x) + abs(d.y) > 1:
                    continue  # portal wire
                self.svg.add(path := SvgPath(class_=' '.join(classes)))
                path.push('M', wire.start.x + d.x / 4, wire.start.y + d.y / 4)
                path.push('l', d.x/2, d.y/2)
            else:
                self.svg.add(path := SvgPath(class_=' '.join(classes)))
                d = wire.path[1] - wire.path[0]
                path.push('M', wire.start.x + d.x / 6, wire.start.y + d.y / 6)
                touched_point(wire.start)
                for a,b in zip(wire.path, wire.path[1:-1]):
                    d = b-a
                    path.push('L', b.x, b.y)
                    touched_point(b)
                d = wire.path[-1] - wire.path[-2]
                path.push('L', wire.end.x - d.x / 6, wire.end.y - d.y / 6)
                # path.push('l', d.x / 2, d.y / 2)

        done = {}
        for comp in self.circuit.components.values():
            if comp.info.category == ComponentCategory.is_virtual:
                continue
            if comp.info not in done:
                done[comp.info] = self.draw_component(comp.info)
            self.svg.add(Use(done[comp.info][0], **get_transform(comp)))
            for p in comp.area():
                touched_point(p)

        for wire in self.circuit.wires.values():
            classes = [
                'wire-head',
                f'wire{wire.color}' if wire.color != 0 else f'wire{wire.color}-{wire.kind}'
            ]
            self.svg.add(Circle((wire.start.x, wire.start.y), 0.25, class_=' '.join(classes)))
            self.svg.add(Circle((wire.end.x, wire.end.y), 0.25, class_=' '.join(classes)))

        for comp in self.circuit.components.values():
            if comp.info.category == ComponentCategory.is_virtual:
                continue
            self.svg.add(Use(done[comp.info][1], **get_transform(comp)))
            for p in comp.area():
                touched_point(p)

        for cluster in self.circuit.clusters[0]:
            self.svg.add(g := Group(class_="wire-cluster"))
            for p in set(cluster.points):
                g.add(Circle((p.x, p.y), r=0.6))

        cx, cy = (minx + maxx) / 2, (miny + maxy) / 2
        w, h = maxx - minx, maxy - miny
        w += 5
        h += 5
        self.svg['viewBox'] = f'{cx - w / 2} {cy - h / 2} {w} {h}'

    def draw_component(self, comp: ComponentInfo):
        assert comp.category != ComponentCategory.is_virtual
        name_id = comp.kind.name
        if name_id != 'Custom':
            img = get_image(name_id)
            content = img.read_bytes()
            size = get_png_size(content)
            content = base64.b64encode(content).decode()
            self.defs.add(image := Image(
                id=f"{name_id}-image",
                href=f"data:image/png;base64,{content}",
                width=size[0] / 20, height=size[1] / 20,
                x=-size[0] / 40, y=-size[1] / 40,
            ))
        else:
            name_id = f'Custom-{comp.other["cid"]}'
            self.defs.add(image := Group(
                id=f"{name_id}-image",
            ))
            for area in comp.area:
                image.add(Rect((area.x - 0.5, area.y - 0.5), (1.01, 1.01), fill="rgb(30, 165, 174)", stroke="none"))
        self.defs.add(pin_container := Group(id=f"{name_id}-pins"))
        for pin in comp.combined_pins():
            if (pin.kind, pin.width) not in self.pin_types:
                self.pin_types[(pin.kind, pin.width)] = self.draw_pin(pin)
            pin_container.add(Use(self.pin_types[(pin.kind, pin.width)], x=pin.pos.x, y=pin.pos.y))
        return (pin_container.get_iri(), image.get_iri())

    def draw_pin(self, pin: PinInfo):
        outer_radius = 0.3 if pin.width == 1 else 0.35
        inner_radius = {1: None, 8: None, 16: 0.1, 32: 0.15, 64: 0.25}[pin.width]
        color = {
            'input': (231, 121, 127),
            'input_late': (227, 158, 69),
            'output': (230, 63, 92),
            'bidirectional': (102, 125, 199),
            'output_tristate': (131, 130, 113)
        }[pin.kind]
        g = Group(id=f"{pin.kind}-{pin.width}")
        if pin.kind != "input_late":
            g.add(Circle(r=outer_radius, fill=f"rgb{color}"))
        else:
            g.add(Rect(insert=(-outer_radius,-outer_radius),
                       size=(outer_radius*2,outer_radius*2),
                       rx=0.1, ry=0.1,
                       fill=f"rgb{color}"))
        if inner_radius is not None:
            g.add(Circle(r=inner_radius, fill=f"rgb(0,0,0)", fill_opacity=0.30))
        self.defs.add(g)
        return g.get_iri()


def main(args: list[str] = None):
    if args is None:
        args = sys.argv[1:]
    argparse = ArgumentParser()
    argparse.add_argument('-o', '--out', type=FileType('w'), default=sys.stdout)
    argparse.add_argument('circuit', type=Path)
    args = argparse.parse_args(args)
    data = args.circuit.read_bytes()
    if 'schematics' in args.circuit.parts:
        p = args.circuit
        while p.name != 'schematics':
            p = p.parent
        tc_save = TCSave(p)
        cc_loader.set(ComponentFactory(tc_save).load_component_info)
    circuit = TCCircuit.from_bytes(data)
    comp = ToSvg(circuit)
    comp.generate()
    comp.svg.write(args.out, pretty=True)


if __name__ == '__main__':
    main()
