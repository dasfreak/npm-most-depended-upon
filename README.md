# MOST DEPENDED UPON PACKAGES OF NPM
Sometimes you just need to know which packages are the most important to the npm ecosystem.

## HOW TO USE
0. Download list of available packages (including meta information) from npm
  - `curl -o package_index_$(date --iso-8601=seconds).json https://replicate.npmjs.com/_all_docs?include_docs=true`
  - WARNING: This file is HUGE, around 50 GB
0. Run script
  - `python main.py --infile package_index.json`
  - Grab a coffee this may take a while
0. Profit

```
usage: main.py [-h] [--loglevel {DEBUG,INFO,WARNING,ERROR,CRITICAL}] [--processes PROCESSES] --infile
               INFILE [--outfile OUTFILE] [--limit LIMIT]

Calculate the most dependend upon packages on npm.

optional arguments:
  -h, --help            show this help message and exit
  --loglevel {DEBUG,INFO,WARNING,ERROR,CRITICAL}
                        Which logelevel to use (default: INFO)
  --processes PROCESSES
                        Number of processes to use (default: 4)
  --infile INFILE       Filename of the package list you downloaded from npm (default: None)
  --outfile OUTFILE     Filename to which results will be written (default: most_dependend_upon.json)
  --limit LIMIT         Return the n most dependend upon packages only, use -1 for untruncted results
                        (default: -1)

```
