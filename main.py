import json
import logging
import argparse
import multiprocessing

parser = argparse.ArgumentParser(
    description='Calculate the most-depended upon packages on npm.',
    formatter_class=argparse.ArgumentDefaultsHelpFormatter)
parser.add_argument('--loglevel',
                    choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
                    default='INFO',
                    help='Which logelevel to use')
parser.add_argument('--processes',
                    type=int,
                    default=multiprocessing.cpu_count(),
                    help='Number of processes to use')
parser.add_argument(
    '--infile',
    type=str,
    required=True,
    help='Filename of the package list you downloaded from npm')
parser.add_argument('--outfile',
                    type=str,
                    default='most_depended_upon.json',
                    help='Filename to which results will be written')
parser.add_argument(
    '--limit',
    type=int,
    default=-1,
    help=
    'Return the n most depended-upon packages only, use -1 for untruncted results'
)

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


def get_dependencies_per_package(package):
    # there are packages without a name... However, name == id
    name = package['doc'].get('name') or package['id']

    try:
        latest_version = package['doc']['dist-tags']['latest']
    except KeyError:
        # sometimes packages don't have a 'latest' version
        logger.warning(f'Package {name} does not have a latest version')
        return []

    try:
        dependencies = list(package['doc']['versions'][latest_version].get('dependencies', {}).keys())
    except KeyError:
        # sometimes packages list versions as latest that do not exist
        logger.warning(
            f'Package {name} does not have version {latest_version}')
        return []

    logger.debug(f'Package {name} got {len(dependencies)} dependencies')
    return dependencies


def main():
    logger.info(f'Using {args.processes} worker processes')
    most_depended_upon = {}

    with multiprocessing.Pool(processes=args.processes) as pool:
        for result in pool.imap_unordered(get_dependencies_per_package, get_packages()):
            # Count occurance per package in a dictionary
            for dependency in result:
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


if __name__ == '__main__':
    main()
