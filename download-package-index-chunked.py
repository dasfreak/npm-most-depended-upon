#!/usr/bin/env python3

from __future__ import annotations
import argparse
import json
import logging
import logging.handlers
import math
from pathlib import Path
from typing import TypedDict

import requests


TIMEOUT_MINUTES = 60 * 3


class Args:
    out_dir: Path
    packages_per_request: int
    initial_package: str
    include_docs: bool


class Package(TypedDict):
    id: str
    key: str
    value: dict[str, str]


class Page(TypedDict):
    total_rows: int
    offset: int
    rows: list[Package]
    doc: dict  # only present if "include_docs" GET param is true


class NpmRegistry:
    def __init__(self, packages_per_request: int, initial_package: str, include_docs: bool):
        self.url = 'https://replicate.npmjs.com/_all_docs'
        self.last_downloaded_package = initial_package
        self.target_packages_per_request = packages_per_request
        self.current_packages_per_request = packages_per_request
        self.include_docs = include_docs

    def backon(self):
        if self.current_packages_per_request < self.target_packages_per_request:
            self.current_packages_per_request = min(
                self.target_packages_per_request, math.ceil(self.current_packages_per_request * 1.2)
            )

    def backoff(self):
        if self.current_packages_per_request >= self.target_packages_per_request // 10:
            self.current_packages_per_request = max(3, self.current_packages_per_request // 2)

    def get_next_page(self) -> Page:
        params = {
            'limit': self.current_packages_per_request,
            'start_key': json.dumps(self.last_downloaded_package),
            'include_docs': self.include_docs
        }
        success = False
        while not success:
            try:
                page = requests.get(self.url, params, timeout=TIMEOUT_MINUTES).json()
                logging.info(
                    'Successfully downloaded packages %i - %i / %i. '
                    'First package: %s. Last package: %s',
                    page['offset'],
                    page['offset'] + self.current_packages_per_request,
                    page['total_rows'],
                    page['rows'][0]['id'],
                    page['rows'][-1]['id']
                )
                success = True
                if self.last_downloaded_package != '':
                    del page['rows'][0]
                self.last_downloaded_package = page['rows'][-1]['id']
            except Exception as e:
                logging.error('Failed to download page starting at package %s limit %i. Error: %s',
                              self.last_downloaded_package,
                              self.current_packages_per_request,
                              e)
                self.backoff()
        self.backon()
        return page

    def download_package_index(self, out_dir: Path) -> None:
        page = {'rows': [1,2]}
        while len(page['rows']) > 1:
            page = self.get_next_page()
            self.save_page_content(out_dir, page)

    def save_page_content(self, dir_path: Path, page: Page) -> None:
        dir_path.mkdir(exist_ok=True)
        file_name = f'offset-{page["offset"]}.json'
        with open(dir_path / file_name, 'w') as fp:
            json.dump(page, fp)



def set_up_logger() -> None:
    file_handler = logging.handlers.RotatingFileHandler(
        filename='npm-index.log',
        maxBytes=1024 * 1024,  # Max 1 Mb per logfile
        backupCount=3,
        encoding='utf-8'
    )
    stream_handler = logging.StreamHandler()
    logging.basicConfig(
        handlers=(file_handler, stream_handler),
        format='%(asctime)s [%(levelname)-4.4s] %(message)s',
        datefmt='%Y-%m-%dT%H:%M:%S',
        level=logging.INFO
    )


def parse_args() -> Args:
    parser = argparse.ArgumentParser('Downlaod the npm registrie\'s package index.')
    parser.add_argument('--out-dir',
                        '-o',
                        help='Directory to place the pages in',
                        type=Path)
    parser.add_argument('--packages-per-request',
                        '-p',
                        help='Amount of packages to download in one request.',
                        default=1000,
                        type=int)
    parser.add_argument('--initial-package',
                        help='The name of the first package to return in the sorted package list response.',
                        default="",
                        type=str)
    parser.add_argument('--include-docs',
                        help='Include all package metadata.',
                        default=False,
                        action='store_true')
    return parser.parse_args(namespace=Args())


def main() -> None:
    set_up_logger()
    args = parse_args()
    reg = NpmRegistry(args.packages_per_request, args.initial_package, args.include_docs)
    reg.download_package_index(args.out_dir)


if __name__ == '__main__':
    main()
