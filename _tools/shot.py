#!/usr/bin/env python3
"""Headless screenshots for checking the page.

shot.py URL OUT.png [W H] [--wait JS] [--full] [--scroll SELECTOR] [--delay MS] [--eval JS]
  --full     scroll through the page first (fires reveal/lazy observers), then capture it all
  --scroll   bring SELECTOR into view and capture the viewport
"""
import asyncio
import sys

from playwright.async_api import async_playwright


def opt(name, default=None):
    return sys.argv[sys.argv.index(name) + 1] if name in sys.argv else default


async def main():
    url, out = sys.argv[1], sys.argv[2]
    w = int(sys.argv[3]) if len(sys.argv) > 3 and sys.argv[3].isdigit() else 1440
    h = int(sys.argv[4]) if len(sys.argv) > 4 and sys.argv[4].isdigit() else 900
    async with async_playwright() as p:
        b = await p.chromium.launch(args=['--use-gl=angle', '--use-angle=swiftshader',
                                          '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist',
                                          '--autoplay-policy=no-user-gesture-required']
                                    + (['--disable-webgl', '--disable-3d-apis'] if '--nogl' in sys.argv else []))
        pg = await b.new_page(viewport={'width': w, 'height': h},
                              device_scale_factor=float(opt('--dpr', 1)))
        pg.on('console', lambda m: print('console:', m.text) if m.type in ('error', 'warning') else None)
        pg.on('pageerror', lambda e: print('pageerror:', e))
        pg.on('response', lambda r: print('http', r.status, r.url) if r.status >= 400 else None)
        await pg.goto(url, wait_until='domcontentloaded', timeout=90000)
        if opt('--wait'):
            await pg.wait_for_function(opt('--wait'), timeout=240000)
        if '--full' in sys.argv:
            total = await pg.evaluate('document.body.scrollHeight')
            for y in range(0, total, h // 2):
                await pg.evaluate(f'window.scrollTo(0, {y})')
                await pg.wait_for_timeout(120)
            await pg.wait_for_timeout(1500)
        if opt('--scroll'):
            await pg.evaluate(f"document.querySelector('{opt('--scroll')}').scrollIntoView({{block:'start'}})")
            await pg.wait_for_timeout(600)
        await pg.wait_for_timeout(int(opt('--delay', 1500)))
        if opt('--eval'):
            r = await pg.evaluate(opt('--eval'))
            if r is not None:
                print('eval:', r)
            await pg.wait_for_timeout(int(opt("--after", 300)))
        await pg.screenshot(path=out, full_page='--full' in sys.argv)
        await b.close()

asyncio.run(main())
