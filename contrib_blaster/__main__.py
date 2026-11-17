"""CLI: python -m contrib_blaster --user LOGIN --out dist [--input calendar.json]

Without --input the calendar is fetched from the GitHub GraphQL API using the
token in $GITHUB_TOKEN (or $GH_TOKEN). The token is never written anywhere.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from . import character, contributions
from .render import render

OUTPUTS = {'light': 'expedition-contrib.svg', 'dark': 'expedition-contrib-dark.svg'}
DEFAULT_CHARACTER = 'character.toml'


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog='contrib_blaster', description=__doc__.splitlines()[0])
    ap.add_argument('--user', default=os.environ.get('GITHUB_REPOSITORY_OWNER', ''),
                    help='GitHub login (default: $GITHUB_REPOSITORY_OWNER)')
    ap.add_argument('--input', help='read a saved GraphQL response instead of calling the API')
    ap.add_argument('--save', help='also save the fetched GraphQL response to this path')
    ap.add_argument('--out', default='dist', help='output folder (default: dist)')
    ap.add_argument('--character', help='hero settings file (default: character.toml if it exists)')
    args = ap.parse_args(argv)
    if not args.user:
        ap.error('--user is required')

    if args.character:
        hero = character.load(args.character)              # named explicitly: must exist
    elif Path(DEFAULT_CHARACTER).is_file():
        hero = character.load(DEFAULT_CHARACTER)
    else:
        hero = character.Character()

    if args.input:
        cal = contributions.load(args.input, args.user)
    else:
        token = os.environ.get('GITHUB_TOKEN') or os.environ.get('GH_TOKEN', '')
        payload = contributions.fetch(args.user, token)
        if args.save:
            Path(args.save).write_text(json.dumps(payload, indent=1), encoding='utf-8')
        cal = contributions.parse(payload, args.user)

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    for theme, name in OUTPUTS.items():
        svg = render(cal, theme, hero)
        (out / name).write_text(svg, encoding='utf-8')
        print(f'{out / name}: {len(svg) // 1024} KB, {len(cal.active)} blocks, theme {theme}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
