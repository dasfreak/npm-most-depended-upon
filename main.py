import json
import logging
import argparse

import asciitree

parser = argparse.ArgumentParser(
    description='Calculate the most-depended upon packages on npm.',
    formatter_class=argparse.ArgumentDefaultsHelpFormatter)
parser.add_argument('--loglevel',
                    choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
                    default='INFO',
                    help='Which logelevel to use')
parser.add_argument('--preprocess', default=False, action='store_true', help='Preprocess the package index to speed up processing')
parser.add_argument('--infile',
                    type=str,
                    help='Filename of the package list you downloaded from npm')
parser.add_argument('--dependency_tree', default=False, action='store_true', help='Build a dependency tree for a given package')
parser.add_argument('--package',
                    type=str,
                    help='Package for which a dependency tree should be build')
parser.add_argument('--outfile',
                    type=str,
                    default='most_depended_upon.json',
                    help='Filename to which results will be written')
parser.add_argument('--limit',
                    type=int,
                    default=-1,
                    help=
                    'Return the n most depended-upon packages only, use -1 for untruncted results')

args = parser.parse_args()

loglevel = {
    'DEBUG': logging.DEBUG,
    'INFO': logging.INFO,
    'WARNING': logging.WARNING,
    'ERROR': logging.ERROR,
    'CRITICAL': logging.CRITICAL
}
logger = logging.getLogger(__name__)
logger.setLevel(loglevel[args.loglevel])
logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s')

# get the package index from npm:
# curl -o package_index_$(date --iso-8601=seconds).json https://replicate.npmjs.com/_all_docs?include_docs=true


def get_packages():
    logger.info(f'Reading from {args.infile}')
    with open(args.infile, 'r') as infile:
        # skip first line
        line = infile.readline()

        # remove trailing newline and comma
        line = infile.readline().replace(',\n', '')

        # read huge ass JSON linewise and yield a single package's meta data
        while line:
            try:
                package = json.loads(line)
            except BaseException as exc:
                logger.warning(f'Could not parse JSON: {line.strip()}: {exc}')
                continue
            finally:
                line = infile.readline().replace(',\n', '')

            yield package


def determine_most_depended_upon():
    logger.info(f'Starting to count dependencies')
    most_depended_upon = {}

    with open('preprocessed.json', 'r') as infile:
        preprocessed = json.load(infile)

    for package in preprocessed:
        logger.debug(f'{package} got {len(preprocessed[package])} dependencies')
        for dependency in preprocessed[package]:
            if most_depended_upon.get(dependency):
                most_depended_upon[dependency] += 1
            else:
                most_depended_upon[dependency] = 1

    logger.info('Sorting results by dependency count')
    if args.limit > 0:
        logger.info(f'Only returning the {args.limit} most depended upon packages')
        most_depended_upon = dict(
            sorted(most_depended_upon.items(),
                   key=lambda item: item[1],
                   reverse=True)[:args.limit])
    else:
        most_depended_upon = dict(
            sorted(most_depended_upon.items(),
                   key=lambda item: item[1],
                   reverse=True))

    logger.info(f'Writing results to file: {args.outfile}')
    with open(args.outfile, 'w') as outfile:
        json.dump(most_depended_upon, outfile)

    logger.info('Goodbye')


def preprocess(package):
    name = package['id']

    try:
        latest_version = package['doc']['dist-tags']['latest']
    except KeyError:
        # sometimes packages don't have a 'latest' version
        logger.warning(f'{name} does not have a latest version')
        return {name: []}

    try:
        dependencies = list(package['doc']['versions'][latest_version].get('dependencies', {}).keys())
    except KeyError:
        # sometimes packages list versions as latest that do not exist
        logger.warning(f'{name} does not have version {latest_version}')
        return {name: []}

    return {name: dependencies}


def get_dependencies(package, preprocessed):
    try:
        return {dependency: get_dependencies(dependency, preprocessed) for dependency in preprocessed[package]}
    except KeyError:
        logger.error(f'{package} is not in the package index')


def build_dependency_tree(package):
    logger.info(f'Building dependency tree for {package}')
    with open('preprocessed.json', 'r') as infile:
        preprocessed = json.load(infile)
        dependency_tree = {package: get_dependencies(package, preprocessed)}
        tr = asciitree.LeftAligned()
        print(tr(dependency_tree))


if __name__ == '__main__':
    if args.preprocess:
        if not args.infile:
            parser.error("--preprocess requires --infile")
        preprocessed = {}

        for package in get_packages():
            small.update(preprocess(package))

        with open('preprocessed.json', 'w') as outfile:
            json.dump(preprocessed, outfile)
    elif args.dependency_tree:
        if not args.package:
            parser.error("--dependency_tree requires --package")
        build_dependency_tree(args.package)
    else:
        determine_most_depended_upon()
