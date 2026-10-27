#!/usr/bin/env python3
"""Editable native RAVEL launch composition. Uses real captured product frames.

Requires Pillow and FFmpeg. Run: python render.py /absolute/new-output.mp4
No network, bundled fonts, audio or API. System-font fallbacks keep it portable.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import shutil
import subprocess
from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
TIMELINE = json.loads((HERE / 'timeline.json').read_text())
ASSETS = HERE.parent / 'assets'
W, H = TIMELINE['width'], TIMELINE['height']
FPS, DURATION = TIMELINE['fps'], TIMELINE['duration_seconds']
PAPER = '#f5f4ef'
INK = '#202c2a'
MUTED = '#697570'
TEAL = '#21695c'
COPPER = '#aa6040'
LINE = '#d8ddd5'


def font(size, mono=False):
    options = (['/System/Library/Fonts/Menlo.ttc', '/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf'] if mono else
               ['/System/Library/Fonts/SFNS.ttf', '/System/Library/Fonts/Helvetica.ttc', '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'])
    for path in options:
        if Path(path).is_file():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default(size=size)

FONTS = {size: font(size) for size in [18, 20, 24, 29, 34, 40, 80, 98]}
MONO = {size: font(size, True) for size in [12, 13, 16, 22, 26]}
SHOTS = {name: Image.open(ASSETS / name).convert('RGB') for name in
         ['symbol-search.jpg', 'natural-search.jpg', 'source-detail.jpg']}


def ease(x):
    x = min(1, max(0, x))
    return 1 - (1 - x) ** 3


def thread(draw, x, y, width, progress=1):
    for offset in [-92, -30, 30, 92]:
        points = []
        for j in range(max(2, int(100 * progress))):
            t = j / 99
            # Cubic paths resolve into the single precise point.
            px = (1-t)**3*x + 3*(1-t)**2*t*(x+width*.6) + 3*(1-t)*t*t*(x+width*.35) + t**3*(x+width)
            py = (1-t)**3*(y+offset) + 3*(1-t)**2*t*(y+offset) + 3*(1-t)*t*t*y + t**3*y
            points.append((px, py))
        draw.line(points, fill=TEAL, width=3)
    if progress > .85:
        r = 10 * ease((progress - .85)/.15)
        draw.ellipse((x+width-r, y-r, x+width+r, y+r), fill=COPPER)


def base():
    frame = Image.new('RGB', (W, H), PAPER)
    draw = ImageDraw.Draw(frame)
    draw.text((50, 27), 'RAVEL / SOURCE → SIGNAL', fill=TEAL, font=MONO[13])
    draw.text((1020, 27), 'LOCAL-FIRST', fill=MUTED, font=MONO[13])
    draw.line((50, 60, W-50, 60), fill=LINE)
    return frame


def identity(t, final=False):
    frame = base()
    draw = ImageDraw.Draw(frame)
    start = t-14 if final else t
    thread(draw, 82, 288, 290, ease(start/.9))
    draw.text((445, 202), 'RAVEL', fill=INK, font=FONTS[98])
    draw.text((449, 327), 'The right context.', fill=INK, font=FONTS[34])
    draw.text((449, 372), 'Almost no overhead.', fill=MUTED, font=FONTS[34])
    if final:
        draw.rounded_rectangle((448, 460, 1125, 558), radius=5, fill='#e5ebe4')
        draw.text((471, 477), '$ ravel index .', fill=TEAL, font=MONO[26])
        draw.text((471, 518), '$ ravel inspect', fill=TEAL, font=MONO[26])
        draw.text((50, 656), 'CLI · PYTHON API · MCP · LOCAL INSPECTOR', fill=MUTED, font=MONO[13])
    else:
        draw.text((50, 585), 'Code + documents. Source-linked context.', fill=MUTED, font=FONTS[24])
        draw.text((50, 656), 'LOCAL SEARCH / EXPLICIT BUDGETS / NO PAID API', fill=TEAL, font=MONO[13])
    return frame


def product(t, scene):
    frame = base()
    draw = ImageDraw.Draw(frame)
    draw.text((50, 77), scene['title'], fill=INK, font=FONTS[29])
    draw.text((947, 88), 'ACTUAL LOCAL CAPTURE', fill=MUTED, font=MONO[12])
    shot = SHOTS[scene['asset']]
    target_width, target_height = 1176, 543
    # Scale captures proportionately. Detail view gets its own authentic scroll capture.
    scale = min(target_width / shot.width, target_height / shot.height)
    size = (round(shot.width * scale), round(shot.height * scale))
    shot = shot.resize(size, Image.Resampling.LANCZOS)
    x = (W - size[0]) // 2
    y = 130 + round(12*(1-ease((t-scene['start'])/.4)))
    draw.rectangle((x-1, y-1, x+size[0], y+size[1]), outline=LINE)
    frame.paste(shot, (x, y))
    draw.text((50, 694), 'Example repository · observed timings include model startup · UTF-8 byte budget bound', fill=MUTED, font=MONO[12])
    return frame


def scene_for(t):
    return next((s for s in TIMELINE['scenes'] if s['start'] <= t < s['end']), TIMELINE['scenes'][-1])


def render_frame(t):
    scene = scene_for(t)
    frame = identity(t, scene['start'] == 14) if scene['type'] == 'original_identity' else product(t, scene)
    # Brief dip to paper keeps separate captured product states visually honest.
    elapsed = t - scene['start']
    if scene['start'] and elapsed < .18:
        frame = Image.blend(Image.new('RGB', (W, H), PAPER), frame, ease(elapsed/.18))
    return frame


def main():
    p = argparse.ArgumentParser()
    p.add_argument('output', type=Path)
    p.add_argument('--frame', type=float, help='Save one current composition frame as PNG instead')
    args = p.parse_args()
    output = args.output.resolve()
    if output.exists() or output.is_symlink():
        raise SystemExit('Refusing to overwrite existing output: '+str(output))
    if not output.parent.is_dir():
        raise SystemExit('Output parent must already exist')
    if args.frame is not None:
        render_frame(args.frame).save(output)
        return
    ffmpeg = shutil.which('ffmpeg')
    if not ffmpeg:
        raise SystemExit('FFmpeg is required')
    staged = output.with_name(output.stem+'.staging.mp4')
    if staged.exists():
        raise SystemExit('Existing stage requires review: '+str(staged))
    process = subprocess.Popen([ffmpeg, '-v', 'error', '-n', '-f', 'rawvideo', '-pix_fmt', 'rgb24',
        '-s', f'{W}x{H}', '-r', str(FPS), '-i', '-', '-an', '-c:v', 'libx264', '-crf', '20',
        '-preset', 'medium', '-pix_fmt', 'yuv420p', '-movflags', '+faststart', str(staged)], stdin=subprocess.PIPE)
    try:
        for i in range(round(DURATION*FPS)):
            process.stdin.write(render_frame(i/FPS).tobytes())
        process.stdin.close()
        if process.wait():
            raise SystemExit('FFmpeg render failed; stage preserved')
        # Hard-link publication is exclusive, preserving any competing valid output.
        output.hardlink_to(staged)
        staged.unlink()
    except BaseException:
        process.terminate()
        process.wait()
        raise
    print(output)

if __name__ == '__main__':
    main()
