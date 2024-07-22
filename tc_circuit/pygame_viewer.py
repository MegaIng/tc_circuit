from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from tkinter import filedialog, messagebox

from pygame import Vector2, SRCALPHA

import os
import pygame as pg
import tkinter as tk

from save_monger import ParseWire, Point
from save_monger.tc_save import TCSave

from tc_circuit.component_factory_loader import ComponentFactory
from tc_circuit.component_types import TCComponent, cc_loader
from tc_circuit.tc_circuit import TCCircuit, WIRE_COLORS


@dataclass
class ViewManager:
    scale: float
    center: Vector2
    screen: pg.Surface
    _grabbed_position: Vector2 | None = None

    @property
    def screen_center(self) -> Vector2:
        return Vector2(self.screen.size) / 2

    def s2w(self, pos: tuple[float, float]) -> Vector2:
        return self.center + (pos - self.screen_center) / self.scale

    def w2s(self, pos: tuple[float, float]) -> Vector2:
        return self.screen_center + (pos - self.center) * self.scale

    def w2s_r(self, rect: pg.Rect | pg.FRect) -> pg.FRect:
        return pg.FRect(
            self.screen_center + (rect.bottomleft - self.center) * self.scale,
            Vector2(rect.size) * self.scale
        )

    def handle_event(self, event: pg.Event) -> bool:
        match event:
            case pg.Event(type=pg.MOUSEWHEEL, y=y):
                fixed = self.s2w(pg.mouse.get_pos())
                self.scale *= 1.1 ** y
                delta = self.s2w(pg.mouse.get_pos()) - fixed
                self.center -= delta
                return True
            case pg.Event(type=pg.MOUSEBUTTONDOWN, button=pg.BUTTON_MIDDLE, pos=pos):
                self._grabbed_position = self.s2w(pos)
                return True
            case pg.Event(type=pg.MOUSEBUTTONUP, button=pg.BUTTON_MIDDLE):
                self._grabbed_position = None
                return True

    def update(self, delta: int):
        if self._grabbed_position is not None:
            delta = self.s2w(pg.mouse.get_pos()) - self._grabbed_position
            self.center -= delta



@dataclass
class CircuitRender:
    view: ViewManager
    circuit: TCCircuit
    font: pg.Font

    def draw_wire(self, wire: ParseWire, highlight: bool):
        # TODO: Think of something that looks better
        points = [self.view.w2s((p.x, p.y)) for p in wire.path]
        width = int(self.view.scale / 2)
        color = WIRE_COLORS[wire.color][wire.kind]
        radius = self.view.scale / 2
        pg.draw.lines(self.view.screen, color, False, points, width)
        # for p in points[1:-1]:
        #     pg.draw.circle(self.view.screen, color, p, radius)
        if highlight:
            highlight_color = (255, 0, 255)
            pg.draw.circle(self.view.screen, highlight_color, points[0], radius * 1.5)
            pg.draw.circle(self.view.screen, highlight_color, points[-1], radius * 1.5)
        pg.draw.circle(self.view.screen, color, points[0], radius)
        pg.draw.circle(self.view.screen, color, points[-1], radius)

    def draw_component(self, component: TCComponent, highlight: bool):
        color = (255, 0, 0)
        for area in component.area():
            r = pg.FRect((area.x - 0.5, area.y - 1.5), (1, 1))
            if highlight:
                hr = r.inflate(0.2, 0.2)
                hr.bottom -= 0.2
                pg.draw.rect(self.view.screen, (255, 0, 255), self.view.w2s_r(hr))
            pg.draw.rect(self.view.screen, color, self.view.w2s_r(r))
        for pin in component.info.pins:
            p = component.local_to_global_pos(pin.pos)
            center = self.view.w2s((p.x, p.y))
            radius = self.view.scale / 3
            pg.draw.circle(self.view.screen, color, center, radius)

    def draw(self):
        pos = self.view.s2w(pg.mouse.get_pos())
        highlighted = self.circuit.index[Point(x=int(round(pos[0])), y=int(round(pos[1])))]
        highlighted_wire_ids = {
            wid
            for ht, cid, _ in highlighted if ht == 'wire'
            for wid in self.circuit.clusters[1][self.circuit.wires[cid].start].segments
        }
        highlighted_components = {
            cid for ht, cid, _ in highlighted if ht == 'comp'
        }
        highlighted_pins = {
            (cid, pid) for ht, cid, pid in highlighted if ht == 'pin'
        }
        for wid, wire in self.circuit.wires.items():
            self.draw_wire(wire, wid in highlighted_wire_ids)
        for cid, comp in self.circuit.components.items():
            self.draw_component(comp, cid in highlighted_components)
        lines = None
        if highlighted_components:
            comp = self.circuit.components[highlighted_components.pop()]
            lines = comp.describe().splitlines()
        elif highlighted_pins:
            cid, pid = highlighted_pins.pop()
            comp = self.circuit.components[cid]
            pin = comp.info.pins[pid]
            lines = [f'{pin.label}']
        if lines is not None:
            images = [self.font.render(line, True, (255, 255, 255)) for line in lines]
            r = pg.Rect().unionall([img.get_rect().inflate(6, 6) for img in images])
            r.bottomleft = pg.mouse.get_pos()
            background = pg.Surface(r.size, SRCALPHA)
            background.fill((0, 0, 0, 127))
            self.view.screen.blit(background, r.topleft)
            y = r.top + 3
            x = r.left + 3
            for img in images:
                self.view.screen.blit(img, (x, y))
                y += img.height + 6


class ViewerApp:
    def __init__(self):
        self.root = tk.Tk()
        self.menubar = tk.Menu(self.root)
        self.menubar.add_command(label="Open Schematic", command=self.open_schematic)
        self.menubar.add_command(label="Select Save Folder", command=self.set_save_folder)
        self.root.config(menu=self.menubar)

        self.embed_pygame = tk.Frame(self.root, width=500, height=500)
        self.embed_pygame.pack(side=tk.TOP, expand=True, fill=tk.BOTH)
        os.environ['SDL_WINDOWID'] = str(self.embed_pygame.winfo_id())
        os.environ['SDL_VIDEODRIVER'] = 'windib'

        pg.init()
        screen = pg.display.set_mode()
        self.view = ViewManager(10, Vector2(0, 0), screen)
        self.save = TCSave.default_profile()
        self.component_factory = ComponentFactory(self.save)
        cc_loader.set(self.component_factory.load_component_info)

        self.render = None

        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.running = False

    def open_schematic(self):
        f = filedialog.askopenfilename(initialdir=self.save.schematics, filetypes=[("Circuit File", "circuit.data",)],
                                       title="Select a schematic to open")
        circuit = TCCircuit.from_bytes(Path(f).read_bytes())
        self.render = CircuitRender(self.view, circuit, pg.font.SysFont("arial", 20))

    def set_save_folder(self):
        save = filedialog.askdirectory(initialdir=self.save.schematics.parent.parent, mustexist=True,
                                       title="Select a Save Folder")
        if not Path(save, "schematics").is_dir():
            messagebox.showerror(title="Invalid Save Folder",
                                 message="This does not appear to be a valid TC save folder")
            return
        self.save.schematics = Path(save) / "schematics"
        self.component_factory.reload()

    def on_close(self):
        self.running = False

    def mainloop(self):
        clock = pg.time.Clock()
        self.running = True
        while self.running:
            delta = clock.tick()
            for event in pg.event.get():
                if self.view.handle_event(event):
                    continue

            self.view.update(delta)

            self.view.screen.fill((72, 76, 99))

            if self.render:
                self.render.draw()

            pg.display.update()

            if self.running:
                self.root.update()
        self.root.destroy()
        pg.quit()


def main():
    app = ViewerApp()
    app.mainloop()


if __name__ == '__main__':
    main()
