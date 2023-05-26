from __future__ import annotations

import argparse
import json
import logging
from collections import defaultdict
from pathlib import Path
from typing import Any, Optional

import semver
import networkx as nx
from pydantic import BaseModel, Field, validator


PackageName = str
DependencyName = str
DependantName = str


class Args():
    in_path: Path
    out_path: Path
    strip: bool
    strip_from_pages: bool
    build_dependant_map: bool
    build_transitive_dependant_map: bool
    count_direct_dependants: bool
    count_transitive_dependants: bool


class Package(BaseModel):
    dependencies: dict[str, Any] = {}

    @validator('dependencies', pre=True)
    def dependencies_must_be_dict(cls, v: Any) -> dict[str, str]:
        if not isinstance(v, dict):
            return {}
        return v


class DistTags(BaseModel):
    latest: Optional[str] = None


class CouchDBDoc(BaseModel):
    dist_tags: DistTags = Field(default=DistTags(), alias='dist-tags')
    versions: dict[str, Package] = {}


class CouchDBRow(BaseModel):
    id: str
    doc: CouchDBDoc


class CouchDBPage(BaseModel):
    rows: list[CouchDBRow]


def get_latest_version(package_doc: CouchDBDoc) -> str:
    if len(package_doc.versions) == 0:
        raise ValueError('Package has no versions')

    # 1: latest version by 'latest' key
    if package_doc.dist_tags.latest and package_doc.dist_tags.latest in package_doc.versions:
        return package_doc.dist_tags.latest

    # 2: latest version by semantic versioning maximum
    try:
        versions = [semver.version.Version.parse(v) for v in package_doc.versions]
    except ValueError:
        # 3: does not use (correct) semantic versioning -> return last version in versions list
        return list(package_doc.versions.keys())[-1]
    else:
        non_pre_versions = [v for v in versions if v.prerelease is None]
        if len(non_pre_versions) > 0:
            return str(max(non_pre_versions))
        else:
            return str(max(versions))


def create_dependency_map(packages: CouchDBPage) -> dict[PackageName, list[DependencyName]]:
    dependency_map = {}
    for row in packages.rows:
        package_name = row.id
        try:
            latest_version = get_latest_version(row.doc)
        except ValueError as e:
            # TODO: maybe we want to add this package as "has no dependencies" or something
            logging.warning(
                'Could not determine latest version (and thus skipping) for package `%s`: %s',
                package_name,
                e
            )
            continue

        dependencies = row.doc.versions[latest_version].dependencies
        try:
            dependency_map[package_name] = list(dependencies.keys())
        except AttributeError:
            # Dependencies not provided as a dict, as is required
            dependency_map[package_name] = []
    return dependency_map


def build_inverse_dependency_map(
    dependency_map: dict[PackageName, list[DependencyName]]
) -> dict[PackageName, list[DependantName]]:
    inverse_dependency_map = defaultdict(set)
    for package, dependencies in dependency_map.items():
        for dependency in dependencies:
            inverse_dependency_map[dependency].add(package)
    serializable_map = {k: list(v) for k, v in inverse_dependency_map.items()}
    return serializable_map


def count_all_dependants(
    transitive_dependant_map: dict[PackageName, list[DependantName]]
) -> dict[PackageName, int]:
    return {k: len(v) for k, v in transitive_dependant_map.items()}

def build_transitive_dependant_map(
    inverse_dependency_map: dict[PackageName, list[DependantName]]
) -> dict[PackageName, list[DependantName]]:
    logging.debug('Building graph...')
    graph = nx.DiGraph(inverse_dependency_map)
    logging.debug('Building transitive dependant map...')
    no_dependants = {
        package: list(nx.descendants(graph, package))
        for package in inverse_dependency_map.keys()
    }
    return no_dependants


def create_dependency_map_from_pages(in_path: Path) -> dict[PackageName, list[DependencyName]]:
    dependency_map = {}
    for i, child in enumerate(in_path.iterdir()):
        if child.suffix != '.json':
            continue
        logging.debug('Loading %dth file %s', i, child)
        with open(child, 'r') as fp:
            data = json.load(fp)
        page = CouchDBPage(**data)
        logging.debug('Stripping data...')
        dependency_map.update(create_dependency_map(page))
    return dependency_map

def load_json(in_path: Path) -> Any:
    logging.info('Loading data from %s.', in_path)
    with open(in_path, 'r') as fp:
        return json.load(fp)


def write_json(out_path: Path, data: Any, **kwargs):
    logging.info('Writing data to %s.', out_path)
    with open(out_path, 'w') as fp:
        json.dump(data, fp, **kwargs)
    logging.info('Successfully written data to %s.', out_path)


def set_up_logging():
    formatter = logging.Formatter(
        fmt='%(asctime)s %(levelname)-8.8s [%(name)-10.10s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler = logging.FileHandler('most-depended-upon.log')
    file_handler.setFormatter(formatter)
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)
    root_logger.setLevel(logging.DEBUG)


def parse_args() -> Args:
    parser = argparse.ArgumentParser()
    parser.add_argument('--in-path',
                        '-i',
                        help=('Path to read data from. Usually a doc file, except when using '
                              '--preprocess-from-pages, then it\'s the path to the pages directory.'),
                        required=True,
                        type=Path)
    parser.add_argument('--out-path',
                        '-o',
                        help='Destination to write the resulting file to.',
                        required=True,
                        type=Path)
    mutex_group = parser.add_mutually_exclusive_group(required=True)
    mutex_group.add_argument('--strip',
                             help='Remove all unnecessary parts of the raw registry doc file.',
                             action='store_true')
    mutex_group.add_argument('--strip-from-pages',
                             help='Remove all unnecessary parts, given a directory of raw registry doc pages.',
                             action='store_true')
    mutex_group.add_argument('--build-dependant-map',
                             help='Build the dependant map from the preprocessed data.',
                             action='store_true')
    mutex_group.add_argument('--build-transitive-dependant-map',
                             help='Build the transitive dependant map from the dependant map.',
                             action='store_true')
    mutex_group.add_argument('--count-direct',
                             dest='count_direct_dependants',
                             help='Count the number of direct dependants for a dependant map.',
                             action='store_true')
    mutex_group.add_argument('--count-transitive',
                             dest='count_transitive_dependants',
                             help='Count the number of transitive dependants for a dependant map.',
                             action='store_true')
    args = parser.parse_args(namespace=Args())
    return args


def main():
    set_up_logging()
    args = parse_args()
    if args.strip_from_pages:
        logging.info('Preprocessing pages from dir %s', args.in_path)
        dependency_map = create_dependency_map_from_pages(args.in_path)
        write_json(args.out_path, dependency_map)
        exit(0)
    else:
        data = load_json(args.in_path)
    if args.strip:
        logging.info('Preprocessing file %s', args.in_path)
        dependency_map = create_dependency_map(CouchDBPage(**data))
        write_json(args.out_path, dependency_map)
    elif args.build_dependant_map:
        logging.info('Building dependant map from file %s', args.in_path)
        inverse_dependency_map = build_inverse_dependency_map(data)
        write_json(args.out_path, inverse_dependency_map)
    elif args.build_transitive_dependant_map:
        logging.info('Building transitive dependant map from file %s.', args.in_path)
        transitive_dependant_map = build_transitive_dependant_map(data)
        write_json(args.out_path, transitive_dependant_map)
    elif args.count_direct_dependants:
        logging.info('Counting direct dependencies from %s.', args.in_path)
        most_direct_depended_upon = list(
            sorted(
                [(name, len(deps)) for name, deps in data.items()],
                key=lambda x: x[1],
                reverse=True
            )
        )
        write_json(args.out_path, most_direct_depended_upon, indent=2)
    elif args.count_transitive_dependants:
        logging.info('Counting transitive dependencies from %s.', args.in_path)
        all_dependant_counts = count_all_dependants(data)
        most_transitive_depended_upon = list(
            sorted(
                [(name, count) for name, count in all_dependant_counts.items()],
                key=lambda x: x[1],
                reverse=True
            )
        )
        write_json(args.out_path, most_transitive_depended_upon, indent=2)


if __name__ == '__main__':
    main()
