#!/usr/bin/env python3

import argparse
import json
from pathlib import Path

class Args():
    in_path: Path
    out_path: Path
    limit: int


def parse_args() -> Args:
    parser = argparse.ArgumentParser()
    parser.add_argument('--in-path',
                        '-i',
                        help=('Path to read data from. Usually a doc file, except when using '
                              '--preprocess-from-pages, then it\'s the path to the pages directory.'),
                        type=Path)
    parser.add_argument('--out-path',
                        '-o',
                        help='Destination to write the resulting file to.',
                        type=Path)
    parser.add_argument('--limit',
                        '-l',
                        help='Amount of packages to write to the file.',
                        default=1000,
                        type=int)
    args = parser.parse_args(namespace=Args())
    return args


def main():
    args = parse_args()
    with open(args.in_path, 'r') as fp:
        data = json.load(fp)
    header = ['| # | name | count |', '|---|------|-------|']
    rows = [
        f'| {i+1} | {name} | {count} |'
        for i, (name, count) in enumerate(data[:args.limit])
    ]
    result = '\n'.join(header + rows)
    with open(args.out_path, 'w') as fp:
        fp.write(result)


if __name__ == '__main__':
    main()
